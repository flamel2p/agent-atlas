"""Validated turn inputs and the common JSON result shape.

Names are local namespaces, not authenticated identities. Stable failure codes
cross the CLI boundary; raw storage and provider exception text does not.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
import re
import unicodedata


STYLES = ("concise", "step-by-step", "example-first")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z", re.ASCII)


class Failure(Exception):
    """Carry a safe, machine-readable failure code between host components."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def validate_name(value: str) -> str:
    """Accept a bounded namespace token usable as a user, session, or store name."""
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise Failure("invalid_input")
    return value


def validate_query(value: str) -> str:
    """Bound query context and reject nonprinting Unicode categories."""
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 1000
        or any(unicodedata.category(char).startswith("C") for char in value)
    ):
        raise Failure("invalid_input")
    return value


def timestamp(value: datetime) -> str:
    """Normalize an aware clock value to fixed-width UTC for SQLite ordering."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise Failure("invalid_clock")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def validate_timestamp(value: str) -> str:
    """Reject stored timestamps that do not match the canonical UTC encoding."""
    try:
        if timestamp(datetime.fromisoformat(value)) != value:
            raise ValueError
    except (TypeError, ValueError, Failure):
        raise Failure("storage_data") from None
    return value


@dataclass(frozen=True)
class Request:
    """One operator-supplied turn; only ``remember_style`` authorizes a preference update.

    Construction does not validate input. ``ask`` calls ``validate`` before
    opening state, so invalid requests cannot create or modify a store.
    """

    user: str
    session: str
    query: str
    remember_style: str | None = None
    mode: str = "replay"
    store: str = "demo"

    def validate(self) -> None:
        for value in (self.user, self.session, self.store):
            validate_name(value)
        validate_query(self.query)
        if self.mode not in ("replay", "live") or (
            self.remember_style is not None and self.remember_style not in STYLES
        ):
            raise Failure("invalid_input")


def terminal(status: str, mode: str, *, code: str | None = None) -> dict:
    """Start a result with no recalled data, answer, or claimed memory commit."""
    return {
        "status": status,
        "failure_code": code,
        "mode": mode,
        "evidence": [],
        "preference": None,
        "recalled_episodes": [],
        "trace": [],
        "answer": None,
        "memory_committed": False,
    }
