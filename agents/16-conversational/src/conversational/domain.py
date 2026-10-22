"""Immutable dialogue records shared by policy, composition, and persistence.

Working context is one session variant plus recent canonical completed turns.
The archived preference is only an explicit lesson style, owned by one user.
No record contains arbitrary user text. Course IDs refer to packaged fixtures.
"""

from dataclasses import asdict, dataclass
from enum import StrEnum
import re
from typing import Literal
import unicodedata

LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}\Z", re.ASCII)
MAX_MESSAGE = 500
MAX_RESPONSE = 1200
HISTORY_LIMIT = 4
SESSION_TURN_LIMIT = 40
USER_LIMIT = 8
USER_SESSION_LIMIT = 4
TOTAL_SESSION_LIMIT = 16
SESSION_TTL = 24 * 60 * 60
PREFERENCE_TTL = 30 * 24 * 60 * 60
BUSY_TIMEOUT = 0.2
DATABASE_BYTES = 2 * 1024 * 1024


class LessonStyle(StrEnum):
    SHORT = "short"
    STANDARD = "standard"


class Detail(StrEnum):
    OVERVIEW = "overview"
    DURATION = "duration"
    PREREQUISITES = "prerequisites"


@dataclass(frozen=True)
class Ready:
    """No focused course or unresolved choice exists in this session."""


@dataclass(frozen=True)
class Choosing:
    """Candidate order and requested detail survive a clarification and restart."""

    candidates: tuple[str, ...]
    detail: Detail


@dataclass(frozen=True)
class Focused:
    course_id: str


@dataclass(frozen=True)
class Closed:
    """A terminal session. Only expiry or explicit user forgetting removes it."""


type SessionState = Ready | Choosing | Focused | Closed


def state_name(state: SessionState) -> str:
    return {Ready: "ready", Choosing: "choosing", Focused: "focused", Closed: "closed"}[type(state)]


@dataclass(frozen=True)
class TurnRequest:
    user_id: str
    session_id: str
    text: str


@dataclass(frozen=True)
class Intent:
    """Gate-approved instruction. Text outside this finite shape never reaches storage."""

    kind: Literal["help", "list", "detail", "choice", "style", "close", "recap"]
    courses: tuple[str, ...] = ()
    detail: Detail = Detail.OVERVIEW
    choice: int | None = None
    style: LessonStyle | None = None
    bare_course: bool = False

    def canonical(self) -> str:
        # The style value is excluded so correcting a preference leaves no old value in history.
        if self.kind == "style":
            return "preference_update"
        return ":".join((self.kind, self.detail.value, ",".join(self.courses), str(self.choice or "")))


@dataclass(frozen=True)
class RecentTurn:
    number: int
    intent: str
    course_id: str | None
    response: str


@dataclass(frozen=True)
class Snapshot:
    state: SessionState
    turn_count: int
    recent: tuple[RecentTurn, ...]
    style: LessonStyle
    preference_stored: bool
    restored: bool


@dataclass(frozen=True)
class ResponsePlan:
    """Policy authorizes a fixed response kind, facts, state, and optional preference write."""

    status: str
    state: SessionState
    kind: str
    course_id: str | None = None
    detail: Detail = Detail.OVERVIEW
    candidates: tuple[str, ...] = ()
    recap: tuple[str, ...] = ()
    save_style: LessonStyle | None = None


@dataclass(frozen=True)
class TurnResult:
    status: str
    response: str
    state: str | None = None
    course_id: str | None = None
    preference_used: str | None = None
    trace: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return asdict(self)


def valid_label(value: object) -> bool:
    return isinstance(value, str) and LABEL.fullmatch(value) is not None


def valid_request(request: TurnRequest) -> bool:
    text = request.text
    return (
        valid_label(request.user_id)
        and valid_label(request.session_id)
        and isinstance(text, str)
        and 0 < len(text) <= MAX_MESSAGE
        and bool(text.strip())
        and not any(unicodedata.category(char).startswith("C") for char in text)
    )


def terminal(status: str, response: str, *trace: str) -> TurnResult:
    return TurnResult(status, response, trace=trace)
