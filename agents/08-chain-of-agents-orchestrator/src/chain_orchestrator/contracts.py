"""Immutable handoffs and reports for one synthetic release-evidence run.

The common proposition is literally `works` for a release/feature/environment.
It is fixture data, not an interpretation of sentiment or a release approval.
Provenance identifies the input bytes and record, without establishing truth.
Only the manager owns mutable lifecycle state; all exposed collections are tuples.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class Role(StrEnum):
    RELEASE = "release"
    TESTS = "tests"
    FEEDBACK = "feedback"


class TaskState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class RunStatus(StrEnum):
    COMPLETE = "complete"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class ReviewKind(StrEnum):
    CONTRADICTION = "contradiction"
    NEGATIVE = "negative"
    MISSING_COVERAGE = "missing_coverage"


@dataclass(frozen=True, slots=True)
class Scope:
    release: str
    feature_id: str
    environment: str


@dataclass(frozen=True, slots=True)
class Record:
    role: Role
    source_id: str
    record_id: str
    scope: Scope
    works: bool
    text: str


@dataclass(frozen=True, slots=True)
class Snapshot:
    target_release: str
    environment: str
    sha256: str
    records: tuple[Record, ...]


@dataclass(frozen=True, slots=True)
class Reference:
    source_id: str
    record_id: str
    snapshot_sha256: str


@dataclass(frozen=True, slots=True)
class Claim:
    role: Role
    scope: Scope
    works: bool
    reference: Reference


@dataclass(frozen=True, slots=True)
class Request:
    """One assigned role's immutable scope, records, and accepted feature catalogue.

    Release receives no catalogue. Dependents receive the catalogue only after
    the manager validates the release reply. Raw source text grants no authority.
    """

    run_id: str
    task_id: str
    sender: Literal["manager"]
    recipient: Role
    target_release: str
    environment: str
    snapshot_sha256: str
    records: tuple[Record, ...]
    feature_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Findings:
    claims: tuple[Claim, ...]


@dataclass(frozen=True, slots=True)
class ReleaseFindings:
    feature_ids: tuple[str, ...]
    claims: tuple[Claim, ...]


@dataclass(frozen=True, slots=True)
class Reply:
    run_id: str
    task_id: str
    sender: Role
    recipient: Literal["manager"]
    payload: Findings | ReleaseFindings


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """An unresolved condition, with all supporting claims or missing roles."""

    kind: ReviewKind
    scope: Scope
    claims: tuple[Claim, ...]
    missing_roles: tuple[Role, ...] = ()


@dataclass(frozen=True, slots=True)
class TaskOutcome:
    role: Role
    task_id: str
    state: TaskState
    error: str | None


@dataclass(frozen=True, slots=True)
class Report:
    mode: Literal["fixture"]
    run_id: str
    status: RunStatus
    target_release: str
    environment: str
    snapshot_sha256: str
    tasks: tuple[TaskOutcome, ...]
    accepted: tuple[Reply, ...]
    review_items: tuple[ReviewItem, ...]

