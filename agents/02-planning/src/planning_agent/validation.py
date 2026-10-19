from typing import Any

from pydantic import ValidationError

from .contracts import Failure, Plan, PlannedTask, TASKS, WORKERS


def unavailable_tasks(availability: dict[str, bool], completed: set[str]) -> list[str]:
    return sorted(task_id for task_id, task in TASKS.items() if task_id not in completed
                  and not any(availability[worker] and capability == task.capability
                              for worker, capability in WORKERS.items()))


def validate_plan(raw: Any, availability: dict[str, bool],
                  fixed: dict[str, PlannedTask] | None = None) -> Plan:
    fixed = fixed or {}
    try:
        plan = Plan.model_validate(raw.model_dump() if isinstance(raw, Plan) else raw)
    except (ValidationError, TypeError, ValueError):
        raise Failure("invalid_plan") from None
    if plan.status == "blocked":
        if plan.tasks or not unavailable_tasks(availability, set(fixed)):
            raise Failure("invalid_plan")
        return plan
    by_id = {task.id: task for task in plan.tasks}
    if len(plan.tasks) != 6 or set(by_id) != set(TASKS):
        raise Failure("invalid_plan")
    for task in plan.tasks:
        if (len(set(task.depends_on)) != len(task.depends_on)
                or task.id in task.depends_on
                or WORKERS[task.worker] != TASKS[task.id].capability
                or (task.id not in fixed and not availability[task.worker])
                or (task.id in fixed and task != fixed[task.id])):
            raise Failure("invalid_plan")
    ancestors: dict[str, set[str]] = {}
    visiting: set[str] = set()

    def walk(task_id: str) -> set[str]:
        if task_id in visiting:
            raise Failure("invalid_plan")
        if task_id in ancestors:
            return ancestors[task_id]
        visiting.add(task_id)
        result = set(by_id[task_id].depends_on)
        for dependency in by_id[task_id].depends_on:
            result.update(walk(dependency))
        visiting.remove(task_id)
        ancestors[task_id] = result
        return result

    for task_id, domain_task in TASKS.items():
        if not set(domain_task.prerequisites) <= walk(task_id):
            raise Failure("invalid_plan")
    return plan
