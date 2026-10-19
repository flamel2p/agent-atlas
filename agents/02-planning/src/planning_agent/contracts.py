"""Host-owned vocabulary and strict data shapes for a six-task planning domain.

A plan is a proposal for dependencies and assignments. Durations, capabilities,
execution evidence, and the decision to declare completion remain host facts.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TaskID = Literal["requirements", "examples", "draft", "technical-review", "editorial-review", "package"]
WorkerID = Literal["researcher-a", "researcher-b", "writer", "reviewer-primary", "reviewer-backup", "publisher"]
Capability = Literal["research", "write", "review", "package"]
# A tick measures simulated task duration; it is separate from wall-clock seconds.
Tick = Annotated[int, Field(ge=0, le=30)]


@dataclass(frozen=True)
class Task:
    """Immutable task definition; prerequisites must occur somewhere upstream."""

    workstream: str
    duration: int
    capability: Capability
    prerequisites: tuple[str, ...] = ()


# Planner output can add dependency edges, but cannot redefine this task catalogue.
TASKS = MappingProxyType({
    "requirements": Task("research", 2, "research"),
    "examples": Task("research", 2, "research"),
    "draft": Task("authoring", 2, "write", ("requirements", "examples")),
    "technical-review": Task("review", 1, "review", ("draft",)),
    "editorial-review": Task("review", 1, "review", ("draft",)),
    "package": Task("release", 1, "package", ("technical-review", "editorial-review")),
})
WORKERS = MappingProxyType({
    "researcher-a": "research", "researcher-b": "research", "writer": "write",
    "reviewer-primary": "review", "reviewer-backup": "review", "publisher": "package",
})
MODEL = "gpt-6-luna"
REQUEST_SECONDS = 20.0
MAX_OUTPUT_TOKENS = 2500


# Shared input/proposal/result policy: reject extra keys and coerced field types.
class StrictModel(BaseModel):
    # Strict types prevent coercion; frozen fields still require copying nested
    # lists/dicts before handing state to an untrusted proposal implementation.
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


# A one-shot resource observation triggered by successful completion of a task.
class AvailabilityEvent(StrictModel):
    after_task: TaskID
    worker: WorkerID
    available: bool


# Synthetic input: objective is context, while the host supplies execution rules.
class Scenario(StrictModel):
    objective: Annotated[str, Field(min_length=1, max_length=500)]
    availability: dict[WorkerID, bool]
    deadline: Annotated[int, Field(ge=1, le=30)] = 20
    events: Annotated[list[AvailabilityEvent], Field(max_length=2)] = Field(default_factory=list)
    fail_task: TaskID | None = None

    @model_validator(mode="after")
    def domain_shape(self):
        """Require a full worker snapshot and unambiguous event targets."""

        if not self.objective.strip() or set(self.availability) != set(WORKERS):
            raise ValueError("invalid scenario shape")
        targets = [(event.after_task, event.worker) for event in self.events]
        if len(set(targets)) != len(targets):
            raise ValueError("duplicate event target")
        return self


# depends_on names direct incoming DAG edges; validation checks all ancestors too.
class PlannedTask(StrictModel):
    id: TaskID
    worker: WorkerID
    depends_on: Annotated[list[TaskID], Field(max_length=5)]


# Shape validation alone does not establish a legal graph or a true blocked claim.
class Plan(StrictModel):
    status: Literal["plan", "blocked"]
    tasks: Annotated[list[PlannedTask], Field(max_length=6)]


# The controller additionally checks identity and the exact run-local evidence ID.
class WorkerResult(StrictModel):
    task: TaskID
    worker: WorkerID
    status: Literal["succeeded", "failed"]
    evidence: Annotated[str, Field(min_length=1, max_length=100)] | None


@dataclass(frozen=True)
class Limits:
    """Host ceilings that callers may tighten, never enlarge.

    Planning calls include the initial proposal; batches count scheduling/finish
    cycles, ticks measure simulated progress, and wall_seconds bounds real time.
    """

    max_planning_calls: int = 3
    max_batches: int = 12
    max_ticks: int = 30
    wall_seconds: float = 90.0

    def __post_init__(self):
        if (type(self.max_planning_calls) is not int or not 1 <= self.max_planning_calls <= 3
                or type(self.max_batches) is not int or not 1 <= self.max_batches <= 12
                or type(self.max_ticks) is not int or not 1 <= self.max_ticks <= 30
                or type(self.wall_seconds) not in (int, float) or not 0 < self.wall_seconds <= 90):
            raise ValueError("limits may only tighten host budgets")


REASONS = frozenset({
    "goal_reached", "resources_unavailable", "running_worker_unavailable", "invalid_input",
    "invalid_plan", "invalid_worker_result", "task_failed", "deadline_reached",
    "planning_limit", "batch_limit", "tick_limit", "wall_limit", "provider_timeout",
    "provider_error", "provider_refusal", "provider_incomplete", "provider_malformed",
    "missing_credentials", "missing_live_dependency", "interrupted", "internal_error",
})


class Failure(Exception):
    """Carry only an allowlisted reason code across report/error boundaries."""

    def __init__(self, reason: str):
        self.reason = reason if reason in REASONS else "internal_error"
        super().__init__(self.reason)
