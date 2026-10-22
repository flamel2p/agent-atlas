"""Reject-by-default interpreter for a deliberately small Python-shaped language.

AST means the parser's abstract syntax tree. We inspect every node, including
unreachable branches, then interpret permitted nodes ourselves. No candidate is
executed by CPython. Integers have bounded magnitude. Comparisons occur only as
direct if conditions, and arithmetic and comparisons require exact integers.
Return requires an integer fee. Each invocation owns fresh locals and
step fuel. This in-process parser/interpreter is not a production sandbox.
"""

import ast

from .domain import Feedback, ORACLE, TestResult

MAX_SOURCE_BYTES = 2048
MAX_NODES = 80
MAX_DEPTH = 12
MAX_STEPS = 100
MAX_INTEGER = 1_000_000


class Rejected(ValueError):
    """A normalized syntax, policy, or evaluation failure with a stable code."""

    def __init__(self, kind: str, code: str):
        self.kind, self.code = kind, code
        super().__init__(code)


def source_bytes(source: str) -> bytes:
    if type(source) is not str:
        raise Rejected("policy", "source_type")
    # Check characters first so encoding an enormous proposal cannot allocate
    # an unbounded second copy. UTF-8 uses at least one byte per character.
    if len(source) > MAX_SOURCE_BYTES:
        raise Rejected("policy", "source_size")
    try:
        encoded = source.encode("utf-8")
    except UnicodeError:
        raise Rejected("policy", "source_encoding") from None
    if len(encoded) > MAX_SOURCE_BYTES:
        raise Rejected("policy", "source_size")
    return encoded


_ALLOWED = {
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Assign, ast.If,
    ast.Return, ast.Name, ast.Load, ast.Store, ast.Constant, ast.BinOp,
    ast.Add, ast.Sub, ast.Mult, ast.Compare, ast.Eq, ast.NotEq,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE,
}


def _parse(source: str) -> ast.FunctionDef:
    source_bytes(source)
    try:
        tree = ast.parse(source, mode="exec")
    except (SyntaxError, ValueError):
        raise Rejected("syntax", "invalid_syntax") from None
    except (RecursionError, MemoryError):
        raise Rejected("syntax", "parser_limit") from None
    stack = [(tree, 1, None)]
    count = 0
    while stack:
        node, depth, parent = stack.pop()
        count += 1
        if count > MAX_NODES:
            raise Rejected("policy", "node_limit")
        if depth > MAX_DEPTH:
            raise Rejected("policy", "depth_limit")
        if type(node) not in _ALLOWED:
            raise Rejected("policy", "forbidden_syntax")
        if isinstance(node, ast.Constant) and (
            type(node.value) is not int or abs(node.value) > MAX_INTEGER
        ):
            raise Rejected("policy", "integer_literal")
        if isinstance(node, ast.Assign) and (
            len(node.targets) != 1 or type(node.targets[0]) is not ast.Name
        ):
            raise Rejected("policy", "assignment_target")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == "__debug__":
            raise Rejected("policy", "reserved_assignment")
        if isinstance(node, ast.Compare) and len(node.ops) != 1:
            raise Rejected("policy", "chained_comparison")
        if isinstance(node, ast.Compare) and not (
            isinstance(parent, ast.If) and parent.test is node
        ):
            raise Rejected("policy", "comparison_context")
        if isinstance(node, ast.If) and type(node.test) is not ast.Compare:
            raise Rejected("policy", "condition_comparison_required")
        stack.extend((child, depth + 1, node) for child in ast.iter_child_nodes(node))
    if len(tree.body) != 1 or type(tree.body[0]) is not ast.FunctionDef:
        raise Rejected("policy", "top_level")
    function = tree.body[0]
    args = function.args
    if (
        function.name != "shipping_fee" or function.decorator_list
        or function.returns is not None or function.type_params
        or args.posonlyargs or args.kwonlyargs or args.defaults
        or args.kw_defaults or args.vararg or args.kwarg
        or [arg.arg for arg in args.args] != ["weight_kg", "subtotal_rm"]
        or any(arg.annotation is not None for arg in args.args)
    ):
        raise Rejected("policy", "function_signature")
    # A FunctionDef is allowed only as the sole module child, never nested.
    if any(type(node) is ast.FunctionDef and node is not function for node in ast.walk(tree)):
        raise Rejected("policy", "nested_function")
    return function


def _integer(value: int | bool) -> int:
    if type(value) is not int:
        raise Rejected("evaluation", "integer_required")
    if abs(value) > MAX_INTEGER:
        raise Rejected("evaluation", "integer_overflow")
    return value


class _Machine:
    def __init__(self, weight: int, subtotal: int, steps: int):
        self.locals: dict[str, int | bool] = {"weight_kg": weight, "subtotal_rm": subtotal}
        self.remaining = steps

    def tick(self) -> None:
        self.remaining -= 1
        if self.remaining < 0:
            raise Rejected("evaluation", "step_limit")

    def expression(self, node: ast.expr) -> int | bool:
        self.tick()
        match node:
            case ast.Constant(value=value):
                return _integer(value)
            case ast.Name(id=name):
                if name not in self.locals:
                    raise Rejected("evaluation", "unbound_name")
                return self.locals[name]
            case ast.BinOp(left=left, op=op, right=right):
                first = _integer(self.expression(left))
                second = _integer(self.expression(right))
                match op:
                    case ast.Add(): value = first + second
                    case ast.Sub(): value = first - second
                    case ast.Mult(): value = first * second
                    case _: raise Rejected("evaluation", "unsupported_operator")
                return _integer(value)
            case ast.Compare(left=left, ops=[op], comparators=[right]):
                first = _integer(self.expression(left))
                second = _integer(self.expression(right))
                match op:
                    case ast.Eq(): return first == second
                    case ast.NotEq(): return first != second
                    case ast.Lt(): return first < second
                    case ast.LtE(): return first <= second
                    case ast.Gt(): return first > second
                    case ast.GtE(): return first >= second
            case _:
                raise Rejected("evaluation", "unsupported_expression")
        raise Rejected("evaluation", "unsupported_operator")

    def statements(self, body: list[ast.stmt]) -> int | None:
        for node in body:
            self.tick()
            match node:
                case ast.Assign(targets=[ast.Name(id=name)], value=value):
                    self.locals[name] = self.expression(value)
                case ast.If(test=test, body=yes, orelse=no):
                    returned = self.statements(yes if self.expression(test) else no)
                    if returned is not None:
                        return returned
                case ast.Return(value=value) if value is not None:
                    fee = _integer(self.expression(value))
                    if not 0 <= fee <= 100:
                        raise Rejected("evaluation", "fee_range")
                    return fee
                case ast.Return():
                    raise Rejected("evaluation", "missing_return_value")
                case _:
                    raise Rejected("evaluation", "unsupported_statement")
        return None


def _inputs(weight: int, subtotal: int, step_limit: int) -> None:
    if type(weight) is not int or not 0 <= weight <= 20:
        raise Rejected("input", "weight_range")
    if type(subtotal) is not int or not 0 <= subtotal <= 1000:
        raise Rejected("input", "subtotal_range")
    if type(step_limit) is not int or not 1 <= step_limit <= MAX_STEPS:
        raise Rejected("input", "step_limit_range")


def _execute(function: ast.FunctionDef, weight: int, subtotal: int, steps: int) -> int:
    result = _Machine(weight, subtotal, steps).statements(function.body)
    if result is None:
        raise Rejected("evaluation", "missing_return")
    return result


def interpret(source: str, weight_kg: int, subtotal_rm: int, *, step_limit: int = MAX_STEPS) -> int:
    """Validate source and host inputs, then interpret one isolated invocation."""
    _inputs(weight_kg, subtotal_rm, step_limit)
    return _execute(_parse(source), weight_kg, subtotal_rm, step_limit)


def check_candidate(source: str) -> Feedback:
    """Validate the whole proposal before checking every frozen host test."""
    try:
        function = _parse(source)
    except Rejected as error:
        return Feedback(error.kind, error.code)
    results = []
    for case in ORACLE:
        try:
            actual = _execute(function, case.weight_kg, case.subtotal_rm, MAX_STEPS)
            results.append(TestResult(case.test_id, case.expected, actual, actual == case.expected))
        except Rejected as error:
            results.append(TestResult(case.test_id, case.expected, None, False, error.code))
    return Feedback("tested", tests=tuple(results))
