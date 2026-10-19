from dataclasses import dataclass
from datetime import UTC, datetime
import re
import unicodedata


STYLES = ("concise", "step-by-step", "example-first")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z", re.ASCII)


class Failure(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def validate_name(value: str) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise Failure("invalid_input")
    return value


def validate_query(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 1000
        or any(unicodedata.category(char).startswith("C") for char in value)
    ):
        raise Failure("invalid_input")
    return value


def timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise Failure("invalid_clock")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def validate_timestamp(value: str) -> str:
    try:
        if timestamp(datetime.fromisoformat(value)) != value:
            raise ValueError
    except (TypeError, ValueError, Failure):
        raise Failure("storage_data") from None
    return value


@dataclass(frozen=True)
class Request:
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
