"""Strict JSON-to-domain boundary. Validation precedes all evidence processing.

Bounded bytes, depth, nodes, number precision/exponents and array cardinality
bound parsing and exact-rational work. Unknown fields and duplicate keys are
errors, including within unused knowledge. Diagnostics never echo input text.
"""
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import cast

from .domain import (CONDITIONS, SIGNALS, Band, BeliefDistribution, KnowledgeRecord,
                     Observation, Request, ReviewDecision, Signal, Vector)

MAX_BYTES = 65_536
MAX_DEPTH = 8
MAX_NODES = 2_048
ID = re.compile(r"[a-z][a-z0-9-]{0,31}\Z", re.ASCII)
TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z", re.ASCII)


class InputFault(ValueError):
    """Stable public error code, without submitted data or underlying exceptions."""
    def __init__(self, code: str, outcome: str = "invalid_input"):
        super().__init__(code)
        self.code = code
        self.outcome = outcome


def require(condition: bool, code: str) -> None:
    if not condition:
        raise InputFault(code)


def pairs(items: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in items:
        require(key not in result, "duplicate_key")
        result[key] = value
    return result


def number(token: str) -> Decimal:
    if len(token) > 32:
        raise InputFault("number_size", "limit")
    try:
        value = Decimal(token)
    except InvalidOperation:
        raise InputFault("number") from None
    require(value.is_finite(), "nonfinite")
    if abs(value.as_tuple().exponent) > 12:
        raise InputFault("number_exponent", "limit")
    return value


def nonfinite(_: str) -> None:
    raise InputFault("nonfinite")


def depth_guard(text: str) -> None:
    # Scan delimiters outside strings before json.loads can recurse on hostile input.
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise InputFault("depth", "limit")
        elif char in "]}":
            depth -= 1


def tree_guard(value: object) -> None:
    stack = [value]
    count = 0
    while stack:
        item = stack.pop()
        count += 1
        if count > MAX_NODES:
            raise InputFault("nodes", "limit")
        if isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str):
            require(not any(0xD800 <= ord(char) <= 0xDFFF for char in item), "unicode")
        else:
            require(isinstance(item, Decimal), "type")


def obj(value: object, fields: set[str]) -> dict:
    require(isinstance(value, dict), "object")
    require(set(value) == fields, "fields")
    return value


def identifier(value: object) -> str:
    require(isinstance(value, str) and ID.fullmatch(value) is not None, "identifier")
    return value


def choice(value: object, options: tuple[str, ...], code: str) -> str:
    require(isinstance(value, str) and value in options, code)
    return value


def timestamp(value: object) -> datetime:
    require(isinstance(value, str) and TIME.fullmatch(value) is not None, "timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise InputFault("timestamp") from None


def numeric(value: object, maximum: int = 1) -> Fraction:
    require(isinstance(value, Decimal), "number")
    require(0 <= value <= maximum, "range")
    return Fraction(value)


def vector(value: object) -> Vector:
    mapping = obj(value, set(CONDITIONS))
    return cast(Vector, tuple(numeric(mapping[name]) for name in CONDITIONS))


def array(value: object, maximum: int) -> list:
    require(isinstance(value, list), "array")
    if len(value) > maximum:
        raise InputFault("array_size", "limit")
    return value


def parse_request(raw: bytes) -> Request:
    """Only supported untrusted entry point; returns trusted immutable run state."""
    if len(raw) > MAX_BYTES:
        raise InputFault("bytes", "limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise InputFault("utf8") from None
    depth_guard(text)
    try:
        root = json.loads(text, object_pairs_hook=pairs, parse_int=number,
                          parse_float=number, parse_constant=nonfinite)
    except (json.JSONDecodeError, RecursionError):
        raise InputFault("json") from None
    tree_guard(root)
    root = obj(root, {"schema_version", "as_of", "priors", "observations", "knowledge", "review"})
    require(root["schema_version"] == "synthetic-1", "schema_version")
    as_of = timestamp(root["as_of"])
    priors = vector(root["priors"])
    require(sum(priors, Fraction(0)) == 1, "prior_mass")
    review = cast(ReviewDecision, choice(root["review"], ("pending", "acknowledged", "rejected"), "review"))
    observations = []
    for item in array(root["observations"], 2):
        item = obj(item, {"id", "signal", "value", "unit", "observed_at"})
        unit = choice(item["unit"], ("ticks", "milli_ticks"), "unit")
        scale = 1 if unit == "ticks" else 1000
        obs = Observation(identifier(item["id"]), cast(Signal, choice(item["signal"], SIGNALS, "signal")),
                          numeric(item["value"], scale) / scale, timestamp(item["observed_at"]))
        require(obs.observed_at <= as_of, "future_time")
        observations.append(obs)
    require(len({obs.id for obs in observations}) == len(observations), "duplicate_observation_id")
    require(len({obs.signal for obs in observations}) == len(observations), "duplicate_signal")
    knowledge = []
    for item in array(root["knowledge"], 16):
        item = obj(item, {"id", "signal", "band", "source", "version", "retrieved_at", "likelihoods"})
        record = KnowledgeRecord(identifier(item["id"]),
                                 cast(Signal, choice(item["signal"], SIGNALS, "signal")),
                                 cast(Band, choice(item["band"], ("low", "high"), "band")),
                                 identifier(item["source"]), identifier(item["version"]),
                                 timestamp(item["retrieved_at"]), vector(item["likelihoods"]))
        require(record.retrieved_at <= as_of, "future_time")
        knowledge.append(record)
    require(len({record.id for record in knowledge}) == len(knowledge), "duplicate_knowledge_id")
    return Request(as_of, BeliefDistribution(priors), tuple(observations), tuple(knowledge), review)
