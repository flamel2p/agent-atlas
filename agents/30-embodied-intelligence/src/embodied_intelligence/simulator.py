"""Fixture proposals meet host authority in a finite integer cart simulation.

The Dispatcher alone replaces current state and records effects. The planner
merely iterates supplied plans. Run orchestration handles world events, bounded
replanning and terminal freezing; it never mutates the cart behind dispatch.
"""

from dataclasses import asdict, dataclass, replace
from typing import Literal

from .schema import CartState, Command, Event, Request

Outcome = Literal['complete', 'halted', 'fault', 'limit']
EffectKind = Literal['command', 'obstacles', 'emergency_stop', 'brake']


@dataclass(frozen=True)
class Receipt:
    """Evidence for one accepted action. Replays return this same prior record."""

    action_id: str
    command: Command
    before: CartState
    after: CartState
    energy: int


@dataclass(frozen=True)
class DispatchResult:
    accepted: bool
    replayed: bool
    reason: str
    receipt: Receipt | None = None


@dataclass(frozen=True)
class Effect:
    """One host mutation, including zero-energy environment and brake updates."""

    kind: EffectKind
    before: CartState
    after: CartState
    energy: int = 0
    action_id: str | None = None


@dataclass(frozen=True)
class Attempt:
    tick: int
    command: Command
    observed_version: int
    accepted: bool
    replayed: bool
    reason: str
    receipt: Receipt | None


class Dispatcher:
    """Sole owner of a run's current observation and accepted-action ledger.

    Caller records have already passed parse_request. Execution is synchronous,
    so checking current state and replacing it form one indivisible dispatch.
    No proposal or receipt grants authority over physical equipment.
    """

    def __init__(self, state: CartState):
        self._state = state
        self._receipts: dict[str, Receipt] = {}
        self._effects: list[Effect] = []

    @property
    def state(self) -> CartState:
        return self._state

    @property
    def effects(self) -> tuple[Effect, ...]:
        return tuple(self._effects)

    def _commit(self, after: CartState, kind: EffectKind, energy: int = 0, action_id: str | None = None) -> None:
        self._effects.append(Effect(kind, self._state, after, energy, action_id))
        self._state = after

    def emergency_stop(self) -> None:
        """Latch immediately, even when the next proposal is an exact replay."""
        if not self._state.emergency_stop:
            self._commit(replace(self._state, velocity=0, emergency_stop=True,
                                 version=self._state.version + 1), 'emergency_stop')

    def update_obstacles(self, event: Event) -> None:
        if not self._state.emergency_stop:
            self._commit(replace(self._state, obstacles=event.obstacles,
                                 version=self._state.version + 1), 'obstacles')

    def brake(self) -> None:
        """Freeze a terminal simulator state without claiming physical braking."""
        if self._state.velocity:
            self._commit(replace(self._state, velocity=0, version=self._state.version + 1), 'brake')

    def dispatch(self, command: Command) -> DispatchResult:
        """Revalidate against current state immediately before exactly one effect."""
        state = self._state
        if state.emergency_stop:
            return DispatchResult(False, False, 'emergency_stop')
        prior = self._receipts.get(command.action_id)
        if prior is not None:
            if prior.command != command:
                return DispatchResult(False, False, 'changed_action_id')
            # A replay acknowledges history and never overwrites a newer observation.
            return DispatchResult(True, True, 'replayed', prior)
        if command.expected_version != state.version:
            return DispatchResult(False, False, 'stale_observation')
        if abs(command.velocity) > 3:
            return DispatchResult(False, False, 'excessive_speed')
        position = state.position + command.velocity
        if not 0 <= position <= 100:
            return DispatchResult(False, False, 'out_of_bounds')
        low, high = sorted((state.position, position))
        # Checking the closed segment prevents jumping over a point obstacle.
        if any(low <= obstacle <= high for obstacle in state.obstacles):
            return DispatchResult(False, False, 'obstacle_crossing')
        energy = 1 + abs(command.velocity)
        if state.battery < energy:
            return DispatchResult(False, False, 'insufficient_battery')
        after = replace(state, position=position, velocity=command.velocity,
                        battery=state.battery - energy, version=state.version + 1)
        receipt = Receipt(command.action_id, command, state, after, energy)
        self._commit(after, 'command', energy, command.action_id)
        self._receipts[command.action_id] = receipt
        return DispatchResult(True, False, 'accepted', receipt)


class FixturePlanner:
    """Finite scripted planner. Loading a replacement discards the old tail."""

    def __init__(self, plans: tuple[tuple[Command, ...], ...]):
        self.plans = plans
        self.plan_index = 0
        self.command_index = 0

    def propose(self) -> Command | None:
        plan = self.plans[self.plan_index]
        if self.command_index == len(plan):
            return None
        command = plan[self.command_index]
        self.command_index += 1
        return command

    def replace_plan(self) -> bool:
        if self.plan_index + 1 == len(self.plans):
            return False
        self.plan_index += 1
        self.command_index = 0
        return True


def run(request: Request) -> dict:
    """Return bounded trace and final state. No world state survives this call."""
    dispatcher = Dispatcher(request.state)
    planner = FixturePlanner(request.plans)
    attempts: list[Attempt] = []
    processed: set[int] = set()
    ticks = replans = 0
    outcome: Outcome
    reason = ''
    while True:
        current = [(index, event) for index, event in enumerate(request.events)
                   if event.tick == ticks and index not in processed]
        emergency = [(index, event) for index, event in current if event.kind == 'emergency_stop']
        # Emergency authority precedes success and replay, including at a tick limit.
        if dispatcher.state.emergency_stop or emergency:
            processed.update(index for index, _ in emergency)
            dispatcher.emergency_stop()
            outcome, reason = 'halted', 'emergency_stop'
            break
        for index, event in current:
            dispatcher.update_obstacles(event)
            processed.add(index)
        if dispatcher.state.position == request.goal and dispatcher.state.velocity == 0:
            outcome, reason = 'complete', 'goal_reached'
            break
        if ticks >= request.max_ticks:
            outcome, reason = 'limit', 'tick_limit'
            break
        command = planner.propose()
        failure = 'plan_exhausted'
        if command is not None:
            observed = dispatcher.state.version
            result = dispatcher.dispatch(command)
            attempts.append(Attempt(ticks, command, observed, result.accepted,
                                    result.replayed, result.reason, result.receipt))
            ticks += 1
            if result.accepted:
                continue
            failure = result.reason
        if replans == 1:
            outcome, reason = 'limit', 'replan_limit'
            break
        if not planner.replace_plan():
            outcome, reason = 'fault', failure
            break
        replans += 1
    dispatcher.brake()
    return {
        'schema_version': 1, 'mode': 'fixture', 'outcome': outcome, 'reason': reason,
        'ticks': ticks, 'replans': replans, 'goal': request.goal,
        'initial_state': asdict(request.state), 'final_state': asdict(dispatcher.state),
        'attempts': [asdict(attempt) for attempt in attempts],
        'effects': [asdict(effect) for effect in dispatcher.effects],
        'unprocessed_events': len(request.events) - len(processed),
        'limits': {'max_ticks': request.max_ticks, 'max_replans': 1},
    }
