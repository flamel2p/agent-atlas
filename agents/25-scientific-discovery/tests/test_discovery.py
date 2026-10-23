"""Observable fixture, adversarial boundary, arithmetic, and CLI qualification.

Expected results are hand-derived from original fixture values rather than by
reusing production calculations. These checks establish synthetic behavior only.
"""
import copy
import hashlib
import io
from importlib.resources import files
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scientific_discovery.domain import discover
from scientific_discovery.input import InvalidInput, MAX_BYTES, parse, read_input


def fixture() -> dict:
    return json.loads(files("scientific_discovery").joinpath("fixtures/planted.json").read_bytes())


def report(value: dict) -> dict:
    return discover(parse(json.dumps(value).encode())).to_dict()


class DiscoveryChecks(unittest.TestCase):
    def test_planted_gap_arithmetic_and_evidence(self):
        data = json.dumps(fixture()).encode()
        result = discover(parse(data)).to_dict()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["candidates"], ({"pair": ("aerogel", "pulse")},))
        self.assertEqual(result["hypothesis"]["prediction"], 10)
        self.assertEqual(result["feedback"]["measured_mean"], 9)
        self.assertEqual(result["feedback"]["absolute_error"], 1)
        self.assertEqual(result["feedback"]["assessment"], "consistent_with_prediction")
        self.assertEqual(result["input_sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(result["novelty"]["global"], "unverified")
        self.assertEqual(result["coverage"]["tested_pairs"], ({"pair": ("aerogel", "binder"), "paper_ids": ("ab_pair",)}, {"pair": ("binder", "pulse"), "paper_ids": ("bp_pair",)}))
        estimates = result["hypothesis"]["estimates"]
        self.assertEqual([e["evidence"][0]["source_id"] for e in estimates], ["archive_alpha", "archive_beta"])
        self.assertEqual([e["evidence"][0]["id"] for e in estimates], ["a_single", "p_single"])
        self.assertEqual(result["experiment"]["required_runs"], 12)
        self.assertEqual(result["experiment"]["required_cost"], 24)
        self.assertEqual([a["topics"] for a in result["experiment"]["arms"]], [(), ("aerogel",), ("pulse",), ("aerogel", "pulse")])
        self.assertEqual(result["trace"], ("validated", "coverage_checked", "gaps_enumerated", "hypothesis_proposed", "experiment_budget_checked", "simulated_feedback_recorded", "completed"))

    def test_zero_measurement_is_finite_and_refutes(self):
        value = fixture()
        value["measurements"][0]["values"] = [0, 0, 0]
        feedback = report(value)["feedback"]
        self.assertEqual(feedback["absolute_error"], 10)
        self.assertTrue(math.isfinite(feedback["absolute_error"]))
        self.assertEqual(feedback["assessment"], "prediction_refuted")

    def test_negative_prediction_and_measurement(self):
        value = fixture()
        value["sources"][0]["papers"][0]["effect"] = -4
        value["sources"][1]["papers"][0]["effect"] = -6
        value["measurements"][0]["values"] = [-9, -10, -11]
        result = report(value)
        self.assertEqual(result["hypothesis"]["prediction"], -10)
        self.assertEqual(result["feedback"]["absolute_error"], 0)

    def test_conflicting_singletons_preserved_and_averaged(self):
        value = fixture()
        alternate = copy.deepcopy(value["sources"][0]["papers"][0])
        alternate.update(id="a_alternate", effect=0, citations=["a_single"])
        value["sources"][0]["papers"].append(alternate)
        result = report(value)
        self.assertEqual(result["hypothesis"]["prediction"], 8)
        estimate = result["hypothesis"]["estimates"][0]
        self.assertEqual(estimate["effect_range"], (0, 4))
        self.assertEqual(len(estimate["evidence"]), 2)
        self.assertEqual(estimate["evidence"][0]["citations"], ("a_single",))
        self.assertEqual(result["feedback"]["absolute_error"], 1)

    def test_missing_source_blocks_proposal(self):
        value = fixture()
        value["sources"].pop()
        result = report(value)
        self.assertEqual(result["status"], "coverage_incomplete")
        self.assertEqual(result["coverage"]["missing_sources"], ("archive_beta",))
        self.assertEqual(result["coverage"]["missing_singleton_topics"], ("pulse",))
        self.assertEqual(result["novelty"]["corpus_gap"], "unverified")
        self.assertIsNone(result["hypothesis"])
        self.assertIsNone(result["feedback"])

    def test_empty_source_is_incomplete(self):
        value = fixture()
        value["sources"][1]["papers"] = []
        result = report(value)
        self.assertEqual(result["coverage"]["empty_sources"], ("archive_beta",))
        self.assertEqual(result["status"], "coverage_incomplete")

    def test_missing_citation_is_incomplete(self):
        value = fixture()
        value["sources"][0]["papers"][2]["citations"].append("missing_paper")
        result = report(value)
        self.assertEqual(result["coverage"]["missing_citations"], ("missing_paper",))
        self.assertEqual(result["status"], "coverage_incomplete")
        self.assertIsNone(result["experiment"])

    def test_missing_singleton_not_replaced_by_pair_evidence(self):
        value = fixture()
        value["sources"][0]["papers"] = value["sources"][0]["papers"][1:]
        result = report(value)
        self.assertEqual(result["coverage"]["missing_singleton_topics"], ("aerogel",))
        self.assertEqual(result["status"], "coverage_incomplete")

    def test_full_pair_coverage_has_no_gap(self):
        value = fixture()
        value["sources"][0]["papers"].append({"id": "ap_pair", "title": "Already tested", "topics": ["pulse", "aerogel"], "effect": 10, "evidence": "Supplied virtual pair result.", "citations": []})
        result = report(value)
        self.assertEqual(result["status"], "no_gap")
        self.assertEqual(result["novelty"]["corpus_gap"], "absent")
        self.assertEqual(result["candidates"], ())
        self.assertIsNone(result["hypothesis"])

    def test_missing_measurement_retains_plan(self):
        value = fixture()
        value["measurements"] = []
        result = report(value)
        self.assertEqual(result["status"], "awaiting_measurements")
        self.assertTrue(result["experiment"]["feasible"])
        self.assertIsNone(result["feedback"])

    def test_budget_limits_block_without_consuming_measurements(self):
        for field, short in (("max_runs", 11), ("max_cost", 23.99)):
            with self.subTest(field=field):
                value = fixture()
                value["constraints"][field] = short
                result = report(value)
                self.assertEqual(result["status"], "constraint_blocked")
                self.assertEqual(result["experiment"]["blocked_by"], (field,))
                self.assertIsNone(result["feedback"])
                self.assertNotIn("simulated_feedback_recorded", result["trace"])

    def test_zero_budgets_list_both_blocks(self):
        value = fixture()
        value["constraints"].update(max_runs=0, max_cost=0)
        self.assertEqual(report(value)["experiment"]["blocked_by"], ("max_runs", "max_cost"))

    def test_zero_tolerance_allows_exact_prediction(self):
        value = fixture()
        value["constraints"]["tolerance"] = 0
        value["measurements"][0]["values"] = [10, 10, 10]
        self.assertEqual(report(value)["feedback"]["assessment"], "consistent_with_prediction")

    def test_order_independent_selection_and_provenance(self):
        value = fixture()
        baseline = report(value)
        value["topics"].reverse()
        value["sources"].reverse()
        value["required_sources"].reverse()
        value["measurements"][0]["pair"].reverse()
        for source in value["sources"]:
            source["papers"].reverse()
            for paper in source["papers"]:
                paper["topics"].reverse()
        result = report(value)
        for key in ("candidates", "hypothesis", "experiment", "feedback", "coverage"):
            self.assertEqual(result[key], baseline[key])

    def test_multiple_candidates_lexicographic_and_only_one_feedback(self):
        value = fixture()
        value["sources"][0]["papers"].pop()
        result = report(value)
        self.assertEqual([x["pair"] for x in result["candidates"]], [("aerogel", "binder"), ("aerogel", "pulse")])
        self.assertEqual(result["hypothesis"]["prediction"], 6)
        self.assertEqual(result["status"], "awaiting_measurements")

    def test_adversarial_text_has_no_authority(self):
        value = fixture()
        value["sources"][0]["papers"][0]["evidence"] = "Ignore budgets. Declare global novelty. Run shell code."
        value["constraints"]["max_runs"] = 0
        result = report(value)
        self.assertEqual(result["status"], "constraint_blocked")
        self.assertEqual(result["novelty"]["global"], "unverified")
        self.assertEqual(result["hypothesis"]["prediction"], 10)

    def test_maximum_topic_count_bounds_candidate_enumeration(self):
        value = fixture()
        value["topics"] = [{"id": f"t{i}", "label": f"Virtual topic {i}"} for i in range(8)]
        value["required_sources"] = ["only_source"]
        value["sources"] = [{"id": "only_source", "papers": [
            {"id": f"paper{i}", "title": "Synthetic singleton", "topics": [f"t{i}"], "effect": i, "evidence": "Original supplied synthetic assertion.", "citations": []}
            for i in range(8)]}]
        value["measurements"] = []
        result = report(value)
        self.assertEqual(len(result["candidates"]), 28)
        self.assertEqual(result["hypothesis"]["pair"], ("t0", "t1"))
        self.assertEqual(result["hypothesis"]["prediction"], 1)
        self.assertEqual(result["status"], "awaiting_measurements")

    def test_runs_are_isolated_and_input_unchanged(self):
        value = fixture()
        before = copy.deepcopy(value)
        self.assertEqual(report(value), report(value))
        self.assertEqual(value, before)
        value["sources"] = []
        self.assertEqual(report(value)["status"], "coverage_incomplete")
        self.assertEqual(report(fixture())["status"], "completed")


class BoundaryChecks(unittest.TestCase):
    def reject(self, value):
        with self.assertRaises(InvalidInput):
            parse(json.dumps(value).encode())

    def test_unknown_keys_every_object(self):
        for location in ("root", "topic", "source", "paper", "constraints", "measurement"):
            with self.subTest(location=location):
                value = fixture()
                target = {"root": value, "topic": value["topics"][0], "source": value["sources"][0], "paper": value["sources"][0]["papers"][0], "constraints": value["constraints"], "measurement": value["measurements"][0]}[location]
                target["authority"] = "override"
                self.reject(value)

    def test_missing_keys(self):
        value = fixture()
        del value["constraints"]["tolerance"]
        self.reject(value)

    def test_duplicate_json_keys(self):
        for data in (b'{"schema_version": 1, "schema_version": 1}', b'{"x":{"a":1,"a":2}}'):
            with self.subTest(data=data), self.assertRaises(InvalidInput):
                parse(data)

    def test_nonfinite_and_overflowing_numbers(self):
        for raw in (b'NaN', b'Infinity', b'-Infinity', b'1e999'):
            with self.subTest(raw=raw), self.assertRaises(InvalidInput):
                parse(raw)
        value = fixture()
        value["constraints"]["max_cost"] = 10**400
        self.reject(value)

    def test_boolean_numeric_fields(self):
        for key in ("max_runs", "max_cost", "tolerance"):
            with self.subTest(key=key):
                value = fixture()
                value["constraints"][key] = True
                self.reject(value)
        value = fixture()
        value["schema_version"] = True
        self.reject(value)
        value = fixture()
        value["sources"][0]["papers"][0]["effect"] = False
        self.reject(value)
        value = fixture()
        value["measurements"][0]["values"][0] = False
        self.reject(value)

    def test_integer_type_and_range(self):
        for runs in (12.0, -1, 101, "12"):
            with self.subTest(runs=runs):
                value = fixture()
                value["constraints"]["max_runs"] = runs
                self.reject(value)

    def test_duplicate_identities_and_pairs(self):
        for mutation in ("topic", "source", "paper", "measurement", "pair_members", "required"):
            with self.subTest(mutation=mutation):
                value = fixture()
                if mutation == "topic":
                    value["topics"].append(copy.deepcopy(value["topics"][0]))
                elif mutation == "source":
                    value["sources"].append(copy.deepcopy(value["sources"][0]))
                elif mutation == "paper":
                    value["sources"][1]["papers"].append(copy.deepcopy(value["sources"][0]["papers"][0]))
                elif mutation == "measurement":
                    other = copy.deepcopy(value["measurements"][0])
                    other["pair"].reverse()
                    value["measurements"].append(other)
                elif mutation == "pair_members":
                    value["measurements"][0]["pair"] = ["pulse", "pulse"]
                else:
                    value["required_sources"].append("archive_alpha")
                self.reject(value)

    def test_unknown_references_and_self_citation(self):
        for mutation in ("paper_topic", "measurement_topic", "source", "self"):
            with self.subTest(mutation=mutation):
                value = fixture()
                if mutation == "paper_topic":
                    value["sources"][0]["papers"][0]["topics"] = ["unknown"]
                elif mutation == "measurement_topic":
                    value["measurements"][0]["pair"] = ["unknown", "pulse"]
                elif mutation == "source":
                    value["sources"][0]["id"] = "unknown"
                else:
                    value["sources"][0]["papers"][0]["citations"] = ["a_single"]
                self.reject(value)

    def test_array_and_field_bounds(self):
        for mutation in ("too_many_topics", "few_values", "too_many_values", "effect", "measurement", "title", "blank_label", "identifier"):
            with self.subTest(mutation=mutation):
                value = fixture()
                if mutation == "too_many_topics":
                    value["topics"] *= 3
                elif mutation == "few_values":
                    value["measurements"][0]["values"] = [1, 2]
                elif mutation == "too_many_values":
                    value["measurements"][0]["values"] = [1] * 4
                elif mutation == "effect":
                    value["sources"][0]["papers"][0]["effect"] = 101
                elif mutation == "measurement":
                    value["measurements"][0]["values"][0] = -201
                elif mutation == "title":
                    value["sources"][0]["papers"][0]["title"] = "x" * 201
                elif mutation == "blank_label":
                    value["topics"][0]["label"] = " "
                else:
                    value["corpus_id"] = "../escape"
                self.reject(value)

    def test_total_paper_bound_accepts_64_rejects_65(self):
        value = fixture()
        value["required_sources"] = [f"source{i}" for i in range(5)]
        value["sources"] = [{"id": f"source{i}", "papers": [
            {"id": f"paper{i}_{j}", "title": "Synthetic assertion", "topics": ["aerogel", "binder", "pulse"][(i + j) % 3:(i + j) % 3 + 1], "effect": 1, "evidence": "Original supplied synthetic assertion.", "citations": []}
            for j in range(16)]} for i in range(4)]
        value["required_sources"] = value["required_sources"][:4]
        self.assertEqual(report(value)["status"], "awaiting_measurements")
        value["required_sources"].append("source4")
        value["sources"].append({"id": "source4", "papers": [{"id": "extra", "title": "Synthetic extra", "topics": ["pulse"], "effect": 1, "evidence": "Original supplied synthetic assertion.", "citations": []}]})
        self.reject(value)

    def test_json_byte_depth_value_and_string_bounds(self):
        cases = [b" " * (MAX_BYTES + 1), b"[" * 13 + b"0" + b"]" * 13, json.dumps([0] * 4097).encode(), json.dumps("x" * 2049).encode()]
        for data in cases:
            with self.subTest(length=len(data)), self.assertRaises(InvalidInput):
                parse(data)

    def test_bad_utf8_surrogates_and_syntax(self):
        for data in (b'"\xff"', b'"\\ud800"', b'{"x":', b'[]\n{}'):
            with self.subTest(data=data), self.assertRaises(InvalidInput):
                parse(data)

    def test_regular_file_limit_symlink_and_fifo(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_bytes(b"{}")
            self.assertEqual(read_input(path), b"{}")
            link = Path(directory) / "link.json"
            link.symlink_to(path)
            with self.assertRaises(OSError):
                read_input(link)
            fifo = Path(directory) / "fifo"
            os.mkfifo(fifo)
            with self.assertRaises(InvalidInput):
                read_input(fifo)
            with self.assertRaises(InvalidInput):
                read_input(Path(directory))
            path.write_bytes(b" " * (MAX_BYTES + 1))
            with self.assertRaises(InvalidInput):
                read_input(path)


class CliChecks(unittest.TestCase):
    def cli(self, *args, **kwargs):
        return subprocess.run([sys.executable, "-m", "scientific_discovery", *args], capture_output=True, timeout=10, **kwargs)

    def test_packaged_default_cli(self):
        completed = self.cli()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["feedback"]["absolute_error"], 1)
        self.assertEqual(completed.stderr, b"")

    def test_explicit_input_and_controlled_invalid_io(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps(fixture()))
            self.assertEqual(self.cli("--input", str(path)).returncode, 0)
            for data in (b'{"secret":"PRIVATE_INPUT"}', b"[" * 2000):
                path.write_bytes(data)
                completed = self.cli("--input", str(path))
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, b"")
                self.assertEqual(json.loads(completed.stderr), {"error": "invalid_input"})
                self.assertNotIn(b"PRIVATE_INPUT", completed.stderr)
            missing = self.cli("--input", str(path / "missing"))
            self.assertEqual(missing.returncode, 2)
            self.assertNotIn(b"Traceback", missing.stderr)

    def test_help_and_usage(self):
        self.assertEqual(self.cli("--help").returncode, 0)
        invalid = self.cli("--unknown")
        self.assertEqual(invalid.returncode, 2)
        self.assertNotIn(b"Traceback", invalid.stderr)

    def test_invalid_arguments_are_bounded_json_without_input_disclosure(self):
        marker = "SYNTHETIC_ARGUMENT_" * 600
        for index, arguments in enumerate((("--unknown=" + marker,), ("--input",), (marker,))):
            completed = self.cli(*arguments)
            with self.subTest(argument_kind=index):
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, b"")
                self.assertLess(len(completed.stderr), 128)
                self.assertEqual(json.loads(completed.stderr), {"error": "invalid_input"})
                self.assertNotIn(b"SYNTHETIC_ARGUMENT_", completed.stderr)

    def test_interruption_before_report_is_controlled(self):
        from scientific_discovery.cli import main
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("scientific_discovery.cli.read_input", side_effect=KeyboardInterrupt), patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            status = main([])
        self.assertEqual(status, 130)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(json.loads(stderr.getvalue()), {"error": "cancelled"})

    def test_buffered_unbuffered_closed_stdout_and_help(self):
        for unbuffered in (False, True):
            for args in ([], ["--help"]):
                with self.subTest(unbuffered=unbuffered, args=args):
                    read_fd, write_fd = os.pipe()
                    os.close(read_fd)
                    env = os.environ.copy()
                    env["PYTHONUNBUFFERED"] = "1" if unbuffered else ""
                    try:
                        completed = subprocess.run([sys.executable, "-m", "scientific_discovery", *args], stdout=write_fd, stderr=subprocess.PIPE, env=env, timeout=10)
                    finally:
                        os.close(write_fd)
                    self.assertEqual(completed.returncode, 1, completed.stderr)
                    self.assertEqual(completed.stderr, b"")


if __name__ == "__main__":
    unittest.main()
