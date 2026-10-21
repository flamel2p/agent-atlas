"""Own one fixed release -> concurrent tests/feedback workflow and its memory.

Specialists propose messages; only this manager changes task state or accepts
evidence. Validation requires exact input-record coverage, so voting or omission
cannot hide dissent. Deadlines are cooperative asyncio limits, not isolation
from hostile Python code. Started children are always cancelled and drained.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
import math
from uuid import uuid4

from .contracts import (
    Claim, Findings, Reference, ReleaseFindings, Reply, Report, Request,
    ReviewItem, ReviewKind, Role, RunStatus, Scope, Snapshot, TaskOutcome, TaskState,
)
from .evidence import InputError, load_snapshot
from .specialists import specialize

type Specialist = Callable[[Request], Awaitable[Reply]]


@dataclass(frozen=True, slots=True)
class Limits:
    """Test-facing deadlines in seconds, each finite and in (0, 60]."""

    specialist_seconds: float = 1.0
    run_seconds: float = 3.0

    def __post_init__(self) -> None:
        for value in (self.specialist_seconds, self.run_seconds):
            if type(value) not in (int, float) or not 0 < value <= 60 or not math.isfinite(value):
                raise InputError("invalid_timeout_limit")


class _InvalidReply(ValueError):
    pass


def _validate_reply(reply: object, request: Request) -> Reply:
    """Check identity, shape, provenance, assertion and complete record coverage.

    Dataclass annotations do not validate runtime values. Exact nested types
    prevent booleans comparing equal to integers and strings impersonating enums.
    The canonical accepted message is reconstructed from validated input records.
    """
    if (type(reply) is not Reply or type(reply.run_id) is not str
            or type(reply.task_id) is not str or type(reply.sender) is not Role
            or type(reply.recipient) is not str
            or (reply.run_id, reply.task_id, reply.sender, reply.recipient)
            != (request.run_id, request.task_id, request.recipient, "manager")):
        raise _InvalidReply("invalid_envelope")
    expected_type = ReleaseFindings if request.recipient is Role.RELEASE else Findings
    if type(reply.payload) is not expected_type or type(reply.payload.claims) is not tuple:
        raise _InvalidReply("invalid_payload")
    if len(reply.payload.claims) != len(request.records):
        raise _InvalidReply("incomplete_record_coverage")
    features = tuple(sorted({record.scope.feature_id for record in request.records}))
    if request.recipient is Role.RELEASE:
        catalogue = reply.payload.feature_ids
        if (type(catalogue) is not tuple or not features
                or any(type(feature) is not str for feature in catalogue)
                or len(catalogue) != len(features) or set(catalogue) != set(features)):
            raise _InvalidReply("invalid_release_catalogue")
    elif any(feature not in request.feature_ids for feature in features):
        raise _InvalidReply("unknown_target_feature")
    expected = {
        (record.source_id, record.record_id): Claim(
            request.recipient, record.scope, record.works,
            Reference(record.source_id, record.record_id, request.snapshot_sha256),
        ) for record in request.records
    }
    seen = set()
    for claim in reply.payload.claims:
        if (type(claim) is not Claim or type(claim.role) is not Role
                or type(claim.works) is not bool or type(claim.scope) is not Scope
                or type(claim.reference) is not Reference
                or any(type(value) is not str for value in (
                    claim.scope.release, claim.scope.feature_id, claim.scope.environment,
                    claim.reference.source_id, claim.reference.record_id,
                    claim.reference.snapshot_sha256))):
            raise _InvalidReply("invalid_claim_shape")
        identity = claim.reference.source_id, claim.reference.record_id
        if identity in seen or identity not in expected or claim != expected[identity]:
            raise _InvalidReply("invalid_claim_provenance_or_assertion")
        seen.add(identity)
    claims = tuple(sorted(expected.values(), key=lambda c: (
        c.scope.feature_id, c.reference.source_id, c.reference.record_id)))
    payload = ReleaseFindings(features, claims) if request.recipient is Role.RELEASE else Findings(claims)
    return Reply(request.run_id, request.task_id, request.recipient, "manager", payload)


@dataclass(frozen=True, slots=True)
class _Completion:
    reply: object = None
    error: str | None = None
    timed_out: bool = False


async def _invoke(call: Specialist, request: Request, deadline: float) -> _Completion:
    if asyncio.get_running_loop().time() >= deadline:
        return _Completion(error="specialist_timeout", timed_out=True)
    try:
        reply = await call(request)
        # A coroutine can suppress cancellation and still return a valid message.
        # Returning does not grant permission to bypass the manager's deadline.
        if asyncio.get_running_loop().time() >= deadline:
            return _Completion(error="specialist_timeout", timed_out=True)
        return _Completion(reply=reply)
    except Exception:
        return _Completion(error="specialist_error")


def _reconcile(snapshot: Snapshot, accepted: dict[Role, Reply]) -> tuple[ReviewItem, ...]:
    release = accepted.get(Role.RELEASE)
    if release is None:
        return ()
    items = []
    for feature in release.payload.feature_ids:
        scope = Scope(snapshot.target_release, feature, snapshot.environment)
        claims = tuple(claim for role in Role if role in accepted
                       for claim in accepted[role].payload.claims if claim.scope == scope)
        if {claim.works for claim in claims} == {False, True}:
            items.append(ReviewItem(ReviewKind.CONTRADICTION, scope, claims))
        negatives = tuple(claim for claim in claims if not claim.works)
        if negatives:
            items.append(ReviewItem(ReviewKind.NEGATIVE, scope, negatives))
        missing = tuple(role for role in Role if not any(c.role is role for c in claims))
        if missing:
            items.append(ReviewItem(ReviewKind.MISSING_COVERAGE, scope, (), missing))
    return tuple(items)


class _Run:
    """Private per-run working memory. Child coroutines never receive this object."""

    def __init__(self, snapshot: Snapshot, limits: Limits, call: Specialist):
        self.snapshot = snapshot
        self.limits = limits
        self.call = call
        self.run_id = uuid4().hex
        self.deadline = asyncio.get_running_loop().time() + limits.run_seconds
        self.outcomes = {role: TaskOutcome(role, f"{self.run_id}:{role}", TaskState.PENDING, None)
                         for role in Role}
        self.requests: dict[Role, Request] = {}
        self.children: dict[Role, asyncio.Task] = {}
        self.deadlines: dict[Role, float] = {}
        self.accepted: dict[Role, Reply] = {}

    def _transition(self, role: Role, state: TaskState, error: str | None = None) -> None:
        previous = self.outcomes[role]
        allowed = ({TaskState.RUNNING, TaskState.BLOCKED, TaskState.CANCELLED}
                   if previous.state is TaskState.PENDING else
                   {TaskState.DONE, TaskState.FAILED, TaskState.TIMED_OUT, TaskState.CANCELLED}
                   if previous.state is TaskState.RUNNING else set())
        if state not in allowed:
            raise RuntimeError("invalid_task_transition")
        self.outcomes[role] = replace(previous, state=state, error=error)

    def _dispatch(self, role: Role) -> bool:
        now = asyncio.get_running_loop().time()
        if now >= self.deadline:
            self._transition(role, TaskState.BLOCKED, "run_timeout")
            return False
        snapshot = self.snapshot
        features = (() if role is Role.RELEASE else
                    self.accepted[Role.RELEASE].payload.feature_ids)
        records = tuple(record for record in snapshot.records if record.role is role
                        and record.scope.release == snapshot.target_release
                        and record.scope.environment == snapshot.environment)
        request = Request(self.run_id, self.outcomes[role].task_id, "manager", role,
                          snapshot.target_release, snapshot.environment, snapshot.sha256,
                          records, features)
        self.requests[role] = request
        self.deadlines[role] = min(now + self.limits.specialist_seconds, self.deadline)
        self._transition(role, TaskState.RUNNING)
        self.children[role] = asyncio.create_task(
            _invoke(self.call, request, self.deadlines[role]), name=f"agent08:{request.task_id}")
        return True

    def _accept(self, role: Role, completion: _Completion) -> None:
        if self.outcomes[role].state is not TaskState.RUNNING or role in self.accepted:
            raise _InvalidReply("duplicate_or_terminal_receipt")
        if completion.timed_out or asyncio.get_running_loop().time() >= self.deadlines[role]:
            self._transition(role, TaskState.TIMED_OUT, "specialist_timeout")
        elif completion.error is not None:
            self._transition(role, TaskState.FAILED, completion.error)
        else:
            try:
                reply = _validate_reply(completion.reply, self.requests[role])
            except _InvalidReply as exc:
                self._transition(role, TaskState.FAILED, str(exc))
            else:
                if asyncio.get_running_loop().time() >= self.deadlines[role]:
                    self._transition(role, TaskState.TIMED_OUT, "specialist_timeout")
                else:
                    self.accepted[role] = reply
                    self._transition(role, TaskState.DONE)

    async def _collect(self, roles: tuple[Role, ...]) -> None:
        pending = {role for role in roles if role in self.children}
        while pending:
            now = asyncio.get_running_loop().time()
            expired = [role for role in roles if role in pending and now >= self.deadlines[role]]
            if expired:
                for role in expired:
                    error = "run_timeout" if now >= self.deadline else "specialist_timeout"
                    self._transition(role, TaskState.TIMED_OUT, error)
                return
            # The manager owns every deadline. There are no child timeout timers
            # that could fire a second cancellation inside asynchronous cleanup.
            remaining = min(self.deadlines[role] for role in pending) - now
            done, _ = await asyncio.wait(
                [self.children[role] for role in pending], timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
            # Fixed order canonicalizes simultaneous receipts, independent of set order.
            for role in roles:
                if role in pending and self.children[role] in done:
                    pending.remove(role)
                    child = self.children[role]
                    completion = (_Completion(error="specialist_cancelled") if child.cancelled()
                                  else child.result())
                    self._accept(role, completion)
            if any(self.outcomes[role].state in (TaskState.FAILED, TaskState.TIMED_OUT)
                   for role in roles):
                return

    async def execute(self) -> None:
        if self._dispatch(Role.RELEASE):
            await self._collect((Role.RELEASE,))
        if self.outcomes[Role.RELEASE].state is not TaskState.DONE:
            for role in (Role.TESTS, Role.FEEDBACK):
                self._transition(role, TaskState.BLOCKED, "prerequisite_unavailable")
            return
        for role in (Role.TESTS, Role.FEEDBACK):
            self._dispatch(role)
        await self._collect((Role.TESTS, Role.FEEDBACK))

    async def drain(self) -> None:
        """Wait for child cleanup even when the caller cancels again during drainage."""
        for child in self.children.values():
            # Already-cancelling children may be awaiting their own cleanup.
            if not child.done() and not child.cancelling():
                child.cancel()
        cleanup = asyncio.gather(*self.children.values(), return_exceptions=True)
        interrupted = False
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                interrupted = True
        # Retrieve every terminal result. A late reply cannot enter accepted memory.
        cleanup.result()
        for role, outcome in self.outcomes.items():
            if outcome.state in (TaskState.PENDING, TaskState.RUNNING):
                self._transition(role, TaskState.CANCELLED)
        if interrupted:
            raise asyncio.CancelledError

    def report(self) -> Report:
        review = _reconcile(self.snapshot, self.accepted)
        outcomes = tuple(self.outcomes[role] for role in Role)
        if any(task.state is TaskState.TIMED_OUT or task.error == "run_timeout" for task in outcomes):
            status = RunStatus.TIMED_OUT
        elif any(task.state is not TaskState.DONE for task in outcomes):
            status = RunStatus.FAILED
        else:
            status = RunStatus.REVIEW_REQUIRED if review else RunStatus.COMPLETE
        return Report("fixture", self.run_id, status, self.snapshot.target_release,
                      self.snapshot.environment, self.snapshot.sha256, outcomes,
                      tuple(self.accepted[role] for role in Role if role in self.accepted), review)


async def analyze_release(
    scenario: str = "consistent", target_release: str | None = None, *,
    _specialist: Specialist | None = None, _limits: Limits = Limits(),
) -> Report:
    """Load a bundled scenario and return an immutable report after child cleanup.

    Underscored arguments support trusted local fault tests, not plugin loading.
    Fault scenarios are host-owned; request fields never select execution policy.
    External cancellation propagates after drainage instead of becoming a report.
    """
    if type(_limits) is not Limits:
        raise InputError("invalid_timeout_limit")
    snapshot = load_snapshot(scenario, target_release)

    async def built_in(request: Request) -> Reply:
        if scenario == "prerequisite-failure" and request.recipient is Role.RELEASE:
            raise RuntimeError("synthetic prerequisite failure")
        if scenario == "downstream-failure" and request.recipient is Role.TESTS:
            await asyncio.sleep(0.01)
            raise RuntimeError("synthetic downstream failure")
        if scenario == "timeout" and request.recipient is Role.FEEDBACK:
            await asyncio.sleep(2)
        return await specialize(request)

    run = _Run(snapshot, _limits, built_in if _specialist is None else _specialist)
    try:
        await run.execute()
    finally:
        await run.drain()
    return run.report()
