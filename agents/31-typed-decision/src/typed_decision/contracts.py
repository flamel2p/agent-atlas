"""Request snapshots, host policy, and strict synthetic probability semantics.

A distribution assigns one number to every caller label. Provenance names how
those numbers were obtained; here they are hand-authored synthetic fixture
values. It provides no evidence of predictive accuracy or calibration.
"""

from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from types import MappingProxyType
from typing import Literal, Mapping

from .json_boundary import Invalid, MAX_BYTES, dumps, number

BACKEND = "fixed-fixture-v1"
MODE = "fixture"
PROVENANCE = "synthetic-hand-authored;not-model-probabilities"
MASS_TOLERANCE = Fraction(1, 1_000_000_000)
Status = Literal["decision", "abstention", "invalid_input", "invalid_output",
                 "backend_failure", "timeout", "cancellation"]


def fields(value: object, expected: set[str]) -> dict:
    if type(value) is not dict or set(value) != expected:
        raise Invalid("invalid_fields")
    return value


def text(value: object, maximum: int) -> str:
    if type(value) is not str or not value.strip():
        raise Invalid("invalid_text")
    try:
        if len(value.encode("utf-8")) > maximum or "\x00" in value:
            raise Invalid("text_limit")
    except UnicodeError:
        raise Invalid("invalid_text") from None
    return value


def numeric(value: object) -> Decimal:
    if type(value) not in (int, float, Decimal):
        raise Invalid("invalid_number")
    try:
        return number(str(value))
    except (ValueError, OverflowError):
        raise Invalid("invalid_number") from None


@dataclass(frozen=True)
class Request:
    """Validated immutable request, owned only by one invocation."""

    request_id: str
    state: str
    question: str
    labels: tuple[str, ...]

    @classmethod
    def parse(cls, raw: object) -> "Request":
        data = fields(raw, {"request_id", "state", "question", "labels"})
        labels = data["labels"]
        if type(labels) is not list or not 2 <= len(labels) <= 16:
            raise Invalid("invalid_labels")
        checked = tuple(text(label, 64) for label in labels)
        if len(set(checked)) != len(checked):
            raise Invalid("duplicate_labels")
        result = cls(text(data["request_id"], 128), text(data["state"], 32_768),
                     text(data["question"], 4096), checked)
        if len(dumps(result.as_dict()).encode("utf-8")) > MAX_BYTES:
            raise Invalid("json_byte_limit")
        return result

    def as_dict(self) -> dict:
        return {"request_id": self.request_id, "state": self.state,
                "question": self.question, "labels": list(self.labels)}


@dataclass(frozen=True)
class Policy:
    """Host configuration. Request text cannot alter threshold or deadlines."""

    threshold: Decimal = Decimal("0.6")
    timeout_seconds: float = 2.0

    def checked(self) -> "Policy":
        threshold = numeric(self.threshold)
        timeout = numeric(self.timeout_seconds)
        if not 0 <= threshold <= 1 or not Decimal("0.05") <= timeout <= 10:
            raise Invalid("invalid_policy")
        return Policy(threshold, float(timeout))


@dataclass(frozen=True)
class Result:
    """Terminal host result. Only decision may carry a selected label.

    Valid abstentions retain the validated distribution and concentration for
    inspection. Failure states carry neither. attempts counts worker launches.
    The host sets provenance even on failure, identifying the selected mode.
    """

    request_id: str | None
    status: Status
    reason: str
    attempts: int = 0
    selected_label: str | None = None
    probabilities: Mapping[str, Decimal] | None = None
    confidence: Decimal | None = None
    threshold: Decimal | None = None

    def as_dict(self) -> dict:
        return {"request_id": self.request_id, "status": self.status,
                "reason": self.reason, "attempts": self.attempts,
                "selected_label": self.selected_label,
                "probabilities": dict(self.probabilities) if self.probabilities is not None else None,
                "confidence": self.confidence, "threshold": self.threshold,
                "backend": BACKEND, "mode": MODE, "probability_provenance": PROVENANCE}

    def to_json(self) -> str:
        return dumps(self.as_dict())


def _confidence_decimal(value: Fraction) -> Decimal:
    """Preserve terminating fractions exactly; round only repeating decimals.

    A reduced fraction terminates in base ten iff its denominator has only
    factors 2 and 5. Decimal tuple construction bypasses all caller context
    precision, rounding, exponent and trap settings for those exact values.
    Repeating values use a complete host-owned context for reproducible output.
    """
    remainder = value.denominator
    twos = fives = 0
    while remainder % 2 == 0:
        remainder //= 2
        twos += 1
    while remainder % 5 == 0:
        remainder //= 5
        fives += 1
    if remainder == 1:
        scale = max(twos, fives)
        coefficient = abs(value.numerator) * 2 ** (scale - twos) * 5 ** (scale - fives)
        return Decimal((int(value < 0), tuple(map(int, str(coefficient))), -scale))
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN,
                              Emin=-999_999, Emax=999_999, capitals=1,
                              clamp=0, flags=[], traps=[])):
        return Decimal(value.numerator) / Decimal(value.denominator)


def decide(request: Request, raw: object, policy: Policy, *, attempts: int = 1) -> Result:
    """Validate adapter output and apply exact rational host policy once.

    Confidence measures concentration above a uniform allocation, not whether
    the answer is correct. Rational comparisons preserve exact threshold and
    tolerance boundaries. Decimal rendering uses 50 significant digits only
    for nonterminating confidence; no supplied probability is normalized.
    """
    data = fields(raw, {"backend", "mode", "provenance", "selection", "probabilities"})
    if (data["backend"], data["mode"], data["provenance"]) != (BACKEND, MODE, PROVENANCE):
        raise Invalid("invalid_provenance")
    values = data["probabilities"]
    if type(values) is not dict or set(values) != set(request.labels):
        raise Invalid("probability_labels")
    probabilities = {label: numeric(values[label]) for label in request.labels}
    if any(not 0 <= value <= 1 for value in probabilities.values()):
        raise Invalid("probability_range")
    mass = sum((Fraction(p) for p in probabilities.values()), Fraction(0))
    if abs(mass - 1) > MASS_TOLERANCE:
        raise Invalid("probability_mass")
    maximum = max(probabilities.values())
    winners = [label for label, value in probabilities.items() if value == maximum]
    selection = data["selection"]
    # The adapter must report no selection on a tie. The host never uses order.
    if (len(winners) > 1 and selection is not None) or (
            len(winners) == 1 and (type(selection) is not str or selection != winners[0])):
        raise Invalid("inconsistent_selection")
    n = len(probabilities)
    confidence_exact = (Fraction(maximum) - Fraction(1, n)) / (1 - Fraction(1, n))
    confidence = _confidence_decimal(confidence_exact)
    if len(winners) > 1:
        status, reason, label = "abstention", "tied_maximum", None
    elif confidence_exact < Fraction(policy.threshold):
        status, reason, label = "abstention", "below_threshold", None
    else:
        status, reason, label = "decision", "eligible", winners[0]
    return Result(request.request_id, status, reason, attempts, label,
                  MappingProxyType(probabilities), confidence, policy.threshold)
