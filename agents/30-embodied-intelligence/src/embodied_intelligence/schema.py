"""Run-scoped immutable records and the only untrusted JSON boundary.

Positions, velocities and battery are synthetic integer units. Parsing validates
all plans and events before a Dispatcher can observe them or create effects.
"""

from dataclasses import dataclass
import json
import re
from typing import Literal

MAX_BYTES = 32768
MAX_DEPTH = 12
MAX_VALUES = 2048


class InvalidRequest(ValueError):
    """A fixed public error, deliberately without input text or parser details."""


@dataclass(frozen=True)
class CartState:
    """One observation. Version changes on every host-owned state replacement."""

    position: int
    velocity: int
    battery: int
    obstacles: tuple[int, ...]
    version: int
    emergency_stop: bool


@dataclass(frozen=True)
class Command:
    """A proposal for one tick, identified together with its observed version."""

    action_id: str
    expected_version: int
    velocity: int


@dataclass(frozen=True)
class Event:
    """Host fixture world update. An emergency event can only latch the stop."""

    tick: int
    kind: Literal['obstacles', 'emergency_stop']
    obstacles: tuple[int, ...] = ()


@dataclass(frozen=True)
class Request:
    state: CartState
    goal: int
    plans: tuple[tuple[Command, ...], ...]
    events: tuple[Event, ...]
    max_ticks: int


def _object(value: object, keys: set[str]) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise InvalidRequest
    return value


def _integer(value: object, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise InvalidRequest
    return value


def _array(value: object, low: int, high: int) -> list:
    if type(value) is not list or not low <= len(value) <= high:
        raise InvalidRequest
    return value


def _obstacles(value: object) -> tuple[int, ...]:
    points = tuple(_integer(item, 0, 100) for item in _array(value, 0, 20))
    if tuple(sorted(set(points))) != points:
        raise InvalidRequest
    return points


def _state(value: object) -> CartState:
    obj = _object(value, {'position', 'velocity', 'battery', 'obstacles', 'version', 'emergency_stop'})
    if type(obj['emergency_stop']) is not bool:
        raise InvalidRequest
    state = CartState(
        _integer(obj['position'], 0, 100), _integer(obj['velocity'], -3, 3),
        _integer(obj['battery'], 0, 100), _obstacles(obj['obstacles']),
        _integer(obj['version'], 0, 1000), obj['emergency_stop'],
    )
    if state.position in state.obstacles or (state.emergency_stop and state.velocity != 0):
        raise InvalidRequest
    return state


def _command(value: object) -> Command:
    obj = _object(value, {'action_id', 'expected_version', 'velocity'})
    action_id = obj['action_id']
    if type(action_id) is not str or re.fullmatch(r'[A-Za-z0-9_-]{1,32}', action_id) is None:
        raise InvalidRequest
    return Command(action_id, _integer(obj['expected_version'], 0, 2000), _integer(obj['velocity'], -100, 100))


def _event(value: object) -> Event:
    if type(value) is not dict:
        raise InvalidRequest
    if value.get('kind') == 'emergency_stop':
        obj = _object(value, {'tick', 'kind'})
        return Event(_integer(obj['tick'], 0, 19), 'emergency_stop')
    obj = _object(value, {'tick', 'kind', 'obstacles'})
    if obj['kind'] != 'obstacles':
        raise InvalidRequest
    return Event(_integer(obj['tick'], 0, 19), 'obstacles', _obstacles(obj['obstacles']))


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidRequest
        result[key] = value
    return result


def _no_number(_: str) -> None:
    raise InvalidRequest


def parse_request(data: bytes) -> Request:
    """Parse at most 32 KiB and validate the entire finite scenario atomically."""
    if len(data) > MAX_BYTES:
        raise InvalidRequest
    try:
        text = data.decode('utf-8')
        # Scan outside strings before json.loads so nesting cannot exhaust its stack.
        depth = 0
        quoted = escaped = False
        for char in text:
            if quoted:
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in '[{':
                depth += 1
                if depth > MAX_DEPTH:
                    raise InvalidRequest
            elif char in ']}':
                depth -= 1
        value = json.loads(text, object_pairs_hook=_pairs, parse_float=_no_number, parse_constant=_no_number)
        stack = [value]
        count = 0
        while stack:
            item = stack.pop()
            count += 1
            if count > MAX_VALUES:
                raise InvalidRequest
            if type(item) is dict:
                stack.extend(item.values())
            elif type(item) is list:
                stack.extend(item)
        obj = _object(value, {'state', 'goal', 'plans', 'events', 'max_ticks'})
        events = tuple(_event(item) for item in _array(obj['events'], 0, 20))
        if tuple(event.tick for event in events) != tuple(sorted(event.tick for event in events)):
            raise InvalidRequest
        if len({(event.tick, event.kind) for event in events}) != len(events):
            raise InvalidRequest
        return Request(
            _state(obj['state']), _integer(obj['goal'], 0, 100),
            tuple(tuple(_command(command) for command in _array(plan, 0, 20))
                  for plan in _array(obj['plans'], 1, 2)),
            events, _integer(obj['max_ticks'], 1, 20),
        )
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError):
        raise InvalidRequest from None
