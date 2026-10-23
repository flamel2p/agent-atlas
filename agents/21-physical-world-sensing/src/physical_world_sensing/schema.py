"""Bounded JSON trust boundary for the sensor replay scenario.

The entire document is validated before replay can produce output. Decimal JSON
decoding preserves finite input values; no binary float enters the domain. A
small lexical depth guard rejects excessive nesting before the JSON decoder.
"""

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import cast

from .domain import KINDS, Kind, Reading, Scenario, Sensor, Zone

MAX_INPUT_BYTES = 262_144
MAX_JSON_DEPTH = 16
_ID = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")


class ScenarioError(ValueError):
    """The external document does not satisfy the bounded scenario contract."""


def _fail() -> None:
    raise ScenarioError("invalid scenario")


def _object(value: object, fields: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        _fail()
    return value


def _array(value: object, minimum: int, maximum: int) -> list:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        _fail()
    return value


def _identifier(value: object) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        _fail()
    return value


def _number(value: object, minimum: int, maximum: int) -> Decimal:
    if type(value) not in (int, Decimal):
        _fail()
    number = Decimal(value)
    if not number.is_finite():
        _fail()
    parts = number.as_tuple()
    if len(parts.digits) > 12 or parts.exponent < -3:
        _fail()
    if not minimum <= number <= maximum:
        _fail()
    return number


def _hour(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 24:
        _fail()
    return value


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or _TIME.fullmatch(value) is None:
        _fail()
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail()
    if not 2000 <= result.year <= 2100:
        _fail()
    return result.astimezone(timezone.utc)


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            _fail()
        result[key] = value
    return result


def _constant(_: str) -> None:
    _fail()


def _decode(raw: str | bytes) -> object:
    if not isinstance(raw, (str, bytes)):
        _fail()
    try:
        encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
        if len(encoded) > MAX_INPUT_BYTES:
            _fail()
        document = encoded.decode("utf-8")
        depth, quoted, escaped = 0, False, False
        for char in document:
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "[{":
                depth += 1
                if depth > MAX_JSON_DEPTH:
                    _fail()
            elif char in "]}":
                depth -= 1
        return json.loads(
            document, parse_float=Decimal, parse_constant=_constant,
            object_pairs_hook=_pairs,
        )
    except (UnicodeError, json.JSONDecodeError, InvalidOperation, RecursionError, ValueError):
        _fail()


def parse_scenario(raw: str | bytes) -> Scenario:
    """Validate raw UTF-8 JSON and return immutable, canonically ordered records.

    No replay state exists until all references, identities, bounds, timestamps,
    values, and schedule definitions have passed. IDs need only be unique within
    their own collection; duplicate sensor/observation pairs are forbidden too.
    """
    root = _object(_decode(raw), {"zones", "sensors", "readings", "ticks"})
    zones = []
    for item in _array(root["zones"], 1, 8):
        zone = _object(item, {
            "id", "target_min_c", "target_max_c", "co2_limit_ppm",
            "occupied_start_hour", "occupied_end_hour",
        })
        record = Zone(
            _identifier(zone["id"]),
            _number(zone["target_min_c"], 10, 35),
            _number(zone["target_max_c"], 10, 35),
            _number(zone["co2_limit_ppm"], 400, 2000),
            _hour(zone["occupied_start_hour"]),
            _hour(zone["occupied_end_hour"]),
        )
        if record.target_min_c >= record.target_max_c:
            _fail()
        if record.occupied_start_hour >= record.occupied_end_hour:
            _fail()
        zones.append(record)
    zone_ids = {zone.id for zone in zones}
    if len(zone_ids) != len(zones):
        _fail()

    sensors = []
    for item in _array(root["sensors"], 1, 64):
        sensor = _object(item, {"id", "zone_id", "kind"})
        kind = sensor["kind"]
        if kind not in KINDS:
            _fail()
        record = Sensor(_identifier(sensor["id"]), _identifier(sensor["zone_id"]), cast(Kind, kind))
        if record.zone_id not in zone_ids:
            _fail()
        sensors.append(record)
    by_sensor = {sensor.id: sensor for sensor in sensors}
    if len(by_sensor) != len(sensors):
        _fail()
    if any({sensor.kind for sensor in sensors if sensor.zone_id == zone.id} != set(KINDS) for zone in zones):
        _fail()

    readings = []
    observations = set()
    for item in _array(root["readings"], 0, 512):
        reading = _object(item, {"id", "sensor_id", "observed_at", "received_at", "value"})
        sensor_id = _identifier(reading["sensor_id"])
        if sensor_id not in by_sensor:
            _fail()
        kind = by_sensor[sensor_id].kind
        minimum, maximum = {"temperature": (-40, 85), "co2": (250, 10000), "occupancy": (0, 1)}[kind]
        record = Reading(
            _identifier(reading["id"]), sensor_id,
            _timestamp(reading["observed_at"]), _timestamp(reading["received_at"]),
            _number(reading["value"], minimum, maximum),
        )
        if kind == "occupancy" and record.value not in (0, 1):
            _fail()
        pair = (record.sensor_id, record.observed_at)
        if record.observed_at > record.received_at or pair in observations:
            _fail()
        observations.add(pair)
        readings.append(record)
    if len({reading.id for reading in readings}) != len(readings):
        _fail()

    ticks = tuple(_timestamp(value) for value in _array(root["ticks"], 1, 64))
    if any(left >= right for left, right in zip(ticks, ticks[1:])):
        _fail()
    if (ticks[-1] - ticks[0]).total_seconds() > 86400:
        _fail()
    return Scenario(
        tuple(sorted(zones, key=lambda zone: zone.id)),
        tuple(sorted(sensors, key=lambda sensor: sensor.id)),
        tuple(sorted(readings, key=lambda reading: (reading.received_at, reading.id))), ticks,
    )
