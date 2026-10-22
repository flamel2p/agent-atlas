"""Deterministic proposal, feedback-directed repair, and run-owned history.

The two analogy cards describe heuristics, not retrieved scientific evidence.
After an independent-start baseline fails, each repair scan uses the current
candidate's violations to select eligible tasks. It tests one-task neighbors
and selects a strict improvement.
No persistent learning, random escape, or global search occurs.
"""

from dataclasses import dataclass
from hashlib import sha256

from .domain import (
    Attempt, Candidate, Decomposition, Evaluation, Problem, Report, ResourceGroup,
    TaskWindow, Violation, evaluate, parse_document,
)


@dataclass(frozen=True, slots=True)
class StrategyCard:
    id: str
    analogy_label: str


INDEPENDENT_STARTS = StrategyCard("independent_starts", "Independent workstations start when ready")
BOTTLENECK_REPAIR = StrategyCard("bottleneck_repair", "Move a contributor away from a bottleneck")


def _decompose(problem: Problem) -> Decomposition:
    return Decomposition(
        tuple(
            TaskWindow(task.id, task.earliest_start, task.latest_finish, task.duration)
            for task in problem.tasks
        ),
        tuple(sorted((predecessor, task.id) for task in problem.tasks for predecessor in task.after)),
        tuple(
            ResourceGroup(resource.id, resource.capacity, tuple(
                task.id for task in problem.tasks
                if any(key == resource.id for key, _ in task.requires)
            ))
            for resource in problem.resources
        ),
    )


def _attempt(
    card: StrategyCard, triggering: tuple[Violation, ...], evaluation: Evaluation, consumed: int,
) -> Attempt:
    return Attempt(card.id, card.analogy_label, "illustrative_heuristic", triggering, evaluation, consumed)


def solve_document(document: bytes) -> Report:
    """Return immutable evidence for a bounded puzzle, or raise InputError.

    Iterations count selected proposals. Evaluations count every tested schedule,
    including rejected neighbors and scans that produce no recorded proposal.
    Feasibility always takes precedence when the final permitted test succeeds.
    """
    problem = parse_document(document)
    current = evaluate(problem, Candidate(tuple(
        min(task.earliest_start, problem.horizon - task.duration) for task in problem.tasks
    )))
    evaluations = 1
    history = [_attempt(INDEPENDENT_STARTS, (), current, 1)]
    reason = "feasible"

    while not current.feasible:
        if len(history) >= problem.budget.iterations:
            reason = "iteration_limit"
            break
        if evaluations >= problem.budget.evaluations:
            reason = "evaluation_limit"
            break

        implicated = {key for violation in current.violations for key in violation.task_ids}
        best = current
        scan_evaluations = 0
        exhausted = False
        for index, task in enumerate(problem.tasks):
            if task.id not in implicated:
                continue
            for start in range(problem.horizon - task.duration + 1):
                if start == current.candidate.starts[index]:
                    continue
                if evaluations >= problem.budget.evaluations:
                    exhausted = True
                    break
                starts = current.candidate.starts[:index] + (start,) + current.candidate.starts[index + 1:]
                neighbor = evaluate(problem, Candidate(starts))
                evaluations += 1
                scan_evaluations += 1
                if neighbor.feasible:
                    best = neighbor
                    break
                # Equal current scores never qualify. Equal improved scores use
                # the full starts tuple, independent of enumeration order.
                if (
                    neighbor.score < current.score
                    and (neighbor.score, starts) < (best.score, best.candidate.starts)
                ):
                    best = neighbor
            if exhausted or best.feasible:
                break

        improved = best is not current
        if improved:
            history.append(_attempt(BOTTLENECK_REPAIR, current.violations, best, scan_evaluations))
            current = best
        if current.feasible:
            reason = "feasible"
            break
        # An incomplete scan cannot establish a local minimum. Preserve any
        # improvement already evaluated before reporting its budget stop.
        if exhausted:
            reason = "evaluation_limit"
            break
        if not improved:
            reason = "local_minimum"
            break

    return Report(
        "solved" if current.feasible else "unsolved", reason, sha256(document).hexdigest(),
        _decompose(problem), tuple(history), len(history), evaluations, current,
    )
