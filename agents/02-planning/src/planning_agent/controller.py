"""Run the planning agent's observe/propose/validate/execute loop.

The backend only proposes a graph. This controller owns simulated execution,
resource observations, replanning budgets, evidence, and terminal outcomes.
All mutable state belongs to one invocation; the report is not durable memory.
"""

from copy import deepcopy
import queue
import threading
import time
from typing import Any, Callable
from uuid import uuid4

from pydantic import ValidationError

from .backends import ReplayPlanner
from .contracts import Failure, Limits, Plan, PlannedTask, REQUEST_SECONDS, Scenario, TASKS, WorkerResult
from .simulator import Simulator, evidence_id
from .validation import unavailable_tasks, validate_plan


def _bounded_proposal(planner: Any, context: dict[str, Any], budget: float, live: bool) -> Any:
    """Bound host waiting without granting the planner access to mutable run state.

    A daemon thread may outlive a timed-out call, but receives only a deep copy of
    proposal context. This is not thread cancellation; the live backend separately
    bounds its async request lifetime.
    """

    results: queue.Queue = queue.Queue(maxsize=1)
    timeout = min(budget, REQUEST_SECONDS) if live else budget

    def propose():
        try:
            results.put((True, planner.propose(deepcopy(context), timeout=timeout)))
        except BaseException as exc:
            results.put((False, exc))

    threading.Thread(target=propose, daemon=True, name="planning-proposal").start()
    try:
        success, value = results.get(timeout=timeout)
    except queue.Empty:
        raise Failure("provider_timeout" if live and budget > REQUEST_SECONDS else "wall_limit") from None
    if not success:
        raise value
    return value


def run(scenario: Scenario | dict, planner: Any = None, simulator: Any = None, *,
        mode: str = "replay", limits: Limits = Limits(),
        clock: Callable[[], float] = time.monotonic,
        preflight_failure: Failure | None = None) -> dict[str, Any]:
    """Return one bounded, sanitized report for a synthetic documentation release.

    planner, simulator, and clock are local injection seams for focused checks.
    They do not grant the model tools. Only six successful host-validated results
    permit a release artifact; every other terminal outcome leaves it absent.
    """

    report: dict[str, Any] = {
        "status": "failed", "reason": "invalid_input", "mode": mode if mode in ("replay", "live") else "replay",
        "plans": [], "trace": [], "tasks": {task: {"status": "pending", "worker": None,
            "started_at": None, "finished_at": None, "evidence": None} for task in TASKS},
        "elapsed_ticks": 0, "planning_calls": 0, "replans": 0, "batches": 0,
        "release_artifact": None,
    }
    started = clock()
    tick = 0
    run_id = uuid4().hex[:16]
    availability: dict[str, bool] = {}
    completed: set[str] = set()
    running: dict[str, int] = {}  # Task ID -> scheduled finish tick, not a real job.
    plan: Plan | None = None
    applied_events: set[int] = set()
    planner = planner if planner is not None else ReplayPlanner()
    simulator = simulator if simulator is not None else Simulator()

    def trace(event: str, **fields):
        report["trace"].append({"event": event, "tick": tick, **fields})

    def remaining() -> float:
        """Check the real-time budget independently of simulated task progress."""

        seconds = limits.wall_seconds - (clock() - started)
        if seconds <= 0:
            raise Failure("wall_limit")
        return seconds

    def revise():
        """Validate a new proposal before replacing pending graph/worker choices."""

        nonlocal plan
        if report["planning_calls"] >= limits.max_planning_calls:
            raise Failure("planning_limit")
        # Completed history and in-flight work are immutable across revisions.
        fixed: dict[str, PlannedTask] = {} if plan is None else {
            task.id: task for task in plan.tasks if task.id in completed or task.id in running}
        context = {
            "objective": scenario.objective, "availability": dict(availability),
            "deadline": scenario.deadline, "current_tick": tick,
            "fixed_tasks": [task.model_dump() for task in fixed.values()],
            "completed": [{"task": task_id, "evidence": report["tasks"][task_id]["evidence"]}
                          for task_id in sorted(completed)],
            "running": sorted(running), "prior_plan": None if plan is None else plan.model_dump(),
        }
        budget = remaining()
        report["planning_calls"] += 1
        report["replans"] = report["planning_calls"] - 1
        raw = _bounded_proposal(planner, context, budget, mode == "live")
        remaining()
        # A structurally valid model response is still untrusted until this gate.
        proposal = validate_plan(raw, availability, fixed)
        plan = proposal
        report["plans"].append({"revision": report["replans"], "tick": tick, **proposal.model_dump()})
        trace("plan_validated", revision=report["replans"], status=proposal.status)
        if proposal.status == "blocked":
            trace("resource_observation", tasks=unavailable_tasks(availability, completed))
            raise Failure("resources_unavailable")
        for task in proposal.tasks:
            if task.id not in completed and task.id not in running:
                report["tasks"][task.id]["worker"] = task.worker

    try:
        if preflight_failure is not None:
            raise preflight_failure
        if mode not in ("replay", "live") or (mode == "live" and isinstance(planner, ReplayPlanner)):
            raise Failure("invalid_input")
        try:
            scenario = Scenario.model_validate(scenario.model_dump() if isinstance(scenario, Scenario) else scenario)
        except (ValidationError, ValueError, TypeError):
            raise Failure("invalid_input") from None
        availability = dict(scenario.availability)
        revise()
        while len(completed) < len(TASKS):
            remaining()
            if report["batches"] >= limits.max_batches:
                raise Failure("batch_limit")
            report["batches"] += 1
            by_id = {task.id: task for task in plan.tasks}
            busy_workers = {by_id[task_id].worker for task_id in running}
            # Stable ID order makes replay inspectable. Global capacity is two;
            # each worker can serve one task, even when multiple tasks are ready.
            for task_id in sorted(TASKS):
                task = by_id[task_id]
                if (task_id in completed or task_id in running or len(running) >= 2
                        or not set(task.depends_on) <= completed or task.worker in busy_workers):
                    continue
                if not availability[task.worker]:
                    raise Failure("invalid_plan")
                running[task_id] = tick + TASKS[task_id].duration
                busy_workers.add(task.worker)
                report["tasks"][task_id].update(status="running", started_at=tick)
                trace("task_started", task=task_id, worker=task.worker)
            if not running:
                raise Failure("invalid_plan")
            # Event-driven simulation jumps to a finish, without sleeping per tick.
            # Equality is allowed: finishing exactly at the deadline is on time.
            next_tick = min(running.values())
            if next_tick > min(scenario.deadline, limits.max_ticks):
                tick = min(scenario.deadline, limits.max_ticks)
                raise Failure("deadline_reached" if scenario.deadline <= limits.max_ticks else "tick_limit")
            tick = next_tick
            finished = sorted(task_id for task_id, finish in running.items() if finish == tick)
            for task_id in finished:
                remaining()
                task = by_id[task_id]
                raw = simulator.finish(task_id, task.worker, run_id, scenario.fail_task)
                remaining()
                try:
                    result = WorkerResult.model_validate(raw.model_dump() if isinstance(raw, WorkerResult) else raw)
                except (ValidationError, TypeError, ValueError):
                    raise Failure("invalid_worker_result") from None
                # Evidence must belong to this exact task/run, not a planner claim
                # or a successful-looking result copied from another invocation.
                if (result.task != task_id or result.worker != task.worker
                        or (result.status == "succeeded" and result.evidence != evidence_id(run_id, task_id))
                        or (result.status == "failed" and result.evidence is not None)):
                    raise Failure("invalid_worker_result")
                del running[task_id]
                report["tasks"][task_id].update(status=result.status, finished_at=tick, evidence=result.evidence)
                trace("task_succeeded" if result.status == "succeeded" else "task_failed", task=task_id, worker=task.worker)
                if result.status == "failed":
                    raise Failure("task_failed")
                completed.add(task_id)
            # Observe availability after this finish batch and before starting new
            # work. Applied indices make each scenario event fire only once.
            changed = False
            for index, event in enumerate(scenario.events):
                if index not in applied_events and event.after_task in completed:
                    applied_events.add(index)
                    availability[event.worker] = event.available
                    changed = True
                    trace("availability_changed", worker=event.worker, available=event.available)
            if changed:
                if any(not availability[by_id[task_id].worker] for task_id in running):
                    raise Failure("running_worker_unavailable")
                pending = [task for task in plan.tasks if task.id not in completed and task.id not in running]
                if any(not availability[task.worker] for task in pending):
                    trace("resource_observation", tasks=unavailable_tasks(availability, completed))
                    if unavailable_tasks(availability, completed):
                        raise Failure("resources_unavailable")
                    revise()
        remaining()
        # This is the sole success gate; the artifact is an in-memory evidence map.
        report["status"], report["reason"] = "completed", "goal_reached"
        report["release_artifact"] = {"id": f"release-{run_id}", "evidence": {
            task_id: report["tasks"][task_id]["evidence"] for task_id in sorted(completed)}}
    except KeyboardInterrupt:
        report["status"], report["reason"] = "cancelled", "interrupted"
    except Failure as exc:
        report["reason"] = exc.reason
        if exc.reason == "interrupted":
            report["status"] = "cancelled"
        elif exc.reason in ("resources_unavailable", "running_worker_unavailable"):
            report["status"] = "blocked"
        elif exc.reason in ("planning_limit", "batch_limit", "tick_limit", "wall_limit", "provider_timeout", "deadline_reached"):
            report["status"] = "limit_reached"
        else:
            report["status"] = "failed"
    except Exception:
        report["status"], report["reason"] = "failed", "internal_error"
    if report["status"] != "completed":
        # Preserve completed evidence, but never imply unfinished work succeeded
        # or that stopping a simulation rolled back any real-world operation.
        report["release_artifact"] = None
        for task in report["tasks"].values():
            if task["status"] == "running":
                task["status"] = "unfinished"
    report["elapsed_ticks"] = tick
    trace("run_finished", status=report["status"], reason=report["reason"])
    return report
