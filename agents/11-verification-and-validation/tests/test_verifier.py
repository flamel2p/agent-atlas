"""Observable verdict, authority, schema, and bound checks using synthetic data.

Temporary replacement snapshots are a test seam behind the private package path,
not a public authority override. Runtime consumers get only verify_document(bytes).
"""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import FrozenInstanceError
from decimal import Decimal, DefaultContext, Inexact, Overflow, ROUND_UP, Rounded, getcontext, localcontext
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from verification_agent import InputError, SourceError, verify_document
from verification_agent import verifier

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = Path(verifier.__file__).parent / "data" / "truth-v1.json"
RAW_SNAPSHOT = SNAPSHOT.read_bytes()
TRUTH = json.loads(RAW_SNAPSHOT)


def claim(**changes):
    value = {"id": "test-claim", "entity": "atlas", "metric": "latency_change",
             "period": "2026-Q3", "baseline_period": "2026-Q2", "value": "-5",
             "unit": "relative_percent"}
    value.update(changes)
    return value


def document(*claims, as_of="2026-10-21"):
    return json.dumps({"as_of": as_of, "claims": list(claims) or [claim()]}).encode()


@contextmanager
def source_bytes(payload):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "snapshot.json"
        path.write_bytes(payload)
        with patch.object(verifier, "_SNAPSHOT_PATH", path):
            yield


@contextmanager
def source(data):
    with source_bytes(json.dumps(data).encode()):
        yield


class VerdictTests(unittest.TestCase):
    def result(self, **changes):
        return verify_document(document(claim(**changes))).results[0]

    def test_exact_claims_scope_provenance_and_digest(self):
        report = verify_document((ROOT / "fixtures/claims.json").read_bytes())
        self.assertEqual(report.snapshot_version, "truth-v1")
        self.assertEqual(report.snapshot_sha256, sha256(RAW_SNAPSHOT).hexdigest())
        self.assertFalse(report.review_required)
        self.assertEqual(len(report.results), 4)
        for result in report.results:
            self.assertEqual((result.verdict, result.reason), ("confirmed", "exact_match"))
            self.assertEqual(result.expected_value, result.claim.quantity.value)
            self.assertEqual(result.difference, 0)
            for record in result.eligible_evidence:
                self.assertEqual(record.scope, result.claim.scope)
                self.assertEqual(record.quantity.unit, result.claim.quantity.unit)
        result = report.results[0]
        self.assertEqual([record.id for record in result.eligible_evidence],
                         ["latency-change-corroboration", "latency-change-primary"])
        self.assertEqual([item.reason for item in result.excluded_evidence],
                         ["expired", "not_yet_valid"])
        wire = report.as_dict()
        self.assertEqual(wire["results"][0]["expected_value"], "-5")
        self.assertEqual(wire["results"][0]["eligible_evidence"][0]["source"], "Synthetic release ledger")
        self.assertEqual(wire["results"][0]["excluded_evidence"][0]["evidence"]["value"], "-9")

    def test_all_documented_scenarios(self):
        expected = {
            "tolerance": "within_tolerance", "outside-tolerance": "outside_tolerance",
            "direction-reversed": "direction_reversed", "small-sign-reversal": "direction_reversed",
            "unit-mismatch": "unit_mismatch", "baseline-mismatch": "missing_evidence",
            "missing-evidence": "missing_evidence", "unknown-metric": "unknown_metric",
            "expired": "no_current_evidence", "future": "no_current_evidence",
            "conflict": "conflicting_evidence", "zero": "exact_match",
        }
        for name, reason in expected.items():
            with self.subTest(name=name):
                result = verify_document((ROOT / f"fixtures/scenarios/{name}.json").read_bytes()).results[0]
                self.assertEqual(result.reason, reason)

    def test_direction_precedes_deliberately_broad_tolerance(self):
        data = deepcopy(TRUTH)
        data["metrics"][0]["tolerance"] = "100"
        with source(data):
            for value in ("0.1", "5", "99"):
                with self.subTest(value=value):
                    result = self.result(value=value)
                    self.assertEqual((result.verdict, result.reason), ("contradicted", "direction_reversed"))
                    self.assertEqual(result.applied_tolerance, Decimal(100))

    def test_positive_expected_value_reversed(self):
        result = self.result(metric="adoption_change", unit="percentage_point", value="-2.5")
        self.assertEqual(result.reason, "direction_reversed")

    def test_zero_has_no_direction_and_normalizes(self):
        self.assertEqual(self.result(value="0").reason, "outside_tolerance")
        self.assertEqual(self.result(entity="tiny", value="0").reason, "within_tolerance")
        result = self.result(entity="quiet", value="-0.000000")
        self.assertEqual(result.reason, "exact_match")
        self.assertEqual(result.claim.as_dict()["value"], "0")
        self.assertEqual(self.result(entity="quiet", value="-0.1").reason, "within_tolerance")

    def test_inclusive_tolerance_and_one_decimal_step_outside(self):
        for value, reason, difference in [
            ("-4.5", "within_tolerance", "0.5"), ("-5.5", "within_tolerance", "0.5"),
            ("-4.499999", "outside_tolerance", "0.500001"),
            ("-5.500001", "outside_tolerance", "0.500001"),
        ]:
            with self.subTest(value=value):
                result = self.result(value=value)
                self.assertEqual(result.reason, reason)
                self.assertEqual(result.difference, Decimal(difference))
                self.assertEqual(result.verdict, "mostly_true" if reason == "within_tolerance" else "contradicted")

    def test_count_has_zero_tolerance(self):
        result = self.result(metric="resolved_tickets", baseline_period=None, value="121", unit="count")
        self.assertEqual(result.reason, "outside_tolerance")
        self.assertEqual(result.applied_tolerance, Decimal(0))

    def test_level_metric_tolerance(self):
        for value, reason in [("239", "within_tolerance"), ("241", "within_tolerance"), ("241.000001", "outside_tolerance")]:
            with self.subTest(value=value):
                self.assertEqual(self.result(metric="latency", baseline_period=None, unit="milliseconds", value=value).reason, reason)

    def test_ambient_decimal_context_cannot_change_result(self):
        expected = self.result(value="-4.499999").as_dict()
        with localcontext() as context:
            context.prec = 1
            context.rounding = ROUND_UP
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            actual = self.result(value="-4.499999").as_dict()
            self.assertEqual(context.prec, 1)
            self.assertEqual(context.rounding, ROUND_UP)
        self.assertEqual(expected, actual)

    def test_mutated_default_decimal_context_cannot_change_results_or_globals(self):
        expected = {value: self.result(value=value) for value in ("5", "-4.499999")}
        self.assertEqual(expected["5"].difference, Decimal("10"))
        self.assertEqual(expected["-4.499999"].difference, Decimal("0.500001"))
        attributes = ("prec", "rounding", "Emin", "Emax", "capitals", "clamp", "flags", "traps")

        def state(context):
            return tuple(dict(getattr(context, name)) if name in ("flags", "traps")
                         else getattr(context, name) for name in attributes)

        saved_default = DefaultContext.copy()
        caller = getcontext()
        caller_before = state(caller)
        for trap_overflow in (True, False):
            with self.subTest(trap_overflow=trap_overflow):
                try:
                    DefaultContext.prec = 1
                    DefaultContext.rounding = ROUND_UP
                    DefaultContext.Emin = 0
                    DefaultContext.Emax = 0
                    DefaultContext.capitals = 0
                    DefaultContext.clamp = 1
                    for signal in DefaultContext.flags:
                        DefaultContext.flags[signal] = True
                        DefaultContext.traps[signal] = trap_overflow
                    self.assertEqual(DefaultContext.traps[Overflow], trap_overflow)
                    default_before = state(DefaultContext)
                    for value, expected_result in expected.items():
                        actual = self.result(value=value)
                        self.assertTrue(actual.difference.is_finite())
                        self.assertEqual(actual, expected_result)
                        self.assertIs(getcontext(), caller)
                        self.assertEqual(state(caller), caller_before)
                        self.assertEqual(state(DefaultContext), default_before)
                finally:
                    # Restore the shared object even when the regression raises.
                    for name in attributes:
                        setattr(DefaultContext, name, getattr(saved_default, name))

    def test_maximum_decimal_difference_is_exact(self):
        data = deepcopy(TRUTH)
        for record in data["records"]:
            if record["entity"] == "atlas" and record["metric"] == "latency_change":
                record["value"] = "-999999999999.999999"
        with source(data):
            result = self.result(value="999999999999.999999")
        self.assertEqual(result.difference, Decimal("1999999999999.999998"))
        self.assertEqual(result.reason, "direction_reversed")

    def test_missing_scope_never_borrows_records(self):
        for changes in [{"entity": "unknown"}, {"period": "2026-Q4"}, {"baseline_period": "2026-Q1"}]:
            with self.subTest(changes=changes):
                result = self.result(**changes)
                self.assertEqual(result.reason, "missing_evidence")
                self.assertEqual(result.eligible_evidence, ())
                self.assertIsNone(result.expected_value)
                self.assertIsNone(result.difference)
                self.assertIsNone(result.applied_tolerance)

    def test_unknown_metric_allows_both_baseline_shapes(self):
        for baseline in (None, "2026-Q1"):
            with self.subTest(baseline=baseline):
                result = self.result(metric="unknown", baseline_period=baseline, value="-1.5", unit="count")
                self.assertEqual(result.reason, "unknown_metric")
                self.assertIsNone(result.expected_value)

    def test_dimensions_never_compare_even_if_numbers_match(self):
        for changes in [{"unit": "percentage_point"},
                        {"metric": "adoption_change", "value": "2.5", "unit": "relative_percent"},
                        {"metric": "latency", "baseline_period": None, "value": "240", "unit": "count"}]:
            with self.subTest(changes=changes):
                result = self.result(**changes)
                self.assertEqual(result.reason, "unit_mismatch")
                self.assertIsNone(result.difference)
                self.assertIsNone(result.expected_value)
                self.assertEqual(result.eligible_evidence, ())

    def test_numeric_domains_do_not_apply_to_mismatched_units(self):
        for changes in [
            {"metric": "resolved_tickets", "unit": "milliseconds", "baseline_period": None, "value": "-0.5"},
            {"metric": "adoption_change", "unit": "relative_percent", "value": "500"},
        ]:
            with self.subTest(changes=changes):
                self.assertEqual(self.result(**changes).reason, "unit_mismatch")

    def test_baseline_shape_still_applies_to_mismatched_units(self):
        for changes in [{"unit": "percentage_point", "baseline_period": None},
                        {"metric": "latency", "unit": "relative_percent"}]:
            with self.subTest(changes=changes), self.assertRaises(InputError) as caught:
                self.result(**changes)
            self.assertEqual(caught.exception.code, "invalid_baseline")

    def test_validity_boundaries_are_inclusive(self):
        for as_of in ("2026-10-01", "2026-12-31"):
            with self.subTest(as_of=as_of):
                result = verify_document(document(as_of=as_of)).results[0]
                self.assertEqual(result.reason, "exact_match")
                self.assertEqual(len(result.eligible_evidence), 2)

    def test_expired_and_future_records_remain_auditable(self):
        for entity, reason in [("archive", "expired"), ("preview", "not_yet_valid")]:
            with self.subTest(entity=entity):
                result = self.result(entity=entity)
                self.assertEqual(result.reason, "no_current_evidence")
                self.assertIsNone(result.expected_value)
                self.assertEqual(result.excluded_evidence[0].reason, reason)
                self.assertEqual(result.excluded_evidence[0].evidence.scope.entity, entity)

    def test_conflicts_precede_tolerance_and_keep_all_records(self):
        result = self.result(entity="fork")
        self.assertEqual(result.reason, "conflicting_evidence")
        self.assertEqual([item.quantity.value for item in result.eligible_evidence], [Decimal("-4.9"), Decimal("-5")])
        self.assertIsNone(result.expected_value)
        self.assertIsNone(result.difference)
        self.assertIsNone(result.applied_tolerance)
        data = deepcopy(TRUTH)
        data["records"].reverse()
        with source(data):
            self.assertEqual(self.result(entity="fork"), result)

    def test_excluded_conflicts_do_not_defeat_eligible_agreement(self):
        result = self.result()
        self.assertEqual(result.reason, "exact_match")
        self.assertEqual(len(result.excluded_evidence), 2)
        self.assertNotEqual(result.excluded_evidence[0].evidence.quantity.value, result.expected_value)

    def test_normalized_equal_values_corroborate(self):
        data = deepcopy(TRUTH)
        data["records"][1]["value"] = "-5.000000"
        with source(data):
            result = self.result()
        self.assertEqual(result.reason, "exact_match")
        self.assertEqual(len(result.eligible_evidence), 2)

    def test_mixed_order_review_and_repeatability(self):
        payload = (ROOT / "fixtures/scenarios/mixed.json").read_bytes()
        before = SNAPSHOT.read_bytes()
        report = verify_document(payload)
        self.assertEqual([result.claim.id for result in report.results], ["latency-fall", "approximate", "reversed", "conflicting"])
        self.assertEqual([result.verdict for result in report.results], ["confirmed", "mostly_true", "contradicted", "unverified"])
        self.assertTrue(report.review_required)
        self.assertEqual(report, verify_document(payload))
        self.assertEqual(SNAPSHOT.read_bytes(), before)
        self.assertEqual(payload, (ROOT / "fixtures/scenarios/mixed.json").read_bytes())

    def test_report_is_immutable_and_serialization_is_detached(self):
        report = verify_document(document())
        with self.assertRaises(FrozenInstanceError):
            report.results = ()
        with self.assertRaises(FrozenInstanceError):
            report.results[0].claim.scope.entity = "changed"
        wire = report.as_dict()
        wire["results"][0]["claim"]["value"] = "999"
        self.assertEqual(report.results[0].claim.quantity.value, Decimal(-5))

    def test_snapshot_digest_tracks_exact_bytes(self):
        with source_bytes(RAW_SNAPSHOT + b" \n"):
            report = verify_document(document())
        self.assertEqual(report.snapshot_sha256, sha256(RAW_SNAPSHOT + b" \n").hexdigest())
        self.assertNotEqual(report.snapshot_sha256, sha256(RAW_SNAPSHOT).hexdigest())
        self.assertFalse(report.review_required)


class RequestValidationTests(unittest.TestCase):
    def rejects(self, payload):
        with self.assertRaises(InputError):
            verify_document(payload)

    def test_schema_types_and_closed_fields(self):
        good = json.loads(document())
        invalid = [[], None, True, "text", 1, {}, {**good, "unknown": 1},
                   {"claims": good["claims"]}, {"as_of": good["as_of"]},
                   {**good, "claims": {}}, {**good, "claims": [None]},
                   {**good, "claims": [{**claim(), "tolerance": "10"}]},
                   {**good, "claims": [{key: value for key, value in claim().items() if key != "value"}]}]
        for value in invalid:
            with self.subTest(value=value):
                self.rejects(json.dumps(value).encode())

    def test_json_and_encoding_fail_atomically(self):
        for payload in [b"", b"\xff", b"{} {}", b'{"as_of":"2026-10-21","claims":[],"claims":[]}',
                        document().replace(b'"value": "-5"', b'"value": "-5", "value": "-5"'),
                        b'{"claims":NaN}', b'{"claims":Infinity}', b'{"claims":-Infinity}',
                        b"[" * 3000 + b"]" * 3000]:
            with self.subTest(prefix=payload[:50]):
                self.rejects(payload)

    def test_wrong_public_operation_type(self):
        for value in ("{}", None, {}, bytearray(document())):
            with self.subTest(kind=type(value).__name__):
                self.rejects(value)

    def test_decimal_grammar_and_type(self):
        for value in ["00", "01", "-01", "+1", " 1", "1 ", "1e2", "NaN", "Infinity", "-Infinity", ".5", "1.",
                      "1.1234567", "1000000000000", "١", "１", "-", "", 1, 1.5, True, False, None, [], {}]:
            with self.subTest(value=value):
                self.rejects(document(claim(value=value)))

    def test_valid_decimal_edges(self):
        for value in ["0", "-0", "999999999999.999999", "-999999999999.999999", "0.000001"]:
            with self.subTest(value=value):
                self.assertEqual(len(verify_document(document(claim(metric="unknown", value=value))).results), 1)

    def test_identifier_grammar(self):
        for field in ("id", "entity", "metric"):
            for value in ["", "1atlas", "Atlas", "atlas.name", "é", "a" * 65, "a\n", True, [], None]:
                with self.subTest(field=field, value=value):
                    self.rejects(document(claim(**{field: value})))
        self.assertEqual(len(verify_document(document(claim(entity="a" * 64))).results), 1)

    def test_dates_require_exact_calendar_form(self):
        for value in ["20261021", "2026-1-21", "2026-10-1", "2026-02-29", "2026-13-01", "0000-01-01", "2026-10-21Z",
                      "2026-10-21T00:00:00", "２０２６-10-21", "2026-10-21\n", 20261021, True, None]:
            with self.subTest(value=value):
                self.rejects(document(as_of=value))
        self.assertEqual(verify_document(document(as_of="2024-02-29")).as_of.isoformat(), "2024-02-29")

    def test_period_and_baseline_grammar(self):
        for field in ("period", "baseline_period"):
            for value in ["2026-Q0", "2026-Q5", "2026-q3", "0000-Q1", "202-Q3", "10000-Q1", "２０２６-Q1", "2026-Q2\n", True, 2026, []]:
                with self.subTest(field=field, value=value):
                    self.rejects(document(claim(**{field: value})))
        for value in ["2026-Q3", "2026-Q4", "2027-Q1", None]:
            with self.subTest(baseline=value):
                self.rejects(document(claim(baseline_period=value)))
        self.rejects(document(claim(period=None)))
        report = verify_document(document(claim(period="9999-Q4", baseline_period="0001-Q1")))
        self.assertEqual(report.results[0].reason, "missing_evidence")

    def test_unit_tags_are_closed(self):
        for unit in ["percent", "%", "COUNT", "", None, [], True]:
            with self.subTest(unit=unit):
                self.rejects(document(claim(unit=unit)))

    def test_known_domains_and_baseline_shape(self):
        for metric, unit, baseline, value in [
            ("latency", "milliseconds", None, "-0.000001"),
            ("resolved_tickets", "count", None, "1.5"),
            ("resolved_tickets", "count", None, "-1"),
            ("adoption_change", "percentage_point", "2026-Q2", "100.000001"),
            ("adoption_change", "percentage_point", "2026-Q2", "-100.000001"),
            ("latency", "milliseconds", "2026-Q2", "240"),
        ]:
            with self.subTest(metric=metric, value=value):
                self.rejects(document(claim(metric=metric, unit=unit, baseline_period=baseline, value=value)))
        for value in ("100", "-100"):
            self.assertEqual(len(verify_document(document(claim(metric="adoption_change", unit="percentage_point", value=value))).results), 1)
        self.assertEqual(verify_document(document(claim(metric="resolved_tickets", unit="count", baseline_period=None, value="120.000000"))).results[0].reason, "exact_match")

    def test_claim_count_and_unique_ids(self):
        for count in (0, 33):
            self.rejects(json.dumps({"as_of": "2026-10-21", "claims": [claim(id=f"c{i}") for i in range(count)]}).encode())
        self.rejects(document(claim(), claim()))
        report = verify_document(document(*(claim(id=f"c{i}") for i in range(32))))
        self.assertEqual(len(report.results), 32)

    def test_size_bound_including_exact_limit(self):
        payload = document()
        self.assertFalse(verify_document(payload + b" " * (65_536 - len(payload))).review_required)
        self.rejects(payload + b" " * (65_537 - len(payload)))

    def test_late_invalid_claim_never_returns_partial_report(self):
        with self.assertRaises(InputError), patch.object(verifier, "_check") as check:
            verify_document(document(claim(), claim(id="invalid", metric="latency", unit="milliseconds", baseline_period=None, value="-1")))
        check.assert_not_called()


class SourceValidationTests(unittest.TestCase):
    def rejects(self, data):
        with source(data), self.assertRaises(SourceError):
            verify_document(document())

    def test_closed_root_and_rule_schema(self):
        for data in [{}, [], None, {**TRUTH, "override": True}, {**TRUTH, "version": "v.1"}, {**TRUTH, "version": 1},
                     {**TRUTH, "metrics": []}, {**TRUTH, "metrics": {}}, {**TRUTH, "records": []}, {**TRUTH, "records": {}}]:
            with self.subTest(data_type=type(data).__name__):
                self.rejects(data)
        for field, value in [("unit", "percent"), ("unit", []), ("baseline", None), ("domain", "anything"),
                             ("domain", []), ("tolerance", "-0.1"), ("tolerance", 1), ("metric", "Bad")]:
            data = deepcopy(TRUTH)
            data["metrics"][0][field] = value
            with self.subTest(field=field, value=value):
                self.rejects(data)
        data = deepcopy(TRUTH)
        data["metrics"][0]["unknown"] = 1
        self.rejects(data)

    def test_rule_and_record_limits_and_duplicates(self):
        data = deepcopy(TRUTH)
        data["metrics"].append(data["metrics"][0])
        self.rejects(data)
        data = deepcopy(TRUTH)
        data["records"].append(data["records"][0])
        self.rejects(data)
        for field, count in [("metrics", 17), ("records", 257)]:
            data = deepcopy(TRUTH)
            data[field] = [data[field][0]] * count
            self.rejects(data)

    def test_maximum_rules_and_records_are_accepted(self):
        data = deepcopy(TRUTH)
        data["metrics"] += [{**data["metrics"][0], "metric": f"extra{i}"} for i in range(12)]
        data["records"] = [{**data["records"][0], "id": f"record{i:03}"} for i in range(256)]
        with source(data):
            report = verify_document(document())
        self.assertFalse(report.review_required)
        self.assertEqual(len(report.results[0].eligible_evidence), 256)

    def test_entire_source_is_validated_even_unmatched_records(self):
        for changes in [
            {"entity": "invalid.entity"}, {"metric": "unknown"}, {"unit": "milliseconds"},
            {"value": "+5"}, {"value": 5}, {"baseline_period": None},
            {"valid_from": "2026-12-31", "valid_through": "2026-01-01"},
            {"valid_from": "2026-02-30"}, {"source": ""}, {"source": " leading"},
            {"source": "x\nsecret"}, {"source": "x\ud800"}, {"source": "x" * 121},
            {"source": True}, {"unknown": "field"},
        ]:
            data = deepcopy(TRUTH)
            data["records"][-1].update(changes)
            with self.subTest(changes=changes):
                self.rejects(data)
        data = deepcopy(TRUTH)
        del data["records"][-1]["source"]
        self.rejects(data)

    def test_source_numeric_domains(self):
        for index, value in [(4, "100.1"), (5, "-1"), (5, "1.5"), (6, "-1")]:
            data = deepcopy(TRUTH)
            data["records"][index]["value"] = value
            self.rejects(data)

    def test_invalid_json_utf8_depth_and_duplicate_keys(self):
        for payload in [b"\xff", b"not-json", b"[" * 3000 + b"]" * 3000,
                        RAW_SNAPSHOT.replace(b'"version": "truth-v1"', b'"version": "truth-v1", "version": "truth-v1"'),
                        RAW_SNAPSHOT.replace(b'"tolerance": "0.5"', b'"tolerance": NaN')]:
            with self.subTest(prefix=payload[:30]), source_bytes(payload), self.assertRaises(SourceError):
                verify_document(document())

    def test_source_size_bound_including_exact_limit(self):
        with source_bytes(RAW_SNAPSHOT + b" " * (262_144 - len(RAW_SNAPSHOT))):
            self.assertFalse(verify_document(document()).review_required)
        with source_bytes(b" " * 262_145), self.assertRaises(SourceError) as caught:
            verify_document(document())
        self.assertEqual(caught.exception.code, "too_large")

    def test_corrupt_source_prevents_any_result(self):
        data = deepcopy(TRUTH)
        data["records"][-1]["value"] = "oops"
        with source(data), patch.object(verifier, "_check") as check, self.assertRaises(SourceError):
            verify_document(document())
        check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
