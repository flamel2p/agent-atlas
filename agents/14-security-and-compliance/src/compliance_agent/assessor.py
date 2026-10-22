"""Assess a bounded syntax subset without executing it or retaining source values.

An abstract value records only where sensitivity or uncertainty originated. Each
run owns its bindings. Immutable origin sets let old aliases survive rebinding.
Statements commit only after every expression is supported, so an unsupported
statement cannot produce partial findings or affect the unexamined suffix.
"""

import ast
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import warnings

from .policy import Policy, RULE_ID

SCHEMA_VERSION = 1
ANALYZER_VERSION = "1.0.0"
MAX_SOURCE_BYTES = 16384
MAX_AST_NODES = 512
MAX_AST_DEPTH = 32
MAX_STATEMENTS = 64
MAX_LOG_ARGUMENTS = 8
RESERVED_NAMES = frozenset({"logger", "Sensitive", "Unclassified"})
LOG_METHODS = frozenset({"debug", "info", "warning", "error", "critical"})
GUIDANCE = (
    "Remove sensitive values from logs or replace the whole argument with a fixed public event message.",
    "Have a human inspect uncertain values and unsupported syntax before relying on this assessment.",
    "No remediation was applied. Masking, hashing, truncation, and comments do not grant exceptions.",
)


class Reason(StrEnum):
    """Closed report codes. Source text and parser exceptions never become reasons."""

    SENSITIVE_LOG = "sensitive_log"
    UNCERTAIN_LOG = "uncertain_log"
    UNSUPPORTED_SYNTAX = "unsupported_syntax"
    RESERVED_BINDING = "reserved_binding"
    ARGUMENT_LIMIT = "argument_limit"
    SOURCE_SIZE_LIMIT = "source_size_limit"
    INVALID_UTF8 = "invalid_utf8"
    INVALID_SYNTAX = "invalid_syntax"
    PARSER_RECURSION_LIMIT = "parser_recursion_limit"
    AST_NODE_LIMIT = "ast_node_limit"
    AST_DEPTH_LIMIT = "ast_depth_limit"
    STATEMENT_LIMIT = "statement_limit"


@dataclass(frozen=True, order=True)
class Span:
    """Source location using 1-based lines and 0-based UTF-8 byte columns.

    End positions are exclusive. Spans identify evidence without quoting it.
    """

    line: int
    column: int
    end_line: int
    end_column: int

    @classmethod
    def of(cls, node: ast.AST) -> "Span":
        return cls(node.lineno, node.col_offset, node.end_lineno, node.end_col_offset)

    def to_dict(self) -> dict[str, int]:
        return {
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "end_column": self.end_column,
        }


@dataclass(frozen=True)
class Value:
    """Independent provenance sets, never an actual Python value or declassification claim."""

    sensitive: frozenset[Span] = frozenset()
    uncertain: frozenset[Span] = frozenset()

    def union(self, other: "Value") -> "Value":
        return Value(self.sensitive | other.sensitive, self.uncertain | other.uncertain)


@dataclass(frozen=True)
class Finding:
    reason: Reason
    location: Span | None = None
    origins: Value = Value()

    @property
    def kind(self) -> str:
        return "violation" if self.reason == Reason.SENSITIVE_LOG else "review"

    def to_dict(self) -> dict[str, object]:
        return {
            "reason": self.reason.value,
            "kind": self.kind,
            "rule_id": RULE_ID,
            "location": self.location.to_dict() if self.location else None,
            "sensitive_origins": [span.to_dict() for span in sorted(self.origins.sensitive)],
            "uncertain_origins": [span.to_dict() for span in sorted(self.origins.uncertain)],
        }


@dataclass(frozen=True)
class Assessment:
    """Immutable run result. Coverage means supported syntax, not regulatory assurance."""

    policy: Policy
    source_sha256: str | None
    input_complete: bool
    coverage_complete: bool
    statements_total: int | None
    statements_analyzed: int = 0
    log_calls_analyzed: int = 0
    findings: tuple[Finding, ...] = ()

    @property
    def status(self) -> str:
        if any(finding.kind == "violation" for finding in self.findings):
            return "blocked"
        return "review_required" if self.findings else "passed"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "analyzer_version": ANALYZER_VERSION,
            "status": self.status,
            "policy": self.policy.to_dict(),
            "source_sha256": self.source_sha256,
            "input_complete": self.input_complete,
            "coverage": {
                "complete": self.coverage_complete,
                "statements_total": self.statements_total,
                "statements_analyzed": self.statements_analyzed,
                "log_calls_analyzed": self.log_calls_analyzed,
            },
            "findings": [finding.to_dict() for finding in self.findings],
            "guidance": list(GUIDANCE),
        }


class Unsupported(Exception):
    """Internal transaction abort carrying only safe evidence locations."""

    def __init__(self, node: ast.AST, reason: Reason = Reason.UNSUPPORTED_SYNTAX):
        self.finding = Finding(reason, Span.of(node))


def _expression(node: ast.AST, bindings: dict[str, Value]) -> Value:
    if isinstance(node, ast.Constant) and type(node.value) is str:
        return Value()
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        return bindings.get(node.id, Value(uncertain=frozenset({Span.of(node)})))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _expression(node.left, bindings).union(_expression(node.right, bindings))
    if isinstance(node, ast.JoinedStr):
        value = Value()
        for part in node.values:
            if isinstance(part, ast.Constant) and type(part.value) is str:
                continue
            if not isinstance(part, ast.FormattedValue) or part.conversion != -1 or part.format_spec is not None:
                raise Unsupported(part)
            value = value.union(_expression(part.value, bindings))
        return value
    raise Unsupported(node)


def _target(node: ast.AST) -> str:
    if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Store):
        raise Unsupported(node)
    if node.id in RESERVED_NAMES:
        raise Unsupported(node, Reason.RESERVED_BINDING)
    return node.id


def _statement(node: ast.stmt, bindings: dict[str, Value]) -> tuple[tuple[str, Value] | None, tuple[Finding, ...], int]:
    """Return a pending binding, findings, and log count without changing run state."""
    if isinstance(node, ast.AnnAssign):
        name = _target(node.target)
        if (
            node.simple != 1
            or not isinstance(node.annotation, ast.Name)
            or node.annotation.id not in {"Sensitive", "Unclassified"}
            or not isinstance(node.value, ast.Constant)
            or type(node.value.value) is not str
        ):
            raise Unsupported(node)
        origin = frozenset({Span.of(node.value)})
        value = Value(sensitive=origin) if node.annotation.id == "Sensitive" else Value(uncertain=origin)
        return (name, value), (), 0
    if isinstance(node, ast.Assign):
        if len(node.targets) != 1:
            raise Unsupported(node)
        name = _target(node.targets[0])
        return (name, _expression(node.value, bindings)), (), 0
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        call = node.value
        function = call.func
        if not (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == "logger"
            and function.attr in LOG_METHODS
        ) or call.keywords:
            raise Unsupported(call)
        if not 1 <= len(call.args) <= MAX_LOG_ARGUMENTS:
            raise Unsupported(call, Reason.ARGUMENT_LIMIT)
        value = Value()
        for argument in call.args:
            value = value.union(_expression(argument, bindings))
        # All arguments must validate before any finding is committed. A sensitive
        # first argument does not authorize a claim about an unsupported call.
        findings = []
        if value.sensitive:
            findings.append(Finding(Reason.SENSITIVE_LOG, Span.of(call), Value(sensitive=value.sensitive)))
        if value.uncertain:
            findings.append(Finding(Reason.UNCERTAIN_LOG, Span.of(call), Value(uncertain=value.uncertain)))
        return None, tuple(findings), 1
    raise Unsupported(node)


def _tree_limit(tree: ast.Module) -> Reason | None:
    """Iterative preflight counts all AST nodes, including context and operator nodes."""
    pending = [(tree, 1)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > MAX_AST_NODES:
            return Reason.AST_NODE_LIMIT
        if depth > MAX_AST_DEPTH:
            return Reason.AST_DEPTH_LIMIT
        pending.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
    if len(tree.body) > MAX_STATEMENTS:
        return Reason.STATEMENT_LIMIT
    return None


def assess(source_bytes: bytes, policy: Policy) -> Assessment:
    """Pure scan of one byte snapshot against a validated policy.

    Preflight rejection interprets zero statements. A later unsupported statement
    retains only committed prefix findings. No source content survives the result.
    """
    if len(source_bytes) > MAX_SOURCE_BYTES:
        return Assessment(policy, None, False, False, None, findings=(Finding(Reason.SOURCE_SIZE_LIMIT),))
    digest = hashlib.sha256(source_bytes).hexdigest()
    try:
        source = source_bytes.decode("utf-8")
    except UnicodeError:
        return Assessment(policy, digest, True, False, None, findings=(Finding(Reason.INVALID_UTF8),))
    try:
        # Python can warn about string escapes during AST parsing. Those messages
        # contain source-derived text, so only our fixed report codes may escape.
        with warnings.catch_warnings(action="ignore"):
            tree = ast.parse(source, mode="exec")
    except (SyntaxError, ValueError):
        return Assessment(policy, digest, True, False, None, findings=(Finding(Reason.INVALID_SYNTAX),))
    except RecursionError:
        return Assessment(policy, digest, True, False, None, findings=(Finding(Reason.PARSER_RECURSION_LIMIT),))
    limit = _tree_limit(tree)
    if limit:
        return Assessment(policy, digest, True, False, len(tree.body), findings=(Finding(limit),))

    bindings: dict[str, Value] = {}
    findings: list[Finding] = []
    analyzed = 0
    log_calls = 0
    for statement in tree.body:
        try:
            binding, pending_findings, pending_logs = _statement(statement, bindings)
        except Unsupported as error:
            findings.append(error.finding)
            return Assessment(policy, digest, True, False, len(tree.body), analyzed, log_calls, tuple(findings))
        if binding is not None:
            bindings[binding[0]] = binding[1]
        findings.extend(pending_findings)
        log_calls += pending_logs
        analyzed += 1
    return Assessment(policy, digest, True, True, len(tree.body), analyzed, log_calls, tuple(findings))
