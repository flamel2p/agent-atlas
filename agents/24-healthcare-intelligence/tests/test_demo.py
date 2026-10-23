"""Observable arithmetic, evidence authority, strict inputs, and real CLI checks."""
import copy
from fractions import Fraction
from importlib.resources import files
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO

from healthcare_intelligence.boundary import InputFault, MAX_BYTES, parse_request
from healthcare_intelligence.cli import main
from healthcare_intelligence.domain import CONDITIONS, evaluate

FIXTURE = files("healthcare_intelligence").joinpath("fixtures/normal.json").read_bytes()


def fixture():
    return json.loads(FIXTURE)


def run(value):
    return evaluate(parse_request(json.dumps(value).encode())).to_json()


class EvidenceTests(unittest.TestCase):
    def test_expected_arithmetic_and_provenance(self):
        report = run(fixture())
        # Independently calculated weights .2, .015, .015 have total .23.
        self.assertEqual([item["exact"] for item in report["posterior"]], ["20/23", "3/46", "3/46"])
        self.assertEqual(sum(Fraction(item["exact"]) for item in report["posterior"]), 1)
        self.assertEqual(report["outcome"], "review_required")
        self.assertEqual(report["evidence"][0]["ticks"], "3/4")
        self.assertEqual(report["evidence"][0]["observed_at"], "2026-10-22T23:00:00Z")
        self.assertEqual(report["evidence"][0]["provenance"], [{"id": "know-glimmer", "source": "toy-almanac", "version": "v-one", "retrieved_at": "2026-10-20T00:00:00Z"}])
        self.assertEqual(report["review"], {"decision": "pending", "real_approval": False, "effect": "none"})

    def test_unit_equivalence_and_order(self):
        value = fixture()
        expected = run(value)
        value["observations"][0].update(value=0.75, unit="ticks")
        value["observations"].reverse()
        value["knowledge"].reverse()
        self.assertEqual(run(value), expected)

    def test_band_boundary(self):
        for value, band in ((0.499, "low"), (0.5, "high"), (1, "high"), (0, "low")):
            with self.subTest(value=value):
                data = fixture()
                data["observations"][0].update(value=value, unit="ticks")
                self.assertEqual(run(data)["evidence"][0]["band"], band)

    def test_identical_knowledge_is_not_repeated_evidence(self):
        value = fixture()
        expected = run(value)["posterior"]
        duplicate = copy.deepcopy(value["knowledge"][0])
        duplicate.update(id="second-source", source="other-toy", version="v-three")
        value["knowledge"].append(duplicate)
        report = run(value)
        self.assertEqual(report["posterior"], expected)
        self.assertEqual(len(report["evidence"][0]["provenance"]), 2)

    def test_all_review_transitions_are_simulated(self):
        for decision, outcome in (("pending", "review_required"), ("acknowledged", "simulated_reviewed"), ("rejected", "review_rejected")):
            with self.subTest(decision=decision):
                value = fixture()
                value["review"] = decision
                report = run(value)
                self.assertEqual(report["outcome"], outcome)
                self.assertIsNotNone(report["posterior"])
                self.assertFalse(report["review"]["real_approval"])
                self.assertEqual(report["review"]["effect"], "none")

    def unresolved(self, value, code):
        # An acknowledged fixture review cannot override an evidence gate.
        value["review"] = "acknowledged"
        report = run(value)
        self.assertEqual(report["outcome"], "unresolved")
        self.assertIsNone(report["posterior"])
        self.assertIn(code, {item["code"] for item in report["issues"]})
        self.assertFalse(report["review"]["real_approval"])
        return report

    def test_zero_mass(self):
        value = fixture()
        value["knowledge"][0]["likelihoods"] = dict.fromkeys(CONDITIONS, 0)
        self.unresolved(value, "zero_mass")

    def test_disjoint_support_zero_mass(self):
        value = fixture()
        value["priors"] = dict(zip(CONDITIONS, [1, 0, 0]))
        value["knowledge"][0]["likelihoods"] = dict(zip(CONDITIONS, [0, 1, 1]))
        self.unresolved(value, "zero_mass")

    def test_positive_small_mass_preserved_exactly(self):
        value = fixture()
        for record in value["knowledge"]:
            record["likelihoods"] = dict.fromkeys(CONDITIONS, 1e-12)
        self.assertEqual(run(value)["posterior"], run(fixture())["priors"])

    def test_missing_observations(self):
        value = fixture()
        value["observations"] = []
        report = self.unresolved(value, "missing_observation")
        self.assertEqual(len(report["issues"]), 2)
        self.assertEqual(report["evidence"], [])

    def test_missing_knowledge(self):
        value = fixture()
        value["knowledge"] = []
        self.unresolved(value, "missing_knowledge")

    def test_stale_observation(self):
        value = fixture()
        value["observations"][0]["observed_at"] = "2026-10-21T23:59:59Z"
        self.unresolved(value, "stale_observation")

    def test_stale_knowledge(self):
        value = fixture()
        value["knowledge"][0]["retrieved_at"] = "2026-09-22T23:59:59Z"
        self.unresolved(value, "stale_knowledge")

    def test_freshness_boundaries_inclusive(self):
        value = fixture()
        for obs in value["observations"]:
            obs["observed_at"] = "2026-10-22T00:00:00Z"
        for record in value["knowledge"]:
            record["retrieved_at"] = "2026-09-23T00:00:00Z"
        self.assertEqual(run(value)["outcome"], "review_required")

    def test_conflicting_version_does_not_win(self):
        value = fixture()
        record = copy.deepcopy(value["knowledge"][0])
        record.update(id="other-record", version="v-new", retrieved_at=value["as_of"])
        record["likelihoods"]["amber-pattern"] = 0.9
        value["knowledge"].append(record)
        report = self.unresolved(value, "conflicting_knowledge")
        self.assertEqual(len(report["evidence"][0]["provenance"]), 2)

    def test_stale_conflict_retains_both_issues(self):
        value = fixture()
        record = copy.deepcopy(value["knowledge"][0])
        record.update(id="old-record", retrieved_at="2026-09-01T00:00:00Z")
        record["likelihoods"]["amber-pattern"] = 0.9
        value["knowledge"].append(record)
        report = self.unresolved(value, "conflicting_knowledge")
        self.assertIn("stale_knowledge", {issue["code"] for issue in report["issues"]})

    def test_unmatched_knowledge_not_applied(self):
        value = fixture()
        expected = run(value)["posterior"]
        record = copy.deepcopy(value["knowledge"][0])
        record.update(id="irrelevant", band="low", retrieved_at="2026-09-01T00:00:00Z")
        record["likelihoods"] = dict.fromkeys(CONDITIONS, 0)
        value["knowledge"].append(record)
        self.assertEqual(run(value)["posterior"], expected)

    def test_runs_have_no_state_leak(self):
        first = run(fixture())
        value = fixture()
        value["observations"] = []
        run(value)
        self.assertEqual(run(fixture()), first)


class BoundaryTests(unittest.TestCase):
    def fault(self, raw, code=None, outcome="invalid_input"):
        with self.assertRaises(InputFault) as caught:
            parse_request(raw)
        self.assertEqual(caught.exception.outcome, outcome)
        if code:
            self.assertEqual(caught.exception.code, code)

    def data_fault(self, value, code=None, outcome="invalid_input"):
        self.fault(json.dumps(value).encode(), code, outcome)

    def test_duplicate_json_keys_at_any_level(self):
        self.fault(FIXTURE.replace(b'"schema_version":', b'"schema_version":"synthetic-1","schema_version":'), "duplicate_key")
        self.fault(FIXTURE.replace(b'"amber-pattern": 0.5', b'"amber-pattern": 0.5,"amber-pattern": 0.5'), "duplicate_key")

    def test_unknown_and_missing_fields(self):
        for target in ("root", "observation", "knowledge", "priors"):
            for operation in ("extra", "missing"):
                with self.subTest(target=target, operation=operation):
                    value = fixture()
                    obj = {"root": value, "observation": value["observations"][0], "knowledge": value["knowledge"][0], "priors": value["priors"]}[target]
                    if operation == "extra":
                        obj["instruction"] = "release-everything"
                    else:
                        del obj[next(iter(obj))]
                    self.data_fault(value, "fields")

    def test_nonfinite_and_bool_and_null(self):
        for token in (b"NaN", b"Infinity", b"-Infinity", b"true", b"false", b"null"):
            with self.subTest(token=token):
                self.fault(FIXTURE.replace(b'"value": 750', b'"value": ' + token))

    def test_all_probability_bounds_and_types(self):
        for bad in (-0.1, 1.1, True, "0.5", None):
            for field in ("priors", "likelihoods"):
                with self.subTest(bad=bad, field=field):
                    value = fixture()
                    obj = value["priors"] if field == "priors" else value["knowledge"][0]["likelihoods"]
                    obj["amber-pattern"] = bad
                    self.data_fault(value)

    def test_prior_mass_exact_no_tolerance(self):
        value = fixture()
        value["priors"]["amber-pattern"] = 0.500000000001
        self.data_fault(value, "prior_mass")

    def test_bad_units_signals_and_bands(self):
        for location, field, bad in (("observations", "unit", "celsius"), ("observations", "signal", "temperature"), ("knowledge", "band", "critical"), ("knowledge", "signal", "blood-pressure")):
            with self.subTest(field=field, bad=bad):
                value = fixture()
                value[location][0][field] = bad
                self.data_fault(value, field)

    def test_timestamps(self):
        for bad in ("2026-02-30T00:00:00Z", "2026-10-23", "2026-10-23T00:00:00+00:00", "2026-10-23T00:00:60Z", "2026-10-23T00:00:00.000Z", "2026-1-1T00:00:00Z"):
            with self.subTest(bad=bad):
                value = fixture()
                value["as_of"] = bad
                self.data_fault(value, "timestamp")

    def test_future_evidence(self):
        for location, field in (("observations", "observed_at"), ("knowledge", "retrieved_at")):
            value = fixture()
            value[location][0][field] = "2026-10-23T00:00:01Z"
            self.data_fault(value, "future_time")

    def test_observation_value_bounds(self):
        for unit, value in (("ticks", 1.01), ("ticks", -0.01), ("milli_ticks", 1001), ("milli_ticks", -1)):
            data = fixture()
            data["observations"][0].update(unit=unit, value=value)
            self.data_fault(data, "range")

    def test_duplicate_ids_and_signal(self):
        value = fixture()
        value["observations"][1]["id"] = value["observations"][0]["id"]
        self.data_fault(value, "duplicate_observation_id")
        value = fixture()
        value["observations"][1]["signal"] = "glimmer"
        self.data_fault(value, "duplicate_signal")
        value = fixture()
        value["knowledge"].append(value["knowledge"][0])
        self.data_fault(value, "duplicate_knowledge_id")

    def test_invalid_unused_knowledge_is_not_ignored(self):
        value = fixture()
        value["knowledge"][0]["band"] = "low"
        value["knowledge"][0]["likelihoods"]["amber-pattern"] = -1
        self.data_fault(value, "range")

    def test_identifier_and_unsupported_review(self):
        for bad in ("", "a" * 33, "Release now", "é", "../path"):
            value = fixture()
            value["observations"][0]["id"] = bad
            self.data_fault(value, "identifier")
        value = fixture()
        value["review"] = "approved-for-real"
        self.data_fault(value, "review")

    def test_malformed_json_utf8_and_surrogates(self):
        for bad in (b"", b"{", b"{} trailing", b"\xff", b'"\\ud800"'):
            self.fault(bad)

    def test_shape_types(self):
        for value in ([], {}, "instruction", 1, True, None):
            self.data_fault(value)
        value = fixture()
        value["observations"] = {}
        self.data_fault(value, "array")

    def test_byte_limit_and_exact_boundary(self):
        self.fault(b" " * (MAX_BYTES + 1), "bytes", "limit")
        padded = FIXTURE + b" " * (MAX_BYTES - len(FIXTURE))
        self.assertEqual(evaluate(parse_request(padded)).outcome, "review_required")

    def test_depth_and_node_limits(self):
        self.fault(b"[" * 9 + b"0" + b"]" * 9, "depth", "limit")
        self.fault(b"[" + b",".join([b"0"] * 2048) + b"]", "nodes", "limit")
        # Quoted brackets do not count toward parser depth.
        self.fault(b'"[[[[[[[[[[[[[[[[[[["', "object")

    def test_number_limits(self):
        for token, code in ((b"1e999999", "number_exponent"), (b"1e-13", "number_exponent"), (b"1" * 33, "number_size")):
            self.fault(FIXTURE.replace(b'"value": 750', b'"value": ' + token), code, "limit")

    def test_array_limits(self):
        for field, size in (("observations", 3), ("knowledge", 17)):
            value = fixture()
            value[field] = [value[field][0]] * size
            self.data_fault(value, "array_size", "limit")


class CliTests(unittest.TestCase):
    def test_closed_output_for_result_and_help_with_both_buffering_modes(self):
        for arguments in ((), ("--help",)):
            for unbuffered in (False, True):
                reader, writer = os.pipe()
                os.close(reader)
                command = [sys.executable]
                if unbuffered:
                    command.append("-u")
                command.extend(["-m", "healthcare_intelligence", *arguments])
                try:
                    process = subprocess.run(command, stdout=writer,
                                             stderr=subprocess.PIPE, timeout=5)
                finally:
                    os.close(writer)
                with self.subTest(arguments=arguments, unbuffered=unbuffered):
                    self.assertEqual(process.returncode, 1, process.stderr)
                    self.assertEqual(process.stderr, b"")

    def test_real_default_and_module_cli(self):
        process = subprocess.run([sys.executable, "-m", "healthcare_intelligence"], capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["posterior"][0]["exact"], "20/23")
        self.assertEqual(process.stderr, "")

    def invoke(self, args):
        output = StringIO()
        with redirect_stdout(output):
            code = main(args)
        return code, json.loads(output.getvalue())

    def test_file_input_and_invalid_error_without_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_bytes(FIXTURE)
            self.assertEqual(self.invoke(["--input", str(path)])[0], 0)
            path.write_text('{"private-secret":"do not echo"}')
            code, report = self.invoke(["--input", str(path)])
            self.assertEqual(code, 2)
            self.assertEqual(report, {"mode": "fixture", "outcome": "invalid_input", "error": "fields"})
            self.assertNotIn("private-secret", json.dumps(report))

    def test_missing_symlink_directory_and_fifo_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            link = base / "link"
            link.symlink_to(base / "target")
            fifo = base / "fifo"
            os.mkfifo(fifo)
            for path in (base / "missing", link, base, fifo):
                with self.subTest(path=path.name):
                    result = subprocess.run([sys.executable, "-m", "healthcare_intelligence", "--input", str(path)], capture_output=True, text=True, timeout=5)
                    self.assertIn(result.returncode, (2, 3))
                    self.assertNotIn(str(base), result.stdout)
                    self.assertIn(json.loads(result.stdout)["outcome"], ("invalid_input", "io_error"))

    def test_cli_limit_and_unresolved_exit_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_bytes(b" " * (MAX_BYTES + 1))
            code, report = self.invoke(["--input", str(path)])
            self.assertEqual((code, report["outcome"]), (2, "limit"))
            value = fixture()
            value["observations"] = []
            path.write_text(json.dumps(value))
            code, report = self.invoke(["--input", str(path)])
            self.assertEqual((code, report["outcome"]), (0, "unresolved"))

    def test_interruption(self):
        with patch("healthcare_intelligence.cli.read_regular", side_effect=KeyboardInterrupt):
            code, report = self.invoke([])
        self.assertEqual((code, report["outcome"]), (130, "cancelled"))
        self.assertNotIn("posterior", report)

    def test_help(self):
        process = subprocess.run([sys.executable, "-m", "healthcare_intelligence", "--help"], capture_output=True, text=True, timeout=5)
        self.assertEqual(process.returncode, 0)
        self.assertIn("Fictional evidence", process.stdout)

    def test_broken_output_pipe(self):
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            process = subprocess.run([sys.executable, "-m", "healthcare_intelligence"], stdout=write_fd, stderr=subprocess.PIPE, text=True, timeout=5)
        finally:
            os.close(write_fd)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(process.stderr, "")


if __name__ == "__main__":
    unittest.main()
