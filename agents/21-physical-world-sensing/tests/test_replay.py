"""Behavior checks for time, evidence ownership, fusion, and channel authority."""

from dataclasses import FrozenInstanceError
from decimal import Inexact, Rounded, localcontext
from importlib import resources
import json
import unittest

from physical_world_sensing import parse_scenario, run_replay
from helpers import NOW, add_sensor, reading, replay, scenario, zone_report


class ReplayTests(unittest.TestCase):
    def test_packaged_normal_has_independent_two_zone_control(self):
        raw = resources.files("physical_world_sensing").joinpath("scenarios", "normal.json").read_bytes()
        result = run_replay(parse_scenario(raw))
        first = result["ticks"][0]["zones"]
        self.assertEqual([zone["zone_id"] for zone in first], ["office", "store"])
        office, store = first
        self.assertEqual(office["estimates"]["temperature"]["value"], "27")
        self.assertEqual(office["estimates"]["co2"]["value"], "1200")
        self.assertEqual(store["estimates"]["temperature"]["value"], "15")
        self.assertEqual(store["estimates"]["co2"]["value"], "700")
        self.assertEqual([(command["mode"], command["percentage"]) for command in result["command_log"][:4]], [("cool", 100), ("ventilate", 20), ("heat", 60), ("idle", 0)])
        self.assertEqual(office["decisions"]["thermal"]["source_reading_ids"], ["r_office_t1", "r_office_t2"])
        self.assertEqual(len(result["command_log"]), 8)

    def test_latest_sensor_sample_is_not_message_weighted(self):
        doc = scenario(20)
        doc["readings"].append(reading("old", "temp", 10, "2026-10-23T08:59:00Z"))
        add_sensor(doc, "peer", "temperature", 24)
        output = zone_report(doc)["estimates"]["temperature"]
        self.assertEqual(output["value"], "22")
        self.assertEqual({item["reading_id"] for item in output["readings"]}, {"t", "r_peer"})

    def test_late_old_extreme_cannot_replace_latest_or_trigger_alert(self):
        doc = scenario(24)
        doc["readings"].append(reading("old_extreme", "temp", -40, "2026-10-23T08:58:00Z", "2026-10-23T09:01:00Z"))
        doc["ticks"].append("2026-10-23T09:01:00Z")
        result = replay(doc)
        for tick in result["ticks"]:
            zone = tick["zones"][0]
            self.assertEqual(zone["estimates"]["temperature"]["readings"][0]["reading_id"], "t")
            self.assertFalse(any(alert["code"] == "critical_temperature" for alert in zone["alerts"]))

    def test_file_order_does_not_change_output(self):
        doc = scenario()
        add_sensor(doc, "peer", "temperature", 24)
        expected = replay(doc)
        for collection in ("zones", "sensors", "readings"):
            doc[collection].reverse()
        self.assertEqual(replay(doc), expected)

    def test_received_time_gates_future_data(self):
        doc = scenario(22)
        doc["readings"][0]["received_at"] = "2026-10-23T09:01:00Z"
        doc["ticks"].append("2026-10-23T09:01:00Z")
        result = replay(doc)
        self.assertEqual(result["ticks"][0]["zones"][0]["decisions"]["thermal"]["mode"], "hold")
        self.assertEqual(result["ticks"][1]["zones"][0]["decisions"]["thermal"]["mode"], "idle")

    def test_readings_received_after_final_tick_remain_unused(self):
        doc = scenario()
        doc["readings"].append(reading("unused", "temp", 85, "2026-10-23T09:01:00Z"))
        self.assertEqual(zone_report(doc)["estimates"]["temperature"]["value"], "22")

    def test_freshness_is_inclusive_at_300_and_stale_at_301(self):
        doc = scenario(27, 1200)
        doc["readings"][0]["observed_at"] = "2026-10-23T08:55:00Z"
        doc["ticks"].append("2026-10-23T09:00:01Z")
        result = replay(doc)
        first, second = [tick["zones"][0] for tick in result["ticks"]]
        self.assertEqual(first["estimates"]["temperature"]["readings"][0]["age_seconds"], 300)
        self.assertEqual(second["estimates"]["temperature"]["quality"], "unavailable")
        self.assertIsNone(second["estimates"]["temperature"]["value"])
        self.assertEqual(second["decisions"]["thermal"]["mode"], "hold")
        self.assertEqual(second["decisions"]["ventilation"]["mode"], "ventilate")
        self.assertEqual(len(result["command_log"]), 3)

    def test_partial_coverage_retains_usable_mean_and_diagnostics(self):
        doc = scenario(24)
        add_sensor(doc, "missing", "temperature", 22)
        doc["readings"].pop()
        add_sensor(doc, "stale", "temperature", 20, "2026-10-23T08:54:59Z")
        output = zone_report(doc)
        estimate = output["estimates"]["temperature"]
        self.assertEqual((estimate["value"], estimate["registered_count"], estimate["eligible_count"]), ("24", 3, 1))
        self.assertEqual({item["code"] for item in output["diagnostics"]}, {"missing_reading", "stale_reading"})

    def test_conflict_rejects_only_affected_channel_and_retains_critical(self):
        doc = scenario(5, 1250)
        add_sensor(doc, "hot", "temperature", 35)
        output = zone_report(doc)
        self.assertEqual(output["estimates"]["temperature"]["quality"], "conflict")
        self.assertIsNone(output["estimates"]["temperature"]["value"])
        self.assertEqual(output["decisions"]["thermal"]["mode"], "hold")
        self.assertEqual(output["decisions"]["ventilation"]["percentage"], 25)
        critical = [item["reading_ids"] for item in output["alerts"] if item["code"] == "critical_temperature"]
        self.assertEqual({tuple(ids) for ids in critical}, {("t",), ("r_hot",)})

    def test_co2_conflict_suppresses_ventilation_and_high_co2_alert(self):
        doc = scenario(24, 1000)
        add_sensor(doc, "carbon_peer", "co2", 1500)
        output = zone_report(doc)
        self.assertEqual(output["decisions"]["thermal"]["mode"], "cool")
        self.assertEqual(output["decisions"]["ventilation"]["mode"], "hold")
        self.assertFalse(any(item["code"] == "high_co2" for item in output["alerts"]))

    def test_spread_equality_usable_but_any_excess_conflicts(self):
        for kind, base, equal, excess in [("temperature", 20, 24, 24.001), ("co2", 1000, 1400, 1400.001)]:
            with self.subTest(kind=kind):
                doc = scenario(base if kind == "temperature" else 22, base if kind == "co2" else 1000)
                add_sensor(doc, "peer", kind, equal)
                self.assertEqual(zone_report(doc)["estimates"][kind]["quality"], "ok")
                doc["readings"][-1]["value"] = excess
                self.assertEqual(zone_report(doc)["estimates"][kind]["quality"], "conflict")

    def test_deadband_boundaries_and_saturation(self):
        for value, mode, percentage in [(21, "idle", 0), (23, "idle", 0), (20.999, "heat", 20), (23.001, "cool", 20), (-40, "heat", 100), (85, "cool", 100)]:
            with self.subTest(value=value):
                decision = zone_report(scenario(value))["decisions"]["thermal"]
                self.assertEqual((decision["mode"], decision["percentage"]), (mode, percentage))

    def test_ventilation_floor_including_positive_zero_and_saturation(self):
        for value, mode, percentage in [(1000, "idle", 0), (1000.001, "ventilate", 0), (1009.999, "ventilate", 0), (1010, "ventilate", 1), (10000, "ventilate", 100)]:
            with self.subTest(value=value):
                decision = zone_report(scenario(co2=value))["decisions"]["ventilation"]
                self.assertEqual((decision["mode"], decision["percentage"]), (mode, percentage))

    def test_repeating_mean_display_is_rounded_without_changing_exact_control(self):
        doc = scenario(23)
        add_sensor(doc, "peer_a", "temperature", 23)
        add_sensor(doc, "peer_b", "temperature", 23.001)
        output = zone_report(doc)
        self.assertEqual(output["estimates"]["temperature"]["value"], "23.000333")
        self.assertEqual((output["decisions"]["thermal"]["mode"], output["decisions"]["thermal"]["percentage"]), ("cool", 20))
        with localcontext() as context:
            context.prec = 2
            context.Emax = 1
            context.Emin = -1
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            self.assertEqual(zone_report(doc), output)
            self.assertTrue(context.traps[Inexact])
            self.assertEqual(context.Emax, 1)

    def test_half_even_estimate_display(self):
        for values, expected in [([22] * 15 + [22.001], "22.000062"), ([22] * 15 + [22.003], "22.000188")]:
            doc = scenario(values[0])
            for index, value in enumerate(values[1:]):
                add_sensor(doc, "peer_" + str(index), "temperature", value)
            self.assertEqual(zone_report(doc)["estimates"]["temperature"]["value"], expected)

    def test_occupancy_is_observed_or_and_schedule_utc_boundaries(self):
        for at, unexpected in [("2026-10-23T07:59:59Z", True), ("2026-10-23T08:00:00Z", False), ("2026-10-23T17:59:59Z", False), ("2026-10-23T18:00:00Z", True)]:
            doc = scenario(occupancy=0)
            doc["ticks"] = [at]
            for item in doc["readings"]:
                item["observed_at"] = item["received_at"] = at
            add_sensor(doc, "present", "occupancy", 1, at)
            output = zone_report(doc)
            self.assertEqual(output["estimates"]["occupancy"]["value"], "1")
            alerts = [item for item in output["alerts"] if item["code"] == "unexpected_occupancy"]
            self.assertEqual(bool(alerts), unexpected)
            if alerts:
                self.assertEqual(alerts[0]["reading_ids"], ["r_present"])

    def test_missing_occupancy_is_null_and_cannot_assert_absence(self):
        doc = scenario()
        doc["readings"].pop()
        output = zone_report(doc)
        self.assertIsNone(output["estimates"]["occupancy"]["value"])
        self.assertEqual(output["estimates"]["occupancy"]["quality"], "unavailable")

    def test_repeated_runs_have_no_retained_state(self):
        parsed = parse_scenario(json.dumps(scenario(24)))
        first = run_replay(parsed)
        empty = scenario()
        empty["readings"] = []
        self.assertEqual(replay(empty)["command_log"], [])
        self.assertEqual(run_replay(parsed), first)
        with self.assertRaises(FrozenInstanceError):
            parsed.zones[0].id = "changed"

    def test_every_packaged_scenario_completes_with_bounded_simulated_commands(self):
        for name in ("normal", "stale", "conflict", "late", "boundary"):
            with self.subTest(name=name):
                raw = resources.files("physical_world_sensing").joinpath("scenarios", name + ".json").read_bytes()
                result = run_replay(parse_scenario(raw))
                self.assertEqual((result["mode"], result["status"]), ("simulation", "completed"))
                for command in result["command_log"]:
                    self.assertIs(type(command["percentage"]), int)
                    self.assertTrue(0 <= command["percentage"] <= 100)
                    self.assertIs(command["simulation"], True)


if __name__ == "__main__":
    unittest.main()
