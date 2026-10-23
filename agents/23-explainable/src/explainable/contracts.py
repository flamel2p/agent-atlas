"""Immutable domain values shared by the policy and explanation release gate.

A trace is a run-scoped tuple of observations and actual policy events. It is
execution evidence for this program, not authenticated real-world evidence or
access to a model's internal reasoning. Claims reference those event IDs.
Frozen dataclasses and tuples prevent normal renderer code from editing history.
"""

from dataclasses import dataclass, field
from typing import Literal

type Priority = Literal["urgent", "high", "routine"]
type Audience = Literal["user", "engineer", "auditor"]
type EvidenceName = Literal["outage", "blocked_users", "due_hours"]
type RunStatus = Literal["completed", "needs_review"]
type ExplanationStatus = Literal["complete", "incomplete", "unavailable"]

AUDIENCES: tuple[Audience, ...] = ("user", "engineer", "auditor")
EVIDENCE_NAMES: tuple[EvidenceName, ...] = ("outage", "blocked_users", "due_hours")


class ContractError(ValueError):
    """Expose only a stable failure code, never untrusted content or secrets."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Evidence:
    """Validated observations. None means missing, never false or zero."""

    outage: bool | None
    blocked_users: int | None
    due_hours: int | None


@dataclass(frozen=True)
class CompleteEvidence:
    """The policy evaluates only after every required observation is present."""

    outage: bool
    blocked_users: int
    due_hours: int


@dataclass(frozen=True)
class Request:
    task_id: str
    evidence: Evidence


@dataclass(frozen=True)
class EvidenceEvent:
    event_id: str
    name: EvidenceName
    value: bool | int | None
    availability: Literal["present", "missing"]
    kind: Literal["evidence"] = field(default="evidence", init=False)


@dataclass(frozen=True)
class RuleEvent:
    """An actual predicate evaluation and the evidence it read.

    More than one rule can match. Event order defines first-match precedence.
    A matched lower-priority rule is not an alternative decision.
    """

    event_id: str
    rule_id: str
    matched: bool
    priority: Priority
    evidence_ids: tuple[str, ...]
    kind: Literal["rule"] = field(default="rule", init=False)


@dataclass(frozen=True)
class FinalEvent:
    """The policy result, retained even when a later explanation is withheld."""

    event_id: str
    status: RunStatus
    decision: Priority | None
    selected_rule: str | None
    evidence_ids: tuple[str, ...]
    kind: Literal["final"] = field(default="final", init=False)


type Event = EvidenceEvent | RuleEvent | FinalEvent


@dataclass(frozen=True)
class Trace:
    """One policy execution. Digest is corruption detection, not a signature."""

    schema_version: int
    policy_version: str
    task_id: str
    events: tuple[Event, ...]
    digest: str


@dataclass(frozen=True)
class Claim:
    """One template statement backed by nonempty IDs in the same trace."""

    text: str
    event_ids: tuple[str, ...]


@dataclass(frozen=True)
class Explanation:
    audience: Audience
    status: Literal["complete", "incomplete"]
    decision: Priority | None
    claims: tuple[Claim, ...]


@dataclass(frozen=True)
class Outcome:
    """Only decision at this level is released for use by the caller.

    A trace may retain a historical policy selection while decision is None.
    Callers must inspect status, not treat historical events as authorization.
    """

    status: RunStatus
    decision: Priority | None
    explanation_status: ExplanationStatus
    explanations: tuple[Explanation, ...]
    trace: Trace | None
    issues: tuple[str, ...]
