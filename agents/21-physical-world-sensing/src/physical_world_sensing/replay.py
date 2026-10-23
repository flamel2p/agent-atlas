"""Fuse asynchronous evidence and derive independent simulated controls.

Freshness means observation age is between zero and 300 seconds inclusive.
Fusion uses one latest arrived observation per sensor, not every message. The
run-owned cache is the only mutable runtime state; a delayed old observation
cannot replace a newer observation. Exact rational arithmetic controls policy;
six-place decimal rendering is only a presentation boundary.
"""

from datetime import datetime
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction

from .domain import KINDS, Decision, Estimate, Kind, Reading, Scenario, Sensor, Zone


def timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def decimal_text(value: Decimal | Fraction) -> str:
    """Render exact input decimals or a six-place half-even estimate display."""
    if isinstance(value, Fraction):
        # Precision is local so caller Decimal settings cannot change replay.
        with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999)):
            value = (Decimal(value.numerator) / Decimal(value.denominator)).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_EVEN,
            )
    if not value:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _age(tick: datetime, reading: Reading) -> int:
    delta = tick - reading.observed_at
    return delta.days * 86400 + delta.seconds


def _fuse(kind: Kind, sensors: tuple[Sensor, ...], latest: dict[str, Reading], tick: datetime) -> Estimate:
    readings = tuple(
        latest[sensor.id] for sensor in sensors
        if sensor.id in latest and 0 <= _age(tick, latest[sensor.id]) <= 300
    )
    if not readings:
        return Estimate(kind, "unavailable", None, len(sensors), readings)
    values = tuple(Fraction(reading.value) for reading in readings)
    if kind != "occupancy" and max(values) - min(values) > {"temperature": 4, "co2": 400}[kind]:
        return Estimate(kind, "conflict", None, len(sensors), readings)
    value = Fraction(any(values)) if kind == "occupancy" else sum(values, Fraction()) / len(values)
    return Estimate(kind, "ok", value, len(sensors), readings)


def _diagnostics(estimate: Estimate, sensors: tuple[Sensor, ...], latest: dict[str, Reading], tick: datetime) -> list[dict]:
    records = []
    missing = [sensor.id for sensor in sensors if sensor.id not in latest]
    stale = [latest[sensor.id] for sensor in sensors if sensor.id in latest and _age(tick, latest[sensor.id]) > 300]
    if missing:
        records.append({
            "code": "missing_reading", "kind": estimate.kind, "sensor_ids": missing,
            "reading_ids": [], "reason": "No observation has arrived for these registered sensors.",
        })
    if stale:
        records.append({
            "code": "stale_reading", "kind": estimate.kind,
            "sensor_ids": [reading.sensor_id for reading in stale],
            "reading_ids": [reading.id for reading in stale],
            "reason": "Latest observations exceed the 300-second freshness window.",
        })
    if estimate.quality == "conflict":
        records.append({
            "code": "conflicting_readings", "kind": estimate.kind,
            "sensor_ids": [reading.sensor_id for reading in estimate.readings],
            "reading_ids": [reading.id for reading in estimate.readings],
            "reason": "Fresh observations exceed the configured spread tolerance.",
        })
    return records


def _decide(zone: Zone, estimate: Estimate) -> Decision:
    ids = tuple(reading.id for reading in estimate.readings)
    if estimate.value is None:
        return Decision("hold", None, f"{estimate.kind} evidence is {estimate.quality}.", ids)
    if estimate.kind == "temperature":
        midpoint = (Fraction(zone.target_min_c) + Fraction(zone.target_max_c)) / 2
        error = estimate.value - midpoint
        if abs(error) <= 1:
            return Decision("idle", 0, "Temperature is within the inclusive neutral band.", ids)
        return Decision(
            "cool" if error > 0 else "heat", min(100, abs(error) * 20 // 1),
            "Temperature is outside the neutral band around the target midpoint.", ids,
        )
    excess = estimate.value - Fraction(zone.co2_limit_ppm)
    if excess <= 0:
        return Decision("idle", 0, "CO2 does not exceed the zone limit.", ids)
    return Decision("ventilate", min(100, excess // 10), "CO2 exceeds the zone limit.", ids)


def _decision_json(decision: Decision) -> dict:
    return {
        "mode": decision.mode, "percentage": decision.percentage,
        "reason": decision.reason, "source_reading_ids": list(decision.source_reading_ids),
    }


def _estimate_json(estimate: Estimate, tick: datetime) -> dict:
    return {
        "quality": estimate.quality,
        "value": None if estimate.value is None else decimal_text(estimate.value),
        "registered_count": estimate.registered_count, "eligible_count": len(estimate.readings),
        "readings": [{
            "reading_id": reading.id, "sensor_id": reading.sensor_id,
            "observed_at": timestamp(reading.observed_at), "received_at": timestamp(reading.received_at),
            "value": decimal_text(reading.value), "age_seconds": _age(tick, reading),
        } for reading in estimate.readings],
    }


def _alerts(zone: Zone, estimates: dict[Kind, Estimate], tick: datetime) -> list[dict]:
    records = []
    # Individual critical evidence survives fusion rejection. Superseded samples
    # are deliberately absent because only the selected latest evidence applies.
    for reading in estimates["temperature"].readings:
        if reading.value <= 5 or reading.value >= 35:
            records.append({
                "code": "critical_temperature", "reading_ids": [reading.id],
                "reason": "A fresh selected temperature observation meets a critical threshold.",
            })
    co2 = estimates["co2"]
    if co2.value is not None and co2.value > Fraction(zone.co2_limit_ppm):
        records.append({
            "code": "high_co2", "reading_ids": [reading.id for reading in co2.readings],
            "reason": "The usable CO2 estimate exceeds the zone limit.",
        })
    occupancy = estimates["occupancy"]
    if occupancy.value == 1 and not zone.occupied_start_hour <= tick.hour < zone.occupied_end_hour:
        records.append({
            "code": "unexpected_occupancy",
            "reading_ids": [reading.id for reading in occupancy.readings if reading.value == 1],
            "reason": "Observed occupancy is present outside the configured UTC schedule.",
        })
    return records


def run_replay(scenario: Scenario) -> dict:
    """Evaluate a validated scenario with no network, hardware, or durable state.

    Each usable channel emits one simulated desired command per tick, including
    repeated/zero-percent commands. A hold emits none. This log expresses policy
    decisions only; it cannot establish physical actuator behavior or safety.
    """
    latest: dict[str, Reading] = {}
    command_log = []
    ticks = []
    position = 0
    bindings = {
        (zone.id, kind): tuple(sensor for sensor in scenario.sensors if sensor.zone_id == zone.id and sensor.kind == kind)
        for zone in scenario.zones for kind in KINDS
    }
    for tick in scenario.ticks:
        while position < len(scenario.readings) and scenario.readings[position].received_at <= tick:
            reading = scenario.readings[position]
            previous = latest.get(reading.sensor_id)
            if previous is None or reading.observed_at > previous.observed_at:
                latest[reading.sensor_id] = reading
            position += 1
        zone_reports = []
        for zone in scenario.zones:
            estimates = {kind: _fuse(kind, bindings[zone.id, kind], latest, tick) for kind in KINDS}
            decisions = {
                "thermal": _decide(zone, estimates["temperature"]),
                "ventilation": _decide(zone, estimates["co2"]),
            }
            for channel, decision in decisions.items():
                # Host-owned policy alone authorizes each channel. There is no
                # model/tool boundary or implicit physical actuation here.
                if decision.mode != "hold":
                    command_log.append({
                        "tick": timestamp(tick), "zone_id": zone.id, "channel": channel,
                        **_decision_json(decision), "simulation": True,
                    })
            zone_reports.append({
                "zone_id": zone.id,
                "estimates": {kind: _estimate_json(estimates[kind], tick) for kind in KINDS},
                "diagnostics": [record for kind in KINDS for record in _diagnostics(estimates[kind], bindings[zone.id, kind], latest, tick)],
                "alerts": _alerts(zone, estimates, tick),
                "decisions": {channel: _decision_json(decision) for channel, decision in decisions.items()},
            })
        ticks.append({"at": timestamp(tick), "zones": zone_reports})
    return {"mode": "simulation", "status": "completed", "ticks": ticks, "command_log": command_log}
