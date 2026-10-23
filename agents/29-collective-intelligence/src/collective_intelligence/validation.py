"""Strict byte, syntax, structure, identity, and numeric parsing boundary.

Lexical depth is checked before JSON decoding to avoid recursive parser work.
Numbers use bounded Decimal exponents before exact rational conversion. External
replay records are fully validated before any independent adapter is invoked.
"""

import json
from decimal import Decimal, InvalidOperation
from fractions import Fraction

from .core import (CRITERIA, PROBLEM, ROLES, Critique, InvalidInput, Proposal,
                   Request, ReviewInput, validate_reviews)

MAX_BYTES = 32_768


def _depth(raw: bytes) -> None:
    depth = 0
    quoted = escaped = False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                quoted = False
        elif char == 34:
            quoted = True
        elif char in (91, 123):
            depth += 1
            if depth > 8:
                raise InvalidInput("JSON depth limit")
        elif char in (93, 125):
            depth -= 1


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidInput("Duplicate key")
        result[key] = value
    return result


def _number(token: str) -> Decimal:
    if len(token) > 32:
        raise InvalidInput("Numeric literal limit")
    value = Decimal(token)
    if not value.is_finite() or not -12 <= value.as_tuple().exponent <= 6:
        raise InvalidInput("Numeric exponent limit")
    return value


def _integer(token: str) -> int:
    if len(token) > 32:
        raise InvalidInput("Numeric literal limit")
    return int(token)


def _constant(_: str) -> None:
    raise InvalidInput("Nonfinite value")


def _tree(value: object, count: list[int]) -> None:
    count[0] += 1
    if count[0] > 512:
        raise InvalidInput("JSON value limit")
    if type(value) is str:
        if len(value) > 1024 or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise InvalidInput("Invalid string")
    elif type(value) is dict:
        if len(value) > 32:
            raise InvalidInput("Object cardinality limit")
        for key, item in value.items():
            _tree(key, count)
            _tree(item, count)
    elif type(value) is list:
        if len(value) > 32:
            raise InvalidInput("Array cardinality limit")
        for item in value:
            _tree(item, count)
    elif type(value) is Decimal:
        if not value.is_finite() or abs(value) > 1_000_000:
            raise InvalidInput("Numeric range limit")
    elif type(value) is int:
        if abs(value) > 1_000_000:
            raise InvalidInput("Numeric range limit")
    elif value is not None and type(value) is not bool:
        raise InvalidInput("Unsupported value")


def _object(value: object, keys: set[str]) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise InvalidInput("Invalid object fields")
    return value


def load_request(raw: bytes) -> Request:
    """Parse a complete bounded request; diagnostic strings contain no input."""
    try:
        if type(raw) is not bytes or len(raw) > MAX_BYTES:
            raise InvalidInput("Input byte limit")
        _depth(raw)
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_float=_number, parse_int=_integer, parse_constant=_constant)
        _tree(data, [0])
        data = _object(data, {"problem_id", "max_rounds", "review_rounds"})
        if data["problem_id"] != PROBLEM.id or type(data["problem_id"]) is not str:
            raise InvalidInput("Unknown problem")
        limit = data["max_rounds"]
        if type(limit) is not int or limit not in (1, 2):
            raise InvalidInput("Invalid round budget")
        rounds = data["review_rounds"]
        if rounds is None:
            return Request(PROBLEM.id, limit, None)
        if type(rounds) is not list or len(rounds) != limit:
            raise InvalidInput("Invalid round count")
        parsed = []
        proposals = tuple(Proposal(r.id, PROBLEM, c) for r, c in zip(ROLES, CRITERIA, strict=True))
        for number, item in enumerate(rounds, 1):
            item = _object(item, {"number", "critiques"})
            if type(item["number"]) is not int or item["number"] != number:
                raise InvalidInput("Invalid round identity")
            if type(item["critiques"]) is not list or len(item["critiques"]) > 6:
                raise InvalidInput("Invalid review count")
            critiques = []
            for raw_critique in item["critiques"]:
                c = _object(raw_critique, {"id", "reviewer_id", "criterion_id", "score", "reason"})
                if any(type(c[key]) is not str for key in ("id", "reviewer_id", "criterion_id", "reason")):
                    raise InvalidInput("Invalid critique text")
                if type(c["score"]) not in (int, Decimal) or not 0 <= c["score"] <= 10:
                    raise InvalidInput("Invalid score")
                critiques.append(Critique(c["id"], c["reviewer_id"], c["criterion_id"],
                                          Fraction(c["score"]), c["reason"]))
            record = ReviewInput(number, tuple(critiques))
            validate_reviews(number, record.critiques, proposals)
            parsed.append(record)
        return Request(PROBLEM.id, limit, tuple(parsed))
    except (ValueError, TypeError, UnicodeError, RecursionError, InvalidOperation, OverflowError) as exc:
        raise InvalidInput("Invalid request") from None
