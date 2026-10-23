"""One bounded policy loop and its enforcing simulated dispatch tool.

The controller proposes a redaction. Only the dispatcher may create an Effect,
after evaluating host policy and recording its attempted action. State lives in one
sequential session, with no cross-run replay protection or persistent audit store.
"""

from dataclasses import dataclass, replace
from enum import StrEnum

from .domain import Action, POLICY_VERSION, PUBLISHABLE_FIELDS, Request, SCHEMA_VERSION
from .policy import Finding, evaluate

MAX_ATTEMPTS = 2


class Status(StrEnum):
    COMPLETED = "completed"
    REVIEW = "review_required"


@dataclass(frozen=True)
class Effect:
    """Symbolic receipt only. No real publication or delivery occurs."""

    receipt_id: str
    action: Action


@dataclass(frozen=True)
class Event:
    """In-run ordered evidence, without durability or tamper resistance."""

    sequence: int
    event: str
    attempt: int
    action: Action
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True)
class Attempt:
    allowed: bool
    findings: tuple[Finding, ...]


@dataclass(frozen=True)
class Review:
    owner: str
    findings: tuple[Finding, ...]


@dataclass(frozen=True)
class RunResult:
    schema_version: int
    policy_version: str
    status: Status
    action: Action
    events: tuple[Event, ...]
    effects: tuple[Effect, ...]
    review: Review | None
    error: None = None


def _redact(request: Request) -> Request:
    fields = tuple(field for field in request.action.fields if field in PUBLISHABLE_FIELDS)
    return replace(request, action=replace(request.action, fields=fields))


class SimulatedDispatcher:
    """The only effect boundary, bound to one immutable original request.

    The first call must match the original. A second call can only be its exact
    field redaction after a denial. IDs, action kind, recipient, and group evidence
    cannot change. A successful or exhausted session cannot create another effect.
    Python host code is trusted; private attributes are not a security sandbox.
    """

    def __init__(self, original: Request) -> None:
        self._original = original
        self._attempts = 0
        self._closed = False
        self._events: list[Event] = []
        self._effects: list[Effect] = []

    @property
    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)

    @property
    def effects(self) -> tuple[Effect, ...]:
        return tuple(self._effects)

    def _record(self, event: str, request: Request, findings: tuple[Finding, ...] = ()) -> None:
        self._events.append(Event(len(self._events) + 1, event, self._attempts, request.action, findings))

    def attempt(self, request: Request) -> Attempt:
        """Recheck policy on actual tool input, audit, then optionally create a receipt."""

        self._attempts += 1
        findings = evaluate(request)
        if self._closed or self._attempts > MAX_ATTEMPTS:
            findings += (Finding("HOST-SESSION-1", "session_closed", "this run cannot dispatch another action"),)
        else:
            expected = self._original if self._attempts == 1 else _redact(self._original)
            if request != expected or (self._attempts == 2 and expected == self._original):
                findings += (Finding("HOST-SESSION-2", "context_changed", "only the original and its exact redaction are permitted"),)

        # The attempted proposal and all findings enter the audit before effects.
        # An earlier evaluator's permission object never crosses this boundary.
        self._record("dispatch_attempt", request, findings)
        if not findings:
            self._effects.append(Effect(f"simulated-{request.action.action_id}", request.action))
            self._closed = True
        elif self._attempts >= MAX_ATTEMPTS:
            self._closed = True
        return Attempt(not findings, findings)


def run(request: Request) -> RunResult:
    """Execute at most two audited attempts and one redaction, then stop."""

    dispatcher = SimulatedDispatcher(request)
    current = request
    attempt = dispatcher.attempt(current)
    if not attempt.allowed:
        repaired = _redact(current)
        if repaired != current:
            dispatcher._record("mitigated", repaired)
            current = repaired
            attempt = dispatcher.attempt(current)
    status = Status.COMPLETED if attempt.allowed else Status.REVIEW
    dispatcher._record(status.value, current, attempt.findings)
    review = None if attempt.allowed else Review("synthetic-policy-owner", attempt.findings)
    return RunResult(SCHEMA_VERSION, POLICY_VERSION, status, current.action,
                     dispatcher.events, dispatcher.effects, review)
