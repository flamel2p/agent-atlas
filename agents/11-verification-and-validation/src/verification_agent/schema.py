"""Strict bounded JSON schemas for caller claims and host-owned evidence.

Lexical validation constructs immutable domain values once. Metric-dependent
checks follow snapshot validation, because the snapshot owns metric authority.
No parser output, unknown field, or unknown unit can bypass these boundaries.
"""

from datetime import date
from decimal import Decimal
import json
import re
import unicodedata

from .domain import Claim, Evidence, InputError, MetricRule, Quantity, Scope, SourceError, VerificationError
from .files import REQUEST_LIMIT, SNAPSHOT_LIMIT

IDENTIFIER = re.compile(r"[a-z][a-z0-9_-]{0,63}")
PERIOD = re.compile(r"[0-9]{4}-Q[1-4]")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
NUMBER = re.compile(r"-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?")
UNIT_POLICY = {
    "count": ("none", "nonnegative_integer"),
    "milliseconds": ("none", "nonnegative"),
    "relative_percent": ("required", "signed"),
    "percentage_point": ("required", "percentage_point"),
}
SCOPE_FIELDS = {"entity", "metric", "period", "baseline_period"}
CLAIM_FIELDS = {"id", "value", "unit"} | SCOPE_FIELDS
EVIDENCE_FIELDS = CLAIM_FIELDS | {"source", "valid_from", "valid_through"}


def _load(document: bytes, limit: int, error: type[VerificationError]) -> object:
    if type(document) is not bytes:
        raise error("invalid_document_type")
    if len(document) > limit:
        raise error("too_large")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise error("duplicate_key")
            result[key] = value
        return result

    def reject_constant(_value):
        raise error("invalid_json")

    try:
        return json.loads(document.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=reject_constant)
    except (UnicodeError, ValueError, RecursionError):
        raise error("invalid_json") from None


def _object(value, fields: set[str], error: type[VerificationError]) -> dict:
    if type(value) is not dict or value.keys() != fields:
        raise error("invalid_schema")
    return value


def _identifier(value, error: type[VerificationError]) -> str:
    if type(value) is not str or not IDENTIFIER.fullmatch(value):
        raise error("invalid_identifier")
    return value


def _date(value, error: type[VerificationError]) -> date:
    if type(value) is not str or not DATE.fullmatch(value):
        raise error("invalid_date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise error("invalid_date") from None


def _period(value, error: type[VerificationError]) -> str:
    if type(value) is not str or not PERIOD.fullmatch(value) or value.startswith("0000"):
        raise error("invalid_period")
    return value


def _scope(value: dict, error: type[VerificationError]) -> Scope:
    period = _period(value["period"], error)
    baseline = value["baseline_period"]
    if baseline is not None:
        baseline = _period(baseline, error)
        if baseline >= period:
            raise error("invalid_baseline")
    return Scope(_identifier(value["entity"], error), _identifier(value["metric"], error),
                 period, baseline)


def _decimal(value, error: type[VerificationError]) -> Decimal:
    if type(value) is not str or not NUMBER.fullmatch(value):
        raise error("invalid_quantity")
    number = Decimal(value)
    return Decimal(0) if number == 0 else number


def _quantity(value: dict, error: type[VerificationError]) -> Quantity:
    unit = value["unit"]
    if type(unit) is not str or unit not in UNIT_POLICY:
        raise error("invalid_unit")
    return Quantity(_decimal(value["value"], error), unit)


def validate_metric(scope: Scope, quantity: Quantity, rule: MetricRule,
                    error: type[VerificationError]) -> None:
    """Baseline shape always applies; numeric domains apply only in the rule's unit."""
    if (scope.baseline_period is not None) != (rule.baseline == "required"):
        raise error("invalid_baseline")
    if quantity.unit != rule.unit:
        return
    value = quantity.value
    if rule.domain in {"nonnegative", "nonnegative_integer"} and value < 0:
        raise error("outside_domain")
    if rule.domain == "nonnegative_integer" and value != value.to_integral_value():
        raise error("outside_domain")
    if rule.domain == "percentage_point" and not Decimal(-100) <= value <= Decimal(100):
        raise error("outside_domain")


def parse_request(document: bytes) -> tuple[date, tuple[Claim, ...]]:
    root = _object(_load(document, REQUEST_LIMIT, InputError), {"as_of", "claims"}, InputError)
    as_of = _date(root["as_of"], InputError)
    rows = root["claims"]
    if type(rows) is not list or not 1 <= len(rows) <= 32:
        raise InputError("invalid_claim_count")
    claims = []
    ids = set()
    for row in rows:
        row = _object(row, CLAIM_FIELDS, InputError)
        identifier = _identifier(row["id"], InputError)
        if identifier in ids:
            raise InputError("duplicate_claim_id")
        ids.add(identifier)
        claims.append(Claim(identifier, _scope(row, InputError), _quantity(row, InputError)))
    return as_of, tuple(claims)


def parse_snapshot(document: bytes) -> tuple[str, tuple[MetricRule, ...], tuple[Evidence, ...]]:
    root = _object(_load(document, SNAPSHOT_LIMIT, SourceError),
                   {"version", "metrics", "records"}, SourceError)
    version = _identifier(root["version"], SourceError)
    rows = root["metrics"]
    if type(rows) is not list or not 1 <= len(rows) <= 16:
        raise SourceError("invalid_rule_count")
    rules = {}
    for row in rows:
        row = _object(row, {"metric", "unit", "baseline", "tolerance", "domain"}, SourceError)
        metric = _identifier(row["metric"], SourceError)
        if metric in rules:
            raise SourceError("duplicate_metric")
        unit = row["unit"]
        if type(unit) is not str or unit not in UNIT_POLICY:
            raise SourceError("invalid_unit")
        if (row["baseline"], row["domain"]) != UNIT_POLICY[unit]:
            raise SourceError("invalid_rule")
        tolerance = _decimal(row["tolerance"], SourceError)
        if tolerance < 0:
            raise SourceError("invalid_tolerance")
        rules[metric] = MetricRule(metric, unit, row["baseline"], tolerance, row["domain"])
    rows = root["records"]
    if type(rows) is not list or not 1 <= len(rows) <= 256:
        raise SourceError("invalid_record_count")
    evidence = []
    ids = set()
    for row in rows:
        row = _object(row, EVIDENCE_FIELDS, SourceError)
        identifier = _identifier(row["id"], SourceError)
        if identifier in ids:
            raise SourceError("duplicate_evidence_id")
        ids.add(identifier)
        scope, quantity = _scope(row, SourceError), _quantity(row, SourceError)
        rule = rules.get(scope.metric)
        if rule is None:
            raise SourceError("unknown_evidence_metric")
        if quantity.unit != rule.unit:
            raise SourceError("inconsistent_evidence_unit")
        validate_metric(scope, quantity, rule, SourceError)
        source = row["source"]
        if (type(source) is not str or not 1 <= len(source) <= 120 or source != source.strip()
                or any(unicodedata.category(char).startswith("C") for char in source)):
            raise SourceError("invalid_source_label")
        start, end = _date(row["valid_from"], SourceError), _date(row["valid_through"], SourceError)
        if start > end:
            raise SourceError("invalid_validity_window")
        evidence.append(Evidence(identifier, scope, quantity, source, start, end))
    return version, tuple(rules.values()), tuple(evidence)
