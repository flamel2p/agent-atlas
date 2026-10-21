"""Validate host inputs and define the deterministic workflow policy.

The caller supplies facts and a simulation profile; the host catalogue derives
price and review routing. These immutable values are persisted at submission.
The simulator only reports an outcome for one attempt; it cannot authorize a
review decision or write the database. A state is one durable checkpoint, not
an in-memory worker that continues after the CLI exits.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
import json
import re
from typing import Any


IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z", re.ASCII)
CATALOGUE_SEN = {"keyboard": 25_000, "monitor": 90_000, "laptop": 350_000}
POLICY_VERSION = "equipment-v1"
REVIEWERS = frozenset({"ops-reviewer", "finance-reviewer"})
MAX_FILE_BYTES = 16 * 1024


class State(StrEnum):
    SUBMITTED = "submitted"
    READY = "ready"
    AWAITING_REVIEW = "awaiting_review"
    RETRY_WAIT = "retry_wait"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


TERMINAL = frozenset({State.FULFILLED, State.REJECTED, State.FAILED,
                      State.CANCELLED, State.EXPIRED})


class Profile(StrEnum):
    SUCCESS = "success"
    TRANSIENT_ONCE = "transient_once"
    ALWAYS_TRANSIENT = "always_transient"
    PERMANENT_FAILURE = "permanent_failure"


class InputError(ValueError):
    """A caller-supplied value violates the public command contract."""


def identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        raise InputError(f"{label} must be 1-64 ASCII letters, digits, _ or -")
    return value


def reason(value: str, label: str = "reason") -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise InputError(f"{label} must be nonblank and at most 500 characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise InputError(f"{label} must contain valid Unicode text") from exc
    return value.strip()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise InputError(f"nonfinite JSON number: {value}")


@dataclass(frozen=True, slots=True)
class RequestInput:
    """Normalized immutable business input; caller cannot submit derived policy fields."""

    request_id: str
    requester_id: str
    equipment_code: str
    quantity: int
    justification: str

    @classmethod
    def from_json_bytes(cls, content: bytes) -> RequestInput:
        if len(content) > MAX_FILE_BYTES:
            raise InputError("request file exceeds 16 KiB")
        try:
            raw = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_pairs,
                             parse_constant=_reject_constant)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
            raise InputError("malformed UTF-8 JSON request") from exc
        if not isinstance(raw, dict) or set(raw) != set(cls.__dataclass_fields__):
            raise InputError("request must have exactly the five specified fields")
        request_id = identifier(raw["request_id"], "request_id")
        requester_id = identifier(raw["requester_id"], "requester_id")
        equipment_code = raw["equipment_code"]
        if not isinstance(equipment_code, str) or equipment_code not in CATALOGUE_SEN:
            raise InputError("unsupported equipment_code")
        quantity = raw["quantity"]
        if type(quantity) is not int or not 1 <= quantity <= 5:
            raise InputError("quantity must be an integer from 1 through 5")
        justification = reason(raw["justification"], "justification")
        return cls(request_id, requester_id, equipment_code, quantity, justification)

    def assessment(self) -> tuple[int, bool]:
        total = CATALOGUE_SEN[self.equipment_code] * self.quantity
        return total, total > 100_000 or self.equipment_code == "laptop"

    def fingerprint(self, profile: Profile) -> str:
        return digest({"input": asdict(self), "profile": profile.value})


def digest(value: dict[str, Any]) -> str:
    """Hash a canonical command or submission representation for equality only."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def simulate(profile: Profile, attempt: int) -> str:
    """Return success, transient, or permanent; attempt starts at one and is <=3."""
    if profile == Profile.SUCCESS or profile == Profile.TRANSIENT_ONCE and attempt > 1:
        return "success"
    if profile == Profile.PERMANENT_FAILURE:
        return "permanent"
    return "transient"
