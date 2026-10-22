"""Immutable scheduling records, strict JSON boundary, and independent evaluator.

Parsing owns all external validation. Records contain only immutable values and
belong to a single solve call. Candidate starts use the sorted Problem.tasks
order. The evaluator checks supplied starts without consulting any strategy.
Intervals are half-open, so a finish and a start at the same tick do not overlap.
"""

from dataclasses import dataclass
import json
import re
from typing import Literal

MAX_DOCUMENT_BYTES = 65_536
_ID = re.compile(r"[a-z][a-z0-9_-]{0,31}")


class InputError(ValueError):
    """The supplied document violates the bounded input contract."""


@dataclass(frozen=True, slots=True)
class Resource:
    id: str
    capacity: int


@dataclass(frozen=True, slots=True)
class Task:
    """One task's constraints. Requirements are sorted resource/demand pairs."""

    id: str
    duration: int
    earliest_start: int
    latest_finish: int
    requires: tuple[tuple[str, int], ...]
    after: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Budget:
    iterations: int
    evaluations: int


@dataclass(frozen=True, slots=True)
class Problem:
    horizon: int
    resources: tuple[Resource, ...]
    tasks: tuple[Task, ...]
    budget: Budget


@dataclass(frozen=True, slots=True)
class Candidate:
    """A complete start tuple in task-ID order, with each task inside the horizon."""

    starts: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Violation:
    """A failed constraint with positive excess and all implicated task IDs.

Window and dependency excesses are ticks. Capacity excesses are demand units at
one tick. Their sum guides search and has no confidence or optimality meaning.
"""

    kind: Literal["window_start", "window_finish", "dependency", "capacity"]
    task_ids: tuple[str, ...]
    excess: int
    resource_id: str | None = None
    tick: int | None = None


@dataclass(frozen=True, slots=True)
class Evaluation:
    candidate: Candidate
    violations: tuple[Violation, ...]
    score: int

    @property
    def feasible(self) -> bool:
        return not self.violations


@dataclass(frozen=True, slots=True)
class TaskWindow:
    task_id: str
    earliest_start: int
    latest_finish: int
    duration: int


@dataclass(frozen=True, slots=True)
class ResourceGroup:
    resource_id: str
    capacity: int
    task_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Decomposition:
    windows: tuple[TaskWindow, ...]
    dependencies: tuple[tuple[str, str], ...]
    resource_groups: tuple[ResourceGroup, ...]


@dataclass(frozen=True, slots=True)
class Attempt:
    """A selected proposal and its feedback, excluding rejected neighbors.

evaluations_consumed includes the entire scan that selected this revision.
Scans without a revision appear only in Report.evaluations.
"""

    strategy_id: str
    analogy_label: str
    analogy_kind: Literal["illustrative_heuristic"]
    triggering_violations: tuple[Violation, ...]
    evaluation: Evaluation
    evaluations_consumed: int


@dataclass(frozen=True, slots=True)
class Report:
    """Run-owned evidence. An unsolved best evaluation remains a failed candidate."""

    status: Literal["solved", "unsolved"]
    stop_reason: Literal["feasible", "iteration_limit", "evaluation_limit", "local_minimum"]
    input_sha256: str
    decomposition: Decomposition
    history: tuple[Attempt, ...]
    iterations: int
    evaluations: int
    best: Evaluation


def _object(value: object, fields: set[str]) -> dict:
    if type(value) is not dict or set(value) != fields:
        # Field names are untrusted too. Never echo an arbitrary key into errors.
        raise InputError("object has missing or unknown fields")
    return value


def _integer(value: object, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise InputError("integer field has an invalid type or is outside its bounds")
    return value


def _identifier(value: object) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise InputError("invalid identifier")
    return value


def _array(value: object, low: int, high: int) -> list:
    if type(value) is not list or not low <= len(value) <= high:
        raise InputError("array has an invalid type or length")
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate object key")
        result[key] = value
    return result


def _reject_number(value: str) -> None:
    raise InputError("only integer JSON numbers are accepted")


def parse_document(document: bytes) -> Problem:
    """Validate JSON and references before returning normalized immutable records."""
    if type(document) is not bytes or len(document) > MAX_DOCUMENT_BYTES:
        raise InputError("input must be bytes within the 65536-byte limit")
    try:
        value = json.loads(
            document.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except (ValueError, UnicodeError, RecursionError):
        raise InputError("invalid UTF-8 JSON document") from None

    root = _object(value, {"horizon", "resources", "tasks", "budget"})
    horizon = _integer(root["horizon"], 1, 24)
    resources = []
    for value in _array(root["resources"], 1, 4):
        item = _object(value, {"id", "capacity"})
        resources.append(Resource(_identifier(item["id"]), _integer(item["capacity"], 1, 8)))
    resource_ids = {resource.id for resource in resources}
    if len(resource_ids) != len(resources):
        raise InputError("resource IDs must be unique")

    tasks = []
    for value in _array(root["tasks"], 1, 8):
        item = _object(value, {"id", "duration", "earliest_start", "latest_finish", "requires", "after"})
        earliest = _integer(item["earliest_start"], 0, horizon - 1)
        latest = _integer(item["latest_finish"], earliest + 1, horizon)
        requirements = item["requires"]
        if type(requirements) is not dict or len(requirements) > len(resources):
            raise InputError("invalid resource requirements")
        requires = tuple(sorted(
            (_identifier(key), _integer(demand, 1, 8)) for key, demand in requirements.items()
        ))
        if any(key not in resource_ids for key, _ in requires):
            raise InputError("unknown required resource")
        after = tuple(sorted(_identifier(key) for key in _array(item["after"], 0, 7)))
        if len(set(after)) != len(after):
            raise InputError("duplicate dependency")
        tasks.append(Task(
            _identifier(item["id"]), _integer(item["duration"], 1, horizon),
            earliest, latest, requires, after,
        ))

    by_id = {task.id: task for task in tasks}
    if len(by_id) != len(tasks):
        raise InputError("task IDs must be unique")
    for task in tasks:
        if any(key not in by_id or key == task.id for key in task.after):
            raise InputError("unknown or self dependency")
    # Acyclic means no task ultimately depends on itself. At most eight nodes
    # keep this validation bounded independently of the controller's budgets.
    done: set[str] = set()
    while len(done) < len(tasks):
        ready = {task.id for task in tasks if task.id not in done and set(task.after) <= done}
        if not ready:
            raise InputError("dependency cycle")
        done.update(ready)

    budget = _object(root["budget"], {"iterations", "evaluations"})
    return Problem(
        horizon,
        tuple(sorted(resources, key=lambda resource: resource.id)),
        tuple(sorted(tasks, key=lambda task: task.id)),
        Budget(_integer(budget["iterations"], 1, 16), _integer(budget["evaluations"], 1, 1024)),
    )


def evaluate(problem: Problem, candidate: Candidate) -> Evaluation:
    """Check every constraint directly; proposals have no acceptance authority.

Inputs are internal records from parsing and construction. Each resource/tick
violation includes every active positive-demand contributor, allowing feedback
to identify repair candidates without depending on proposal logic.
"""
    starts = dict(zip((task.id for task in problem.tasks), candidate.starts, strict=True))
    finishes = {task.id: starts[task.id] + task.duration for task in problem.tasks}
    violations = []
    for task in problem.tasks:
        start, finish = starts[task.id], finishes[task.id]
        if start < task.earliest_start:
            violations.append(Violation("window_start", (task.id,), task.earliest_start - start))
        if finish > task.latest_finish:
            violations.append(Violation("window_finish", (task.id,), finish - task.latest_finish))
        for predecessor in task.after:
            if finishes[predecessor] > start:
                violations.append(Violation(
                    "dependency", (predecessor, task.id), finishes[predecessor] - start,
                ))
    for resource in problem.resources:
        demands = [
            (task.id, demand) for task in problem.tasks
            for key, demand in task.requires if key == resource.id
        ]
        for tick in range(problem.horizon):
            active = [(key, demand) for key, demand in demands if starts[key] <= tick < finishes[key]]
            excess = sum(demand for _, demand in active) - resource.capacity
            if excess > 0:
                violations.append(Violation(
                    "capacity", tuple(key for key, _ in active), excess, resource.id, tick,
                ))
    return Evaluation(candidate, tuple(violations), sum(violation.excess for violation in violations))
