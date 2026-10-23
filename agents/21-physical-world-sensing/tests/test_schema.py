"""Trust-boundary checks reject complete invalid documents before replay."""

import copy
import json
import unittest

from physical_world_sensing import ScenarioError, parse_scenario
from helpers import NOW, add_sensor, reading, scenario


class SchemaTests(unittest.TestCase):
    def rejects(self, document):
        with self.assertRaises(ScenarioError):
            parse_scenario(json.dumps(document))

    def test_exact_root_and_record_fields(self):
        for collection in (None, "zones", "sensors", "readings"):
            for operation in ("extra", "missing"):
                with self.subTest(collection=collection, operation=operation):
                    doc = scenario()
                    target = doc if collection is None else doc[collection][0]
                    if operation == "extra":
                        target["unknown"] = 1
                    else:
                        target.pop(next(iter(target)))
                    self.rejects(doc)

    def test_wrong_collection_and_record_shapes(self):
        for collection in ("zones", "sensors", "readings", "ticks"):
            for value in (None, {}, "bad", True):
                doc = scenario()
                doc[collection] = value
                self.rejects(doc)
        for collection in ("zones", "sensors", "readings"):
            doc = scenario()
            doc[collection][0] = []
            self.rejects(doc)

    def test_duplicate_object_keys_and_nonfinite_literals(self):
        raw = json.dumps(scenario())
        for invalid in (raw.replace('"zones":', '"zones": [], "zones":', 1), raw.replace('"value": 22', '"value": NaN'), raw.replace('"value": 22', '"value": Infinity'), raw.replace('"value": 22', '"value": -Infinity')):
            with self.assertRaises(ScenarioError):
                parse_scenario(invalid)

    def test_nonfinite_and_boolean_numbers(self):
        for value in (float("nan"), float("inf"), -float("inf"), True, False, None, "22"):
            doc = scenario(value)
            self.rejects(doc)
        for field in ("target_min_c", "target_max_c", "co2_limit_ppm", "occupied_start_hour", "occupied_end_hour"):
            doc = scenario()
            doc["zones"][0][field] = True
            self.rejects(doc)

    def test_numeric_precision_and_range(self):
        for value in (-40.001, 85.001, 22.0001, 0.1234567890123):
            self.rejects(scenario(value))
        for value in (249.999, 10000.001):
            self.rejects(scenario(co2=value))
        for value in (-1, 0.5, 2):
            self.rejects(scenario(occupancy=value))
        raw = json.dumps(scenario()).replace('"value": 22', '"value": 22.000000000000')
        with self.assertRaises(ScenarioError):
            parse_scenario(raw)

    def test_boundary_values_are_accepted_and_decimal_input_is_preserved(self):
        for value in (-40, 85, -0.0, 22.125):
            parsed = parse_scenario(json.dumps(scenario(value)))
            self.assertEqual(str(next(reading for reading in parsed.readings if reading.id == "t").value), str(value))
        for value in (250, 10000):
            parse_scenario(json.dumps(scenario(co2=value)))

    def test_duplicate_ids_within_each_collection(self):
        for collection in ("zones", "sensors", "readings"):
            doc = scenario()
            doc[collection].append(copy.deepcopy(doc[collection][0]))
            self.rejects(doc)

    def test_duplicate_sensor_observation_pair_despite_different_reading_id(self):
        doc = scenario()
        doc["readings"].append(reading("different", "temp", 23))
        self.rejects(doc)

    def test_identifier_grammar(self):
        for bad in ("", "A", "1abc", "space here", "a/b", "a" * 33, "é", None, 123):
            doc = scenario()
            doc["readings"][0]["id"] = bad
            self.rejects(doc)

    def test_unknown_bindings_kinds_and_missing_metric(self):
        doc = scenario()
        doc["sensors"][0]["zone_id"] = "elsewhere"
        self.rejects(doc)
        doc = scenario()
        doc["readings"][0]["sensor_id"] = "missing"
        self.rejects(doc)
        for kind in ("humidity", [], None, 1):
            doc = scenario()
            doc["sensors"][0]["kind"] = kind
            self.rejects(doc)
        doc = scenario()
        doc["sensors"].pop()
        doc["readings"].pop()
        self.rejects(doc)

    def test_invalid_targets_and_schedules(self):
        for field, value in [("target_min_c", 9.999), ("target_max_c", 35.001), ("target_min_c", 24), ("target_min_c", 25), ("co2_limit_ppm", 399.999), ("co2_limit_ppm", 2000.001), ("occupied_start_hour", -1), ("occupied_end_hour", 25), ("occupied_start_hour", 18), ("occupied_start_hour", 20), ("occupied_start_hour", 8.0)]:
            with self.subTest(field=field, value=value):
                doc = scenario()
                doc["zones"][0][field] = value
                self.rejects(doc)

    def test_timestamps_require_exact_utc_second_format_and_year_range(self):
        for bad in ("2026-10-23T09:00:00+00:00", "2026-10-23T09:00:00.0Z", "2026-10-23t09:00:00z", "2026-02-30T09:00:00Z", "2026-10-23T09:00:60Z", "1999-12-31T23:59:59Z", "2101-01-01T00:00:00Z", "2026-10-23", None, 123):
            doc = scenario()
            doc["ticks"] = [bad]
            self.rejects(doc)
        for valid in ("2000-01-01T00:00:00Z", "2100-12-31T23:59:59Z", "2028-02-29T00:00:00Z"):
            doc = scenario()
            doc["ticks"] = [valid]
            parse_scenario(json.dumps(doc))

    def test_observation_cannot_follow_receipt_even_if_after_last_tick(self):
        doc = scenario()
        doc["readings"].append(reading("invalid_future", "temp", 23, "2026-10-23T10:01:00Z", "2026-10-23T10:00:00Z"))
        self.rejects(doc)

    def test_tick_order_uniqueness_and_one_day_span(self):
        for ticks in ([NOW, NOW], ["2026-10-23T09:01:00Z", NOW], [NOW, "2026-10-24T09:00:01Z"]):
            doc = scenario()
            doc["ticks"] = ticks
            self.rejects(doc)
        doc = scenario()
        doc["ticks"] = [NOW, "2026-10-24T09:00:00Z"]
        parse_scenario(json.dumps(doc))

    def test_collection_lower_and_upper_bounds(self):
        for collection in ("zones", "sensors", "ticks"):
            doc = scenario()
            doc[collection] = []
            self.rejects(doc)
        for collection, maximum in (("zones", 8), ("sensors", 64), ("readings", 512), ("ticks", 64)):
            doc = scenario()
            doc[collection] = [doc[collection][0]] * (maximum + 1)
            self.rejects(doc)
        doc = scenario()
        doc["readings"] = []
        parse_scenario(json.dumps(doc))

    def test_malformed_overdeep_non_utf8_and_oversize_json(self):
        for raw in ("{", "[]", "null", "{} {}", b"\xff", "[" * 17 + "]" * 17, " " * 262145, '"\\ud800"'):
            with self.subTest(raw=repr(raw[:20])):
                with self.assertRaises(ScenarioError):
                    parse_scenario(raw)
        with self.assertRaises(ScenarioError):
            parse_scenario(scenario())


if __name__ == "__main__":
    unittest.main()
