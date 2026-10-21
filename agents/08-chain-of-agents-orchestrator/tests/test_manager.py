"""Fixture and fake-specialist evidence for lifecycle, authority, and synthesis."""

import asyncio
from dataclasses import FrozenInstanceError, asdict, replace
import json
import time

import pytest

from chain_orchestrator import analyze_release
from chain_orchestrator.contracts import (
    Findings, Reference, ReleaseFindings, ReviewKind, Role, RunStatus, TaskState,
)
from chain_orchestrator.evidence import InputError, load_snapshot
from chain_orchestrator.manager import Limits, _InvalidReply, _Run
from chain_orchestrator.specialists import specialize


def run(coroutine):
    return asyncio.run(coroutine)


def states(report):
    return {task.role: task.state for task in report.tasks}


def test_consistent_run_has_full_positive_provenance_and_three_terminal_tasks():
    report = run(analyze_release())
    snapshot = load_snapshot("consistent")
    assert report.status is RunStatus.COMPLETE
    assert report.mode == "fixture"
    assert report.review_items == ()
    assert list(states(report).values()) == [TaskState.DONE] * 3
    assert [reply.sender for reply in report.accepted] == list(Role)
    records = {(r.role, r.source_id, r.record_id): r for r in snapshot.records}
    for reply in report.accepted:
        assert reply.run_id == report.run_id
        assert reply.recipient == "manager"
        for claim in reply.payload.claims:
            reference = claim.reference
            record = records.pop((claim.role, reference.source_id, reference.record_id))
            assert reference.snapshot_sha256 == snapshot.sha256
            assert claim.scope == record.scope and claim.works is record.works
    assert not records


def test_dissent_survives_repeated_positive_records_and_negative_observations():
    report = run(analyze_release("contradictory"))
    assert report.status is RunStatus.REVIEW_REQUIRED
    conflicts = [item for item in report.review_items if item.kind is ReviewKind.CONTRADICTION]
    assert len(conflicts) == 1
    assert len(conflicts[0].claims) == 6
    assert {c.works for c in conflicts[0].claims} == {True, False}
    assert any(item.kind is ReviewKind.NEGATIVE for item in report.review_items)
    negative = run(analyze_release("negative"))
    assert negative.status is RunStatus.REVIEW_REQUIRED
    assert all(item.kind is ReviewKind.NEGATIVE for item in negative.review_items)
    assert sum(len(item.claims) for item in negative.review_items) == 6


def test_missing_coverage_is_unknown_and_other_scopes_cannot_fill_or_conflict():
    report = run(analyze_release("missing-evidence"))
    assert report.status is RunStatus.REVIEW_REQUIRED
    assert len(report.review_items) == 1
    item = report.review_items[0]
    assert item.kind is ReviewKind.MISSING_COVERAGE
    assert item.scope.feature_id == "search" and item.missing_roles == (Role.FEEDBACK,)
    scoped = run(analyze_release("scoped"))
    assert scoped.status is RunStatus.COMPLETE
    assert sum(len(r.payload.claims) for r in scoped.accepted) == 6
    previous = run(analyze_release("scoped", "v0.9"))
    assert previous.status is RunStatus.REVIEW_REQUIRED
    assert all(c.scope.release == "v0.9" for r in previous.accepted for c in r.payload.claims)


def test_invalid_input_prevents_all_delegation():
    called = []

    async def call(request):
        called.append(request)
        return await specialize(request)

    with pytest.raises(InputError):
        run(analyze_release("consistent", "absent", _specialist=call))
    assert called == []


def test_prerequisite_gates_fanout_and_both_dependents_make_progress_concurrently():
    async def exercise():
        release_started, allow_release = asyncio.Event(), asyncio.Event()
        downstream = {role: asyncio.Event() for role in (Role.TESTS, Role.FEEDBACK)}
        requests = []

        async def call(request):
            requests.append(request)
            with pytest.raises(FrozenInstanceError):
                request.target_release = "altered"
            with pytest.raises(FrozenInstanceError):
                request.records[0].scope.feature_id = "altered"
            assert all(r.role is request.recipient for r in request.records)
            if request.recipient is Role.RELEASE:
                assert request.feature_ids == ()
                release_started.set()
                await allow_release.wait()
            else:
                assert request.feature_ids == ("export", "search")
                downstream[request.recipient].set()
                other = Role.FEEDBACK if request.recipient is Role.TESTS else Role.TESTS
                await downstream[other].wait()
            return await specialize(request)

        task = asyncio.create_task(analyze_release(_specialist=call))
        await release_started.wait()
        assert len(requests) == 1
        assert not any(event.is_set() for event in downstream.values())
        allow_release.set()
        report = await asyncio.wait_for(task, 0.5)
        assert report.status is RunStatus.COMPLETE
        assert len(requests) == 3

    run(exercise())


def mutate_claim(reply, change):
    claims = reply.payload.claims
    return replace(reply, payload=replace(reply.payload, claims=(change(claims[0]), *claims[1:])))


@pytest.mark.parametrize("forge", [
    lambda r: replace(r, run_id="different-run"),
    lambda r: replace(r, task_id="different-task"),
    lambda r: replace(r, sender=Role.TESTS),
    lambda r: replace(r, sender="feedback"),
    lambda r: replace(r, recipient="tests"),
    lambda r: replace(r, payload=ReleaseFindings(("export", "search"), r.payload.claims)),
    lambda r: replace(r, payload=Findings(r.payload.claims[:-1])),
    lambda r: replace(r, payload=Findings((r.payload.claims[0], r.payload.claims[0]))),
    lambda r: replace(r, payload=Findings(list(r.payload.claims))),
    lambda r: mutate_claim(r, lambda c: replace(c, works=not c.works)),
    lambda r: mutate_claim(r, lambda c: replace(c, works=1)),
    lambda r: mutate_claim(r, lambda c: replace(c, role=Role.TESTS)),
    lambda r: mutate_claim(r, lambda c: replace(c, scope=replace(c.scope, environment="production"))),
    lambda r: mutate_claim(r, lambda c: replace(c, reference=replace(c.reference, source_id="tests-source"))),
    lambda r: mutate_claim(r, lambda c: replace(c, reference=replace(c.reference, record_id="invented"))),
    lambda r: mutate_claim(r, lambda c: replace(c, reference=replace(c.reference, snapshot_sha256="0" * 64))),
    lambda r: {"payload": r.payload},
])
def test_forged_incomplete_and_dissent_hiding_replies_never_enter_memory(forge):
    async def call(request):
        reply = await specialize(request)
        return forge(reply) if request.recipient is Role.FEEDBACK else reply

    report = run(analyze_release("contradictory", _specialist=call))
    assert report.status is RunStatus.FAILED
    assert states(report)[Role.FEEDBACK] is TaskState.FAILED
    assert all(reply.sender is not Role.FEEDBACK for reply in report.accepted)


@pytest.mark.parametrize("features", [(), ("export",), ("export", "search", "invented"), ("export", "export")])
def test_forged_release_catalogue_blocks_both_dependents(features):
    calls = []

    async def call(request):
        calls.append(request.recipient)
        reply = await specialize(request)
        return replace(reply, payload=replace(reply.payload, feature_ids=features))

    report = run(analyze_release(_specialist=call))
    assert report.status is RunStatus.FAILED
    assert calls == [Role.RELEASE]
    assert list(states(report).values()) == [TaskState.FAILED, TaskState.BLOCKED, TaskState.BLOCKED]
    assert report.accepted == ()


def test_unknown_feature_cannot_expand_release_catalogue(monkeypatch):
    snapshot = load_snapshot("consistent")
    records = tuple(replace(r, scope=replace(r.scope, feature_id="invented"))
                    if r.role is Role.TESTS else r for r in snapshot.records)
    monkeypatch.setattr("chain_orchestrator.manager.load_snapshot", lambda *_: replace(snapshot, records=records))
    report = run(analyze_release())
    assert states(report)[Role.TESTS] is TaskState.FAILED
    assert report.tasks[1].error == "unknown_target_feature"


def test_empty_release_catalogue_fails_and_empty_downstream_role_requires_review(monkeypatch):
    snapshot = load_snapshot("consistent")
    for role in (Role.RELEASE, Role.FEEDBACK):
        monkeypatch.setattr("chain_orchestrator.manager.load_snapshot", lambda *_, role=role:
                            replace(snapshot, records=tuple(r for r in snapshot.records if r.role is not role)))
        report = run(analyze_release())
        assert report.status is (RunStatus.FAILED if role is Role.RELEASE else RunStatus.REVIEW_REQUIRED)
        if role is Role.FEEDBACK:
            assert len(report.review_items) == 2


def test_prerequisite_failure_sanitizes_errors_and_never_dispatches_dependents():
    calls = []

    async def call(request):
        calls.append(request.recipient)
        raise RuntimeError("SECRET arbitrary exception content")

    report = run(analyze_release(_specialist=call))
    assert calls == [Role.RELEASE]
    assert list(states(report).values()) == [TaskState.FAILED, TaskState.BLOCKED, TaskState.BLOCKED]
    assert "SECRET" not in json.dumps(asdict(report))


def test_downstream_failure_cancels_and_drains_unfinished_sibling():
    async def exercise():
        started, cleaned = asyncio.Event(), asyncio.Event()

        async def call(request):
            if request.recipient is Role.TESTS:
                await started.wait()
                raise ValueError("secret detail")
            if request.recipient is Role.FEEDBACK:
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    await asyncio.sleep(0)
                    cleaned.set()
            return await specialize(request)

        report = await analyze_release(_specialist=call)
        assert report.status is RunStatus.FAILED
        assert states(report)[Role.FEEDBACK] is TaskState.CANCELLED
        assert [r.sender for r in report.accepted] == [Role.RELEASE]
        assert cleaned.is_set()
        assert report.review_items

    run(exercise())


@pytest.mark.parametrize("late_return", [False, True])
def test_timeout_preserves_accepted_negative_evidence_and_rejects_late_reply(late_return):
    async def exercise():
        cleaned = asyncio.Event()

        async def call(request):
            if request.recipient is Role.FEEDBACK:
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    if not late_return:
                        raise
                finally:
                    cleaned.set()
            return await specialize(request)

        report = await analyze_release("negative", _specialist=call, _limits=Limits(0.02, 0.5))
        assert report.status is RunStatus.TIMED_OUT
        assert states(report)[Role.FEEDBACK] is TaskState.TIMED_OUT
        assert [r.sender for r in report.accepted] == [Role.RELEASE, Role.TESTS]
        assert any(item.kind is ReviewKind.NEGATIVE for item in report.review_items)
        assert any(item.kind is ReviewKind.MISSING_COVERAGE for item in report.review_items)
        assert cleaned.is_set()

    run(exercise())


def test_whole_run_deadline_and_prerequisite_timeout_are_explicit():
    async def call(request):
        await asyncio.Event().wait()

    report = run(analyze_release(_specialist=call, _limits=Limits(0.5, 0.01)))
    assert report.status is RunStatus.TIMED_OUT
    assert list(states(report).values()) == [TaskState.TIMED_OUT, TaskState.BLOCKED, TaskState.BLOCKED]
    calls = []

    async def should_not_start(request):
        calls.append(request)
        return await specialize(request)

    expired = run(analyze_release(_specialist=should_not_start, _limits=Limits(1, 1e-30)))
    assert expired.status is RunStatus.TIMED_OUT and calls == []


def test_deadline_crossed_during_validation_prevents_acceptance(monkeypatch):
    from chain_orchestrator import manager

    validate = manager._validate_reply

    def slow_validation(reply, request):
        result = validate(reply, request)
        time.sleep(0.02)
        return result

    monkeypatch.setattr(manager, "_validate_reply", slow_validation)
    report = run(analyze_release(_limits=Limits(0.01, 0.5)))
    assert report.status is RunStatus.TIMED_OUT
    assert report.accepted == ()
    assert list(states(report).values()) == [TaskState.TIMED_OUT, TaskState.BLOCKED, TaskState.BLOCKED]


@pytest.mark.parametrize("failure", ["self_cancel", "own_timeout"])
def test_specialist_cancellation_or_timeout_exception_is_execution_failure(failure):
    async def call(request):
        if failure == "self_cancel":
            raise asyncio.CancelledError
        raise TimeoutError("not the manager deadline")

    report = run(analyze_release(_specialist=call))
    assert report.status is RunStatus.FAILED
    assert list(states(report).values()) == [TaskState.FAILED, TaskState.BLOCKED, TaskState.BLOCKED]
    assert report.accepted == ()


@pytest.mark.parametrize("value", [0, -1, True, float("nan"), float("inf"), 61, "1",
                                  pytest.param(10**1000, id="huge_integer")])
def test_invalid_limits_fail_before_execution(value):
    with pytest.raises(InputError):
        Limits(value, 3)
    with pytest.raises(InputError):
        Limits(1, value)


@pytest.mark.parametrize("trigger", ["external", "sibling_failure", "timeout", "already_cancelling"])
def test_cancellation_cleanup_outlasts_specialist_deadline_without_second_cancellation(trigger):
    async def exercise():
        entered, cleaned = asyncio.Event(), asyncio.Event()

        async def call(request):
            if trigger == "sibling_failure" and request.recipient is Role.RELEASE:
                return await specialize(request)
            if trigger == "sibling_failure" and request.recipient is Role.TESTS:
                await entered.wait()
                await asyncio.sleep(0.01)
                raise RuntimeError("synthetic failure")
            entered.set()
            if trigger == "already_cancelling":
                asyncio.current_task().cancel()
            try:
                await asyncio.Event().wait()
            finally:
                await asyncio.sleep(0.08)
                cleaned.set()

        limits = (Limits(0.02, 0.04) if trigger in ("timeout", "already_cancelling")
                  else Limits(0.03, 0.5))
        task = asyncio.create_task(analyze_release(_specialist=call, _limits=limits))
        await entered.wait()
        if trigger == "external":
            await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        elif trigger == "sibling_failure":
            report = await task
            assert report.status is RunStatus.FAILED
            assert states(report)[Role.FEEDBACK] is TaskState.CANCELLED
        else:
            report = await task
            assert report.status is RunStatus.TIMED_OUT
            assert states(report)[Role.RELEASE] is TaskState.TIMED_OUT
        assert cleaned.is_set()
        assert not [t for t in asyncio.all_tasks() if t.get_name().startswith("agent08:")]

    run(exercise())


@pytest.mark.parametrize("phase", ["prerequisite", "fanout"])
def test_external_cancellation_propagates_after_child_cleanup_even_if_cancelled_again(phase):
    async def exercise():
        entered = asyncio.Event()
        cleanup_started = asyncio.Event()
        allow_cleanup = asyncio.Event()
        started, cleaned = set(), set()

        async def call(request):
            if phase == "fanout" and request.recipient is Role.RELEASE:
                return await specialize(request)
            started.add(request.recipient)
            if phase == "prerequisite" or len(started) == 2:
                entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleanup_started.set()
                await allow_cleanup.wait()
                cleaned.add(request.recipient)

        task = asyncio.create_task(analyze_release(_specialist=call))
        await asyncio.wait_for(entered.wait(), 0.5)
        task.cancel()
        await asyncio.wait_for(cleanup_started.wait(), 0.5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        allow_cleanup.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert started == cleaned
        assert not [t for t in asyncio.all_tasks() if t.get_name().startswith("agent08:")]

    run(exercise())


def test_cancellation_during_failure_drain_propagates_after_cleanup():
    async def exercise():
        entered, cleanup_started, allow_cleanup = asyncio.Event(), asyncio.Event(), asyncio.Event()
        cleaned = False

        async def call(request):
            nonlocal cleaned
            if request.recipient is Role.TESTS:
                await entered.wait()
                raise RuntimeError()
            if request.recipient is Role.FEEDBACK:
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleanup_started.set()
                    await allow_cleanup.wait()
                    cleaned = True
            return await specialize(request)

        task = asyncio.create_task(analyze_release(_specialist=call))
        await asyncio.wait_for(cleanup_started.wait(), 0.5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        allow_cleanup.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cleaned

    run(exercise())


def test_duplicate_receipt_cannot_change_terminal_state_or_accepted_findings():
    async def exercise():
        manager = _Run(load_snapshot("consistent"), Limits(), specialize)
        manager._dispatch(Role.RELEASE)
        completion = await manager.children[Role.RELEASE]
        manager._accept(Role.RELEASE, completion)
        accepted = manager.accepted[Role.RELEASE]
        with pytest.raises(_InvalidReply, match="duplicate_or_terminal_receipt"):
            manager._accept(Role.RELEASE, completion)
        assert manager.accepted[Role.RELEASE] is accepted
        assert manager.outcomes[Role.RELEASE].state is TaskState.DONE
        await manager.drain()

    run(exercise())


def test_replayed_reply_is_rejected_and_concurrent_repeated_runs_remain_isolated():
    async def exercise():
        reports = await asyncio.gather(*(analyze_release(name) for name in
                                         ("consistent", "negative", "consistent")))
        assert len({r.run_id for r in reports}) == 3
        assert [r.status for r in reports] == [RunStatus.COMPLETE, RunStatus.REVIEW_REQUIRED, RunStatus.COMPLETE]
        for report in reports:
            assert all(reply.run_id == report.run_id for reply in report.accepted)
        old_reply = reports[0].accepted[0]

        async def replay(request):
            return old_reply

        rejected = await analyze_release(_specialist=replay)
        assert rejected.status is RunStatus.FAILED
        assert rejected.accepted == ()
        assert (await analyze_release()).status is RunStatus.COMPLETE

    run(exercise())


def test_completion_order_does_not_change_report_order():
    async def exercise(delay_role):
        async def call(request):
            if request.recipient is delay_role:
                await asyncio.sleep(0.002)
            reply = await specialize(request)
            return replace(reply, payload=replace(reply.payload, claims=tuple(reversed(reply.payload.claims))))
        return await analyze_release(_specialist=call)

    first, second = run(exercise(Role.TESTS)), run(exercise(Role.FEEDBACK))
    assert [r.sender for r in first.accepted] == [r.sender for r in second.accepted] == list(Role)
    assert [r.payload for r in first.accepted] == [r.payload for r in second.accepted]
