"""Independently check public replay reports through real CLI subprocesses.

This oracle imports no agent code. Authored inputs and hand-computed expectations
cover temporal causality, sensor weighting, independent channel authority, and
input/output failures. Run with the interpreter that owns the package to qualify.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def scenario() -> dict:
    """Return two synthetic zones with independently specified expected controls."""
    result = {"zones": [], "sensors": [], "readings": [], "ticks": ["2026-10-23T10:00:00Z"]}
    for zone, temperature, co2 in (("hall", 28, 1200), ("studio", 18, 700)):
        result["zones"].append({
            "id": zone, "target_min_c": 20, "target_max_c": 24,
            "co2_limit_ppm": 1000, "occupied_start_hour": 8, "occupied_end_hour": 18,
        })
        for kind, value in (("temperature", temperature), ("co2", co2), ("occupancy", 1)):
            sensor = zone + "_" + kind
            result["sensors"].append({"id": sensor, "zone_id": zone, "kind": kind})
            result["readings"].append({
                "id": "r_" + sensor, "sensor_id": sensor,
                "observed_at": result["ticks"][0], "received_at": result["ticks"][0], "value": value,
            })
    return result


def reading(data: dict, sensor: str) -> dict:
    return next(item for item in data["readings"] if item["sensor_id"] == sensor)


def add_temperature(data: dict, suffix: str, value: int | float) -> None:
    sensor = "hall_temp_" + suffix
    data["sensors"].append({"id": sensor, "zone_id": "hall", "kind": "temperature"})
    data["readings"].append({
        "id": "r_" + sensor, "sensor_id": sensor,
        "observed_at": data["ticks"][0], "received_at": data["ticks"][0], "value": value,
    })


def zone(report: dict, name: str = "hall", tick: int = 0) -> dict:
    return next(item for item in report["ticks"][tick]["zones"] if item["zone_id"] == name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, required=True)
    options = parser.parse_args()
    count = 0
    command = [sys.executable, "-m", "physical_world_sensing"]
    with tempfile.TemporaryDirectory(prefix="agent21-oracle-") as folder:
        root = Path(folder)
        input_file = root / "private-input.json"

        def invoke(args: list[str], *, success: bool = True, raw: bytes | None = None, env: dict | None = None) -> dict | None:
            nonlocal count
            if raw is not None:
                input_file.write_bytes(raw)
            process = subprocess.run(command + args, capture_output=True, timeout=8, env=env)
            count += 1
            assert str(root).encode() not in process.stdout + process.stderr, "private path leaked"
            assert b"Traceback" not in process.stderr, "traceback leaked"
            if not success:
                assert process.returncode == 2, (args, process.returncode, process.stderr)
                assert not process.stdout, "invalid input emitted successful or partial report"
                assert process.stderr, "failed input had no diagnostic"
                return None
            assert process.returncode == 0, (args, process.returncode, process.stderr)
            assert not process.stderr, process.stderr
            report = json.loads(process.stdout)
            assert report["mode"] == "simulation" and report["status"] == "completed"
            for entry in report["command_log"]:
                assert entry["simulation"] is True
                assert type(entry["percentage"]) is int and 0 <= entry["percentage"] <= 100
                assert entry["source_reading_ids"], "command lacks evidence"
            expected_log = []
            for tick in report["ticks"]:
                for current in tick["zones"]:
                    for metric in current["estimates"].values():
                        assert metric["eligible_count"] == len(metric["readings"])
                        assert len({r["sensor_id"] for r in metric["readings"]}) == metric["eligible_count"]
                        assert (metric["value"] is not None) == (metric["quality"] == "ok")
                        for evidence in metric["readings"]:
                            observed = datetime.fromisoformat(evidence["observed_at"].replace("Z", "+00:00"))
                            received = datetime.fromisoformat(evidence["received_at"].replace("Z", "+00:00"))
                            at = datetime.fromisoformat(tick["at"].replace("Z", "+00:00"))
                            assert observed <= received <= at
                            assert (at - observed).total_seconds() == evidence["age_seconds"]
                            assert 0 <= evidence["age_seconds"] <= 300
                    for channel, kind in (("thermal", "temperature"), ("ventilation", "co2")):
                        decision = current["decisions"][channel]
                        estimate = current["estimates"][kind]
                        assert (decision["mode"] == "hold") == (estimate["quality"] != "ok")
                        if decision["mode"] == "hold":
                            assert decision["percentage"] is None
                        else:
                            assert decision["source_reading_ids"] == [r["reading_id"] for r in estimate["readings"]]
                            expected_log.append({
                                "tick": tick["at"], "zone_id": current["zone_id"], "channel": channel,
                                "simulation": True, **decision,
                            })
            assert report["command_log"] == expected_log, "command log disagrees with tick decisions"
            return report

        def run(data: dict) -> dict:
            result = invoke(["--input", str(input_file)], raw=json.dumps(data).encode())
            assert isinstance(result, dict)
            return result

        normal = run(scenario())
        assert zone(normal)["estimates"]["temperature"]["value"] == "28"
        assert zone(normal)["decisions"]["thermal"]["mode"] == "cool"
        assert zone(normal)["decisions"]["thermal"]["percentage"] == 100
        assert zone(normal)["decisions"]["ventilation"]["percentage"] == 20
        assert zone(normal, "studio")["decisions"]["thermal"]["mode"] == "heat"
        assert zone(normal, "studio")["decisions"]["thermal"]["percentage"] == 80
        assert len(normal["command_log"]) == 4
        assert run(scenario()) == normal, "replay differs across processes"

        for value, mode, percent in ((21, "idle", 0), (23, "idle", 0), (23.001, "cool", 20), (23.15, "cool", 23), (20.999, "heat", 20), (85, "cool", 100), (-40, "heat", 100)):
            data = scenario()
            reading(data, "hall_temperature")["value"] = value
            decision = zone(run(data))["decisions"]["thermal"]
            assert (decision["mode"], decision["percentage"]) == (mode, percent), (value, decision)

        for value, mode, percent in ((1000, "idle", 0), (1000.001, "ventilate", 0), (1010, "ventilate", 1), (10000, "ventilate", 100)):
            data = scenario()
            reading(data, "hall_co2")["value"] = value
            decision = zone(run(data))["decisions"]["ventilation"]
            assert (decision["mode"], decision["percentage"]) == (mode, percent)

        for age, quality in ((300, "ok"), (301, "unavailable")):
            data = scenario()
            reading(data, "hall_temperature")["observed_at"] = "2026-10-23T09:55:" + ("00Z" if age == 300 else "59Z")
            if age == 301:
                reading(data, "hall_temperature")["observed_at"] = "2026-10-23T09:54:59Z"
            report = run(data)
            estimate = zone(report)["estimates"]["temperature"]
            assert estimate["quality"] == quality
            if quality == "unavailable":
                assert estimate["value"] is None
                assert zone(report)["decisions"]["thermal"]["mode"] == "hold"
                assert not any(c["zone_id"] == "hall" and c["channel"] == "thermal" for c in report["command_log"])
                assert zone(report)["decisions"]["ventilation"]["percentage"] == 20

        data = scenario()
        data["readings"] = [r for r in data["readings"] if r["sensor_id"] != "hall_temperature"]
        assert zone(run(data))["estimates"]["temperature"]["quality"] == "unavailable"

        data = scenario()
        add_temperature(data, "two", 24)
        for index in range(10):
            old = copy.deepcopy(reading(data, "hall_temperature"))
            old.update(id="old_" + str(index), observed_at="2026-10-23T09:59:" + str(index).zfill(2) + "Z", value=25)
            data["readings"].append(old)
        report = run(data)
        estimate = zone(report)["estimates"]["temperature"]
        assert estimate["value"] == "26" and estimate["eligible_count"] == 2
        assert {r["reading_id"] for r in estimate["readings"]} == {"r_hall_temperature", "r_hall_temp_two"}
        assert zone(report)["decisions"]["thermal"]["percentage"] == 80
        data["readings"].reverse()
        data["sensors"].reverse()
        data["zones"].reverse()
        assert run(data) == report, "input order changed decisions"

        data = scenario()
        reading(data, "hall_temperature")["value"] = 20
        add_temperature(data, "two", 20)
        add_temperature(data, "three", 21)
        report = run(data)
        assert zone(report)["estimates"]["temperature"]["value"] == "20.333333"
        assert zone(report)["decisions"]["thermal"]["percentage"] == 33

        for second, quality in ((32, "ok"), (32.001, "conflict"), (40, "conflict")):
            data = scenario()
            add_temperature(data, "two", second)
            report = run(data)
            assert zone(report)["estimates"]["temperature"]["quality"] == quality
            if quality == "conflict":
                assert zone(report)["decisions"]["thermal"]["mode"] == "hold"
            if second == 40:
                alert = next(a for a in zone(report)["alerts"] if a["code"] == "critical_temperature")
                assert alert["reading_ids"] == ["r_hall_temp_two"]

        for value, quality in ((800, "ok"), (799.999, "conflict")):
            data = scenario()
            data["sensors"].append({"id": "hall_co2_two", "zone_id": "hall", "kind": "co2"})
            extra = copy.deepcopy(reading(data, "hall_co2"))
            extra.update(id="r_hall_co2_two", sensor_id="hall_co2_two", value=value)
            data["readings"].append(extra)
            report = run(data)
            assert zone(report)["estimates"]["co2"]["quality"] == quality
            assert zone(report)["decisions"]["thermal"]["mode"] == "cool"
            if quality == "ok":
                assert zone(report)["estimates"]["co2"]["value"] == "1000"
                assert zone(report)["decisions"]["ventilation"]["percentage"] == 0

        data = scenario()
        data["sensors"].append({"id": "hall_temp_absent", "zone_id": "hall", "kind": "temperature"})
        report = run(data)
        assert zone(report)["estimates"]["temperature"]["registered_count"] == 2
        assert zone(report)["estimates"]["temperature"]["eligible_count"] == 1
        assert zone(report)["estimates"]["temperature"]["value"] == "28"
        assert any(d["code"] == "missing_reading" and d["sensor_ids"] == ["hall_temp_absent"] for d in zone(report)["diagnostics"])

        data = scenario()
        newer = reading(data, "hall_temperature")
        older = copy.deepcopy(newer)
        older.update(id="late_old", observed_at="2026-10-23T09:59:00Z", received_at="2026-10-23T10:01:00Z", value=40)
        future = copy.deepcopy(newer)
        future.update(id="future", observed_at="2026-10-23T10:02:00Z", received_at="2026-10-23T10:02:00Z", value=35)
        data["readings"].extend([older, future])
        data["ticks"].append("2026-10-23T10:01:00Z")
        report = run(data)
        for index in (0, 1):
            assert zone(report, tick=index)["estimates"]["temperature"]["value"] == "28"
            assert not any(a["code"] == "critical_temperature" for a in zone(report, tick=index)["alerts"])

        for hour, unexpected in ((7, True), (8, False), (17, False), (18, True)):
            data = scenario()
            stamp = f"2026-10-23T{hour:02d}:00:00Z"
            data["ticks"] = [stamp]
            for entry in data["readings"]:
                entry["observed_at"] = entry["received_at"] = stamp
            alerts = zone(run(data))["alerts"]
            assert any(a["code"] == "unexpected_occupancy" for a in alerts) == unexpected

        for primary, expected in ((1, "1"), (0, "0")):
            data = scenario()
            reading(data, "hall_occupancy")["value"] = primary
            data["sensors"].append({"id": "hall_occ_two", "zone_id": "hall", "kind": "occupancy"})
            extra = copy.deepcopy(reading(data, "hall_occupancy"))
            extra.update(id="r_occ_two", sensor_id="hall_occ_two", value=0)
            data["readings"].append(extra)
            assert zone(run(data))["estimates"]["occupancy"]["value"] == expected

        for name in ("normal", "stale", "conflict", "late", "boundary"):
            invoke(["--scenario", name])
        invoke([])

        mutations = [
            lambda d: d.update(extra=1),
            lambda d: d.update(ticks=[]),
            lambda d: d.update(ticks=d["ticks"] * 2),
            lambda d: d["ticks"].append("2026-10-24T10:00:01Z"),
            lambda d: d["readings"].append(copy.deepcopy(d["readings"][0])),
            lambda d: d["zones"].append(copy.deepcopy(d["zones"][0])),
            lambda d: d["sensors"][0].update(zone_id="unknown"),
            lambda d: d["sensors"][0].update(kind="humidity"),
            lambda d: d["readings"][0].update(value=True),
            lambda d: d["readings"][0].update(value=85.001),
            lambda d: d["readings"][0].update(value=20.0001),
            lambda d: d["readings"][0].update(value=float("nan")),
            lambda d: d["readings"][0].update(sensor_id="unknown"),
            lambda d: d["readings"][0].update(observed_at="2026-10-23T10:00:01Z"),
            lambda d: d["readings"][0].update(observed_at="2026-10-23T10:00:00+00:00"),
            lambda d: d["zones"][0].update(occupied_start_hour=18, occupied_end_hour=8),
            lambda d: d["zones"][0].update(target_min_c=24),
        ]
        for mutate in mutations:
            data = scenario()
            mutate(data)
            invoke(["--input", str(input_file)], success=False, raw=json.dumps(data).encode())

        duplicate_key = json.dumps(scenario()).replace('"zones":', '"zones": [], "zones":', 1).encode()
        valid_document = json.dumps(scenario()).encode()
        oversized = valid_document + b" " * (262145 - len(valid_document))
        for payload in (duplicate_key, b"[]", b"{", b"\xff", oversized, b"[" * 2000 + b"]" * 2000, b'{"zones":1e999999999999999999999}'):
            invoke(["--input", str(input_file)], success=False, raw=payload)
        invoke(["--scenario", "unknown"], success=False)
        invoke(["--input", str(input_file), "--scenario", "normal"], success=False)
        invoke(["--input", str(root / "missing")], success=False)
        invoke(["--input", str(root)], success=False)
        input_file.write_text(json.dumps(scenario()))
        link = root / "linked.json"
        link.symlink_to(input_file)
        invoke(["--input", str(link)], success=False)
        fifo = root / "pipe.json"
        os.mkfifo(fifo)
        invoke(["--input", str(fifo)], success=False)
        for args in ([], ["--help"]):
            read_fd, write_fd = os.pipe()
            os.close(read_fd)
            try:
                process = subprocess.run(command + args, stdout=write_fd, stderr=subprocess.PIPE, timeout=8)
                count += 1
                assert process.returncode == 2, ("broken output", process.returncode, process.stderr)
                assert b"Traceback" not in process.stderr
            finally:
                os.close(write_fd)

        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            process = subprocess.run(command + ["--scenario", "unknown"], stdout=subprocess.PIPE, stderr=write_fd, timeout=8)
            count += 1
            assert process.returncode == 2 and not process.stdout, ("failed error delivery", process.returncode)
        finally:
            os.close(write_fd)

        fault_root = root / "package-faults"
        package = fault_root / "physical_world_sensing"
        shutil.copytree(options.package_dir, package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        isolated_environment = {**os.environ, "PYTHONPATH": str(fault_root)}
        invoke(["--scenario", "normal"], env=isolated_environment)
        resource = package / "scenarios" / "normal.json"
        resource.unlink()
        invoke(["--scenario", "normal"], success=False, env=isolated_environment)
        resource.mkdir()
        invoke(["--scenario", "normal"], success=False, env=isolated_environment)
        resource.rmdir()
        resource.symlink_to(input_file)
        invoke(["--scenario", "normal"], success=False, env=isolated_environment)
        resource.unlink()
        os.mkfifo(resource)
        invoke(["--scenario", "normal"], success=False, env=isolated_environment)
        resource.unlink()
        resource.write_bytes(oversized)
        invoke(["--scenario", "normal"], success=False, env=isolated_environment)

    print(f"PASS: {count} independent CLI invocations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
