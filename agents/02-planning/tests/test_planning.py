from copy import deepcopy
import json
import threading
import time

import pytest

from planning_agent.backends import ReplayPlanner
from planning_agent.contracts import Failure, Limits, Plan, TASKS, WORKERS
from planning_agent.controller import run
from planning_agent.fixtures import load_example
from planning_agent.simulator import Simulator
from planning_agent.validation import validate_plan


def baseline():
    return ReplayPlanner().propose({"fixed_tasks": [], "availability": dict.fromkeys(WORKERS, True)}, timeout=1).model_dump()


class Proposals:
    def __init__(self, values):
        self.values = iter(values)
        self.contexts = []

    def propose(self, context, *, timeout):
        self.contexts.append(deepcopy(context))
        value = next(self.values)
        if isinstance(value, BaseException):
            raise value
        return value(context) if callable(value) else value


def assert_no_release(report, status, reason):
    assert report["status"] == status
    assert report["reason"] == reason
    assert report["release_artifact"] is None
    assert report["trace"][-1]["event"] == "run_finished"


def assert_schedule(report):
    tasks = report["tasks"]
    for task_id, task in tasks.items():
        if task["status"] != "succeeded":
            continue
        assert task["finished_at"] - task["started_at"] == TASKS[task_id].duration
        for prerequisite in TASKS[task_id].prerequisites:
            assert tasks[prerequisite]["finished_at"] <= task["started_at"]
    for tick in range(report["elapsed_ticks"]):
        active = [task for task in tasks.values() if task["started_at"] is not None
                  and task["finished_at"] is not None and task["started_at"] <= tick < task["finished_at"]]
        assert len(active) <= 2
        assert len({task["worker"] for task in active}) == len(active)


def test_normal_parallel_release_evidence():
    report = run(load_example("normal"))
    assert report["status"] == "completed"
    assert report["elapsed_ticks"] == 6
    assert report["planning_calls"] == 1
    assert report["replans"] == 0
    assert all(task["status"] == "succeeded" for task in report["tasks"].values())
    assert report["tasks"]["requirements"]["started_at"] == report["tasks"]["examples"]["started_at"] == 0
    assert report["tasks"]["technical-review"]["started_at"] == report["tasks"]["editorial-review"]["started_at"] == 4
    assert report["release_artifact"]["evidence"] == {key: value["evidence"] for key, value in report["tasks"].items()}
    assert_schedule(report)


def test_departure_replans_preserving_completed_and_capacity():
    report = run(load_example("reviewer-unavailable"))
    assert report["status"] == "completed"
    assert report["elapsed_ticks"] == 7
    assert report["planning_calls"] == 2 and report["replans"] == 1
    old, new = ({task["id"]: task for task in plan["tasks"]} for plan in report["plans"])
    for task_id in ("requirements", "examples", "draft"):
        assert old[task_id] == new[task_id]
        assert sum(item["event"] == "task_started" and item.get("task") == task_id for item in report["trace"]) == 1
    assert new["technical-review"]["worker"] == new["editorial-review"]["worker"] == "reviewer-backup"
    assert_schedule(report)


def test_unavailable_reviewers_observed_after_completed_draft():
    report = run(load_example("no-reviewer"))
    assert_no_release(report, "blocked", "resources_unavailable")
    assert report["tasks"]["draft"]["status"] == "succeeded"
    assert report["tasks"]["package"]["status"] == "pending"
    assert [event for event in report["trace"] if event["event"] == "resource_observation"][0]["tasks"] == ["editorial-review", "technical-review"]


def mutate(plan, change):
    change(plan)
    return plan


@pytest.mark.parametrize("change", [
    lambda p: p["tasks"].append(p["tasks"][0]),
    lambda p: p["tasks"].pop(),
    lambda p: p["tasks"][0].update(id="unknown"),
    lambda p: p["tasks"][0].update(worker="publisher"),
    lambda p: p["tasks"][0].update(worker="unknown"),
    lambda p: p["tasks"][0].update(depends_on=["unknown"]),
    lambda p: p["tasks"][0].update(depends_on=["requirements"]),
    lambda p: p["tasks"][0].update(depends_on=["package"]),
    lambda p: p["tasks"][2].update(depends_on=["requirements", "requirements", "examples"]),
    lambda p: p["tasks"][2].update(depends_on=["requirements"]),
    lambda p: p["tasks"][3].update(depends_on=[]),
    lambda p: p["tasks"][5].update(depends_on=["draft"]),
    lambda p: p["tasks"][0].update(evidence="fabricated"),
    lambda p: p.update(status="completed"),
    lambda p: p.update(extra="not permitted"),
    lambda p: p.update(status="blocked", tasks=[]),
    lambda p: p.update(status="blocked"),
])
def test_invalid_plans_rejected_before_effect(change):
    report = run(load_example("normal"), planner=Proposals([mutate(baseline(), change)]))
    assert_no_release(report, "failed", "invalid_plan")
    assert not any(event["event"] == "task_started" for event in report["trace"])


def test_unavailable_assignment_rejected_and_true_blocked_accepted():
    scenario = load_example("normal").model_dump()
    scenario["availability"]["reviewer-primary"] = False
    assert_no_release(run(scenario, Proposals([baseline()])), "failed", "invalid_plan")
    scenario["availability"]["reviewer-backup"] = False
    report = run(scenario, Proposals([{"status": "blocked", "tasks": []}]))
    assert_no_release(report, "blocked", "resources_unavailable")
    assert report["plans"][0]["status"] == "blocked"


def test_safe_extra_dependency_and_shared_researcher_schedule():
    plan = baseline()
    plan["tasks"][1].update(worker="researcher-a", depends_on=["requirements"])
    report = run(load_example("normal"), Proposals([plan]))
    assert report["status"] == "completed"
    assert report["elapsed_ticks"] == 8
    assert_schedule(report)


@pytest.mark.parametrize("field,value", [("worker", "researcher-b"), ("depends_on", ["examples"])])
def test_completed_records_cannot_be_revised(field, value):
    def bad_revision(context):
        proposal = ReplayPlanner().propose(context, timeout=1).model_dump()
        next(task for task in proposal["tasks"] if task["id"] == "requirements")[field] = value
        return proposal
    report = run(load_example("reviewer-unavailable"), Proposals([baseline(), bad_revision]))
    assert_no_release(report, "failed", "invalid_plan")
    assert report["tasks"]["requirements"]["status"] == "succeeded"
    assert report["tasks"]["technical-review"]["status"] == "pending"


@pytest.mark.parametrize("change", [
    lambda s: s.update(objective=" "), lambda s: s.update(objective="x" * 501),
    lambda s: s.update(deadline=True), lambda s: s.update(deadline="5"),
    lambda s: s.update(deadline=0), lambda s: s.update(deadline=31),
    lambda s: s.update(unknown="data"), lambda s: s.update(fail_task="unknown"),
    lambda s: s["availability"].update(writer=1),
    lambda s: s["availability"].update(unknown=True),
    lambda s: s["availability"].pop("writer"),
    lambda s: s.update(events=[{"after_task": "unknown", "worker": "writer", "available": False}]),
    lambda s: s.update(events=[{"after_task": "draft", "worker": "writer", "available": 0}]),
    lambda s: s.update(events=[{"after_task": "draft", "worker": "writer", "available": False}] * 3),
    lambda s: s.update(events=[{"after_task": "draft", "worker": "writer", "available": False}] * 2),
])
def test_invalid_scenarios_do_not_obtain_plan(change):
    scenario = load_example("normal").model_dump()
    change(scenario)
    planner = Proposals([])
    report = run(scenario, planner)
    assert_no_release(report, "failed", "invalid_input")
    assert report["planning_calls"] == 0 and planner.contexts == []


@pytest.mark.parametrize("change", [
    lambda result: result.update(task="package"),
    lambda result: result.update(worker="publisher"),
    lambda result: result.update(evidence="forged"),
    lambda result: result.update(status="completed"),
    lambda result: result.update(extra="raw data"),
    lambda result: result.update(status="failed", evidence="invalid failure evidence"),
    lambda result: result.update(evidence=None),
])
def test_invalid_simulator_outputs_fail_without_evidence(change):
    class BadSimulator(Simulator):
        def finish(self, *args):
            result = super().finish(*args).model_dump()
            change(result)
            return result
    report = run(load_example("normal"), simulator=BadSimulator())
    assert_no_release(report, "failed", "invalid_worker_result")
    assert not any(task["evidence"] for task in report["tasks"].values())


def test_task_failure_never_packages_or_retries():
    report = run(load_example("task-failure"))
    assert_no_release(report, "failed", "task_failed")
    assert report["tasks"]["technical-review"]["evidence"] is None
    assert report["tasks"]["package"]["status"] == "pending"
    assert sum(event.get("task") == "technical-review" and event["event"] == "task_started" for event in report["trace"]) == 1


def test_deadline_exact_finish_allowed_and_late_finish_not_completed():
    scenario = load_example("normal").model_dump()
    scenario["deadline"] = 6
    assert run(scenario)["status"] == "completed"
    scenario["deadline"] = 5
    report = run(scenario)
    assert_no_release(report, "limit_reached", "deadline_reached")
    assert report["elapsed_ticks"] == 5
    assert report["tasks"]["package"]["status"] == "unfinished"
    assert report["tasks"]["package"]["finished_at"] is None


@pytest.mark.parametrize("limits,example,reason", [
    (Limits(max_planning_calls=1), "reviewer-unavailable", "planning_limit"),
    (Limits(max_batches=1), "normal", "batch_limit"),
    (Limits(max_ticks=3), "normal", "tick_limit"),
])
def test_budgets_stop_truthfully(limits, example, reason):
    assert_no_release(run(load_example(example), limits=limits), "limit_reached", reason)


def test_total_planning_calls_bounded_with_two_resource_revisions():
    scenario = load_example("normal").model_dump()
    scenario["events"] = [
        {"after_task": "requirements", "worker": "researcher-b", "available": False},
        {"after_task": "draft", "worker": "reviewer-primary", "available": False},
    ]
    initial = baseline()
    initial["tasks"][1]["depends_on"] = ["requirements"]
    planner = Proposals([initial, lambda c: ReplayPlanner().propose(c, timeout=1),
                         lambda c: ReplayPlanner().propose(c, timeout=1)])
    report = run(scenario, planner)
    assert report["status"] == "completed"
    assert report["planning_calls"] == 3 and report["replans"] == 2
    report = run(scenario, Proposals([initial, lambda c: ReplayPlanner().propose(c, timeout=1)]),
                 limits=Limits(max_planning_calls=2))
    assert_no_release(report, "limit_reached", "planning_limit")
    assert report["planning_calls"] == 2


def test_wall_clock_checked_after_proposal_before_effect():
    elapsed = [0.0]
    def proposal(context):
        elapsed[0] = 91.0
        return baseline()
    report = run(load_example("normal"), Proposals([proposal]), clock=lambda: elapsed[0])
    assert_no_release(report, "limit_reached", "wall_limit")
    assert all(task["status"] == "pending" for task in report["tasks"].values())


def test_slow_planner_is_wall_bounded_without_waiting_for_thread():
    release = threading.Event()
    class SlowPlanner:
        def propose(self, context, *, timeout):
            release.wait(2)
            return baseline()
    before = time.monotonic()
    try:
        report = run(load_example("normal"), SlowPlanner(), limits=Limits(wall_seconds=0.03))
        assert time.monotonic() - before < 0.5
        assert_no_release(report, "limit_reached", "wall_limit")
    finally:
        release.set()


@pytest.mark.parametrize("failure,status,reason", [
    (KeyboardInterrupt(), "cancelled", "interrupted"),
    (Failure("provider_timeout"), "limit_reached", "provider_timeout"),
    (RuntimeError("secret exception body"), "failed", "internal_error"),
])
def test_cancellation_and_errors_are_sanitized(failure, status, reason):
    report = run(load_example("normal"), Proposals([failure]))
    assert_no_release(report, status, reason)
    assert "secret" not in json.dumps(report)


def test_pending_worker_removed_revises_before_that_task_starts():
    plan = baseline()
    plan["tasks"][1]["depends_on"] = ["requirements"]
    scenario = load_example("normal").model_dump()
    scenario["events"] = [{"after_task": "requirements", "worker": "researcher-b", "available": False}]
    report = run(scenario, Proposals([plan, lambda c: ReplayPlanner().propose(c, timeout=1)]))
    assert report["status"] == "completed"
    assert report["tasks"]["examples"]["worker"] == "researcher-a"
    assert report["planning_calls"] == 2


def test_run_state_and_evidence_are_isolated():
    first, second = run(load_example("normal")), run(load_example("normal"))
    assert first["release_artifact"]["id"] != second["release_artifact"]["id"]
    assert set(first["release_artifact"]["evidence"].values()).isdisjoint(second["release_artifact"]["evidence"].values())
    first["tasks"]["draft"]["status"] = "modified"
    assert second["tasks"]["draft"]["status"] == "succeeded"


@pytest.mark.parametrize("kwargs", [{"max_planning_calls": 4}, {"max_batches": 13},
    {"max_ticks": 31}, {"wall_seconds": 91}, {"max_ticks": True}, {"wall_seconds": float("nan")}])
def test_limits_cannot_expand_host_authority(kwargs):
    with pytest.raises(ValueError):
        Limits(**kwargs)


def test_running_and_completed_plan_records_are_fixed_by_validator():
    plan = Plan.model_validate(baseline())
    fixed = {task.id: task for task in plan.tasks if task.id in ("requirements", "examples")}
    changed = plan.model_dump()
    changed["tasks"][0]["worker"] = "researcher-b"
    with pytest.raises(Failure, match="invalid_plan"):
        validate_plan(changed, dict.fromkeys(WORKERS, True), fixed)
