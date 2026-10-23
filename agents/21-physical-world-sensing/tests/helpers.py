"""Small independent scenario builders for observable replay behavior checks."""

import json

from physical_world_sensing import parse_scenario, run_replay

NOW = "2026-10-23T09:00:00Z"


def reading(id, sensor, value, observed=NOW, received=None):
    return {"id": id, "sensor_id": sensor, "value": value, "observed_at": observed, "received_at": received or observed}


def scenario(temperature=22, co2=1000, occupancy=0):
    return {
        "zones": [{"id": "office", "target_min_c": 20, "target_max_c": 24, "co2_limit_ppm": 1000, "occupied_start_hour": 8, "occupied_end_hour": 18}],
        "sensors": [
            {"id": "temp", "zone_id": "office", "kind": "temperature"},
            {"id": "carbon", "zone_id": "office", "kind": "co2"},
            {"id": "occupied", "zone_id": "office", "kind": "occupancy"},
        ],
        "readings": [reading("t", "temp", temperature), reading("c", "carbon", co2), reading("o", "occupied", occupancy)],
        "ticks": [NOW],
    }


def replay(document):
    return run_replay(parse_scenario(json.dumps(document)))


def zone_report(document):
    return replay(document)["ticks"][0]["zones"][0]


def add_sensor(document, id, kind, value, observed=NOW, received=None):
    document["sensors"].append({"id": id, "zone_id": "office", "kind": kind})
    document["readings"].append(reading("r_" + id, id, value, observed, received))
