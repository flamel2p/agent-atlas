"""Immutable run-scoped domain values and the JSON report boundary.

A scope identifies the exact assertion being checked, including its baseline.
A quantity keeps its dimension beside its Decimal value. Frozen records and
nested tuples prevent a caller from changing a completed report in place.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

Unit = Literal["count", "milliseconds", "relative_percent", "percentage_point"]
Verdict = Literal["confirmed", "mostly_true", "contradicted", "unverified"]
Domain = Literal["signed", "nonnegative", "nonnegative_integer", "percentage_point"]


class VerificationError(Exception):
    """A stable public error code; never includes rejected values or file paths."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class InputError(VerificationError):
    """The document, claim domain, or request file is invalid."""


class SourceError(VerificationError):
    """The fixed package snapshot is unavailable or violates its schema."""


def decimal_text(value: Decimal) -> str:
    """Render exact normalized decimals without consulting ambient precision."""
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


@dataclass(frozen=True, slots=True)
class Scope:
    """Exact evidence key; no entity, unit, period, or baseline is inferred."""

    entity: str
    metric: str
    period: str
    baseline_period: str | None

    def as_dict(self) -> dict:
        return {
            "entity": self.entity, "metric": self.metric,
            "period": self.period, "baseline_period": self.baseline_period,
        }


@dataclass(frozen=True, slots=True)
class Quantity:
    value: Decimal
    unit: Unit

    def as_dict(self) -> dict:
        return {"value": decimal_text(self.value), "unit": self.unit}


@dataclass(frozen=True, slots=True)
class Claim:
    id: str
    scope: Scope
    quantity: Quantity

    def as_dict(self) -> dict:
        return {"id": self.id, **self.scope.as_dict(), **self.quantity.as_dict()}


@dataclass(frozen=True, slots=True)
class MetricRule:
    """Host policy for a metric; baseline mode also defines change vs level."""

    metric: str
    unit: Unit
    baseline: Literal["required", "none"]
    tolerance: Decimal
    domain: Domain


@dataclass(frozen=True, slots=True)
class Evidence:
    """Synthetic observation with inclusive eligibility and a provenance label.

    Provenance identifies the supplied source label, not its real-world accuracy.
    No record receives priority over another eligible record.
    """

    id: str
    scope: Scope
    quantity: Quantity
    source: str
    valid_from: date
    valid_through: date

    def as_dict(self) -> dict:
        return {
            "id": self.id, **self.scope.as_dict(), **self.quantity.as_dict(),
            "source": self.source, "valid_from": self.valid_from.isoformat(),
            "valid_through": self.valid_through.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ExcludedEvidence:
    evidence: Evidence
    reason: Literal["expired", "not_yet_valid"]

    def as_dict(self) -> dict:
        return {"evidence": self.evidence.as_dict(), "reason": self.reason}


@dataclass(frozen=True, slots=True)
class Result:
    """One ordered claim result; absence of an expected value is explicit null."""

    claim: Claim
    verdict: Verdict
    reason: str
    eligible_evidence: tuple[Evidence, ...] = ()
    excluded_evidence: tuple[ExcludedEvidence, ...] = ()
    expected_value: Decimal | None = None
    difference: Decimal | None = None
    applied_tolerance: Decimal | None = None

    def as_dict(self) -> dict:
        return {
            "claim": self.claim.as_dict(), "verdict": self.verdict,
            "reason": self.reason,
            "eligible_evidence": [item.as_dict() for item in self.eligible_evidence],
            "excluded_evidence": [item.as_dict() for item in self.excluded_evidence],
            "expected_value": None if self.expected_value is None else decimal_text(self.expected_value),
            "difference": None if self.difference is None else decimal_text(self.difference),
            "applied_tolerance": None if self.applied_tolerance is None else decimal_text(self.applied_tolerance),
        }


@dataclass(frozen=True, slots=True)
class Report:
    snapshot_version: str
    snapshot_sha256: str
    as_of: date
    results: tuple[Result, ...]

    @property
    def review_required(self) -> bool:
        return any(result.verdict != "confirmed" for result in self.results)

    def as_dict(self) -> dict:
        return {
            "snapshot_version": self.snapshot_version,
            "snapshot_sha256": self.snapshot_sha256, "as_of": self.as_of.isoformat(),
            "results": [result.as_dict() for result in self.results],
            "review_required": self.review_required,
        }
