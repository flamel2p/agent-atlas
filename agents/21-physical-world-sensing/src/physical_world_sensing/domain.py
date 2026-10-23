"""Immutable records shared by validation and replay within this case.

A sensor binding fixes one metric and one zone. A reading records observation
time separately from arrival time, so replay can reject stale evidence without
pretending delayed messages arrived earlier. Scenario records own no live state.
The replay invocation alone owns the mutable latest-reading cache.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
from typing import Literal

Kind = Literal["temperature", "co2", "occupancy"]
Quality = Literal["ok", "unavailable", "conflict"]
KINDS: tuple[Kind, ...] = ("temperature", "co2", "occupancy")


@dataclass(frozen=True, slots=True)
class Zone:
    id: str
    target_min_c: Decimal
    target_max_c: Decimal
    co2_limit_ppm: Decimal
    occupied_start_hour: int
    occupied_end_hour: int


@dataclass(frozen=True, slots=True)
class Sensor:
    id: str
    zone_id: str
    kind: Kind


@dataclass(frozen=True, slots=True)
class Reading:
    id: str
    sensor_id: str
    observed_at: datetime
    received_at: datetime
    value: Decimal


@dataclass(frozen=True, slots=True)
class Scenario:
    zones: tuple[Zone, ...]
    sensors: tuple[Sensor, ...]
    readings: tuple[Reading, ...]
    ticks: tuple[datetime, ...]


@dataclass(frozen=True, slots=True)
class Estimate:
    """Fusion result retaining exact arithmetic and selected evidence.

    Fusion combines at most one fresh reading per registered sensor. Coverage
    counts describe observed evidence, not sensor health or physical safety.
    A missing/conflicting estimate has no value; an observed zero is distinct.
    """

    kind: Kind
    quality: Quality
    value: Fraction | None
    registered_count: int
    readings: tuple[Reading, ...]


@dataclass(frozen=True, slots=True)
class Decision:
    """A simulated desired command, or a hold without command authority.

    Holding one channel never authorizes or suppresses the independent channel.
    There is no actuator delivery, acknowledgment, or physical-state guarantee.
    """

    mode: Literal["hold", "idle", "heat", "cool", "ventilate"]
    percentage: int | None
    reason: str
    source_reading_ids: tuple[str, ...]
