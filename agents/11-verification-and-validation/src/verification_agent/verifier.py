"""One bounded verification operation over a fixed package-owned snapshot.

All records are indexed by full scope in a multimap. Date eligibility separates
current observations from auditable exclusions. Conflicts precede tolerance,
and signed direction precedes numeric agreement. No model proposes authority.
"""

from collections import defaultdict
from datetime import date
from decimal import Context, DivisionByZero, InvalidOperation, Overflow, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
from pathlib import Path

from .domain import Claim, Evidence, ExcludedEvidence, InputError, MetricRule, Report, Result, Scope, SourceError
from .files import SNAPSHOT_LIMIT, read_regular
from .schema import parse_request, parse_snapshot, validate_metric

_SNAPSHOT_PATH = Path(__file__).parent / "data" / "truth-v1.json"


def _check(claim: Claim, rule: MetricRule | None, records: tuple[Evidence, ...], as_of: date) -> Result:
    if rule is None:
        return Result(claim, "unverified", "unknown_metric")
    if claim.quantity.unit != rule.unit:
        return Result(claim, "unverified", "unit_mismatch")
    if not records:
        return Result(claim, "unverified", "missing_evidence")
    eligible, excluded = [], []
    for record in records:
        if as_of < record.valid_from:
            excluded.append(ExcludedEvidence(record, "not_yet_valid"))
        elif as_of > record.valid_through:
            excluded.append(ExcludedEvidence(record, "expired"))
        else:
            eligible.append(record)
    details = {"eligible_evidence": tuple(eligible), "excluded_evidence": tuple(excluded)}
    if not eligible:
        return Result(claim, "unverified", "no_current_evidence", **details)
    expected = eligible[0].quantity.value
    # Even close disagreeing observations conflict; tolerance applies to claims only.
    if any(record.quantity.value != expected for record in eligible):
        return Result(claim, "unverified", "conflicting_evidence", **details)
    value = claim.quantity.value
    difference = abs(value - expected)
    details.update(expected_value=expected, difference=difference, applied_tolerance=rule.tolerance)
    if rule.baseline == "required" and value != 0 and expected != 0 and (value < 0) != (expected < 0):
        return Result(claim, "contradicted", "direction_reversed", **details)
    if difference == 0:
        return Result(claim, "confirmed", "exact_match", **details)
    if difference <= rule.tolerance:
        return Result(claim, "mostly_true", "within_tolerance", **details)
    return Result(claim, "contradicted", "outside_tolerance", **details)


def verify_document(document: bytes) -> Report:
    """Return a complete immutable report or raise InputError/SourceError.

    The only filesystem authority is the bundled snapshot path. All request and
    source validation finishes before any claim result is constructed. A fresh
    Decimal context isolates all arithmetic settings and flags from callers.
    """
    # Unspecified Context settings inherit mutable DefaultContext values. Set
    # every knob; these bounds cover the full validated quantity range exactly.
    with localcontext(Context(
        prec=40, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
        capitals=1, clamp=0, flags=[], traps=[InvalidOperation, DivisionByZero, Overflow],
    )):
        as_of, claims = parse_request(document)
        raw_snapshot = read_regular(_SNAPSHOT_PATH, SNAPSHOT_LIMIT, SourceError)
        version, rule_rows, evidence = parse_snapshot(raw_snapshot)
        rules = {rule.metric: rule for rule in rule_rows}
        for claim in claims:
            rule = rules.get(claim.scope.metric)
            if rule is not None:
                validate_metric(claim.scope, claim.quantity, rule, InputError)
        index: dict[Scope, list[Evidence]] = defaultdict(list)
        for record in sorted(evidence, key=lambda item: item.id):
            index[record.scope].append(record)
        results = tuple(_check(claim, rules.get(claim.scope.metric),
                               tuple(index.get(claim.scope, ())), as_of) for claim in claims)
        return Report(version, sha256(raw_snapshot).hexdigest(), as_of, results)
