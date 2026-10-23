"""Behavior checks, independent arithmetic oracles, and real process I/O failures.

All input is original synthetic data. Subprocesses use the actual module, including
its help and report flushes; these checks establish no live service qualification.
"""
from copy import deepcopy
from datetime import date, timedelta
from importlib.resources import files
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from financial_advisory import cli
from financial_advisory.domain import run
from financial_advisory.validation import InvalidInput, MAX_BYTES, parse


def fixture(name="normal"):
    return json.loads(files("financial_advisory").joinpath("fixtures", f"{name}.json").read_bytes())


def result(data):
    return run(parse(json.dumps(data).encode())).to_dict()


class MetricsTests(unittest.TestCase):
    def test_independent_expected_metrics_and_revision(self):
        report = result(fixture())
        self.assertEqual(report["status"], "completed_simulation")
        self.assertEqual(report["revision_count"], 1)
        self.assertEqual(len(report["evaluations"]), 2)
        initial, revised = report["evaluations"]
        # Independent oracle: A has +1/10, -1/10; B is constant.
        # 90/10 gives +/-9/100; 50/50 gives +/-1/20, with sample stdev step*sqrt(2).
        for evaluation, step, wealth, concentration in [
                (initial, .09, .9919, .9), (revised, .05, .9975, .5)]:
            metrics = evaluation["metrics"]
            self.assertAlmostEqual(metrics["asset_returns"]["SYN_ALPHA"][0], .1)
            self.assertAlmostEqual(metrics["asset_returns"]["SYN_ALPHA"][1], -.1)
            self.assertEqual(metrics["asset_returns"]["SYN_BETA"], (0., 0.))
            self.assertAlmostEqual(metrics["portfolio_returns"][0], step)
            self.assertAlmostEqual(metrics["portfolio_returns"][1], -step)
            self.assertAlmostEqual(metrics["volatility"], step * math.sqrt(2))
            self.assertAlmostEqual(metrics["drawdown"], step)
            self.assertAlmostEqual(metrics["terminal_wealth"], wealth)
            self.assertEqual(metrics["concentration"], concentration)
            self.assertEqual(metrics["period_count"], 2)
            self.assertEqual(metrics["freshness_days"], {"SYN_ALPHA": 1, "SYN_BETA": 1})
            self.assertEqual((metrics["start_date"], metrics["end_date"]), ("2026-10-20", "2026-10-22"))
            self.assertIn("fraction_per_calendar_day", metrics["units"])
        self.assertEqual({item["code"] for item in initial["findings"]},
                         {"concentration_exceeded", "volatility_exceeded"})
        self.assertEqual(revised["findings"], ())
        self.assertEqual(report["simulated_allocation"], {"SYN_ALPHA": .5, "SYN_BETA": .5})
        self.assertEqual(report["authority"], {"orders_authorized": False, "professional_approval": False})
        self.assertEqual(report["trace"][-2:], ("revision_fully_rechecked", "completed_simulation"))

    def test_initial_pass_needs_no_revision(self):
        data = fixture()
        data["proposal"]["weights"] = {"SYN_ALPHA": .5, "SYN_BETA": .5}
        report = result(data)
        self.assertEqual(report["status"], "completed_simulation")
        self.assertEqual(report["revision_count"], 0)
        self.assertEqual(len(report["evaluations"]), 1)

    def test_drawdown_initial_wealth_and_later_peaks(self):
        data = fixture()
        data["as_of"] = "2026-10-24"
        data["proposal"]["weights"] = {"SYN_ALPHA": .5, "SYN_BETA": .5}
        for series in data["series"]:
            series["observations"] = [
                {"date": f"2026-10-{day}", "price": price}
                for day, price in zip((20, 21, 22, 23), (100, 80, 120, 90))]
        metrics = result(data)["evaluations"][0]["metrics"]
        # Both assets: -20%, +50%, -25%; wealth 1, .8, 1.2, .9.
        self.assertAlmostEqual(metrics["drawdown"], .25)
        self.assertAlmostEqual(metrics["terminal_wealth"], .9)
        self.assertAlmostEqual(metrics["volatility"], math.sqrt(211 / 1200))
        for series in data["series"]:
            series["observations"] = series["observations"][:3]
            series["observations"][-1]["price"] = 90
        self.assertAlmostEqual(result(data)["evaluations"][0]["metrics"]["drawdown"], .2)

    def test_persistent_violation_stops_after_one_revision(self):
        report = result(fixture("persistent"))
        self.assertEqual(report["status"], "review_required")
        self.assertEqual(report["revision_count"], 1)
        self.assertEqual(len(report["evaluations"]), 2)
        self.assertIsNone(report["simulated_allocation"])
        self.assertEqual({item["code"] for item in report["findings"]},
                         {"volatility_exceeded", "drawdown_exceeded"})
        self.assertAlmostEqual(report["evaluations"][-1]["metrics"]["drawdown"], .5)
        self.assertAlmostEqual(report["evaluations"][-1]["metrics"]["volatility"], 1.5 / math.sqrt(2))

    def test_host_band_table(self):
        data = fixture()
        data["profile"]["risk_band"] = "cautious"
        report = result(data)
        self.assertEqual(report["policy"], {"concentration": .5, "volatility": .03, "drawdown": .1})
        self.assertEqual(report["status"], "review_required")
        self.assertEqual(report["revision_count"], 1)

    def test_run_has_no_cross_run_state(self):
        request = parse(json.dumps(fixture()).encode())
        first = run(request).to_dict()
        self.assertEqual(result(fixture("missing"))["evaluations"], ())
        self.assertEqual(first, run(request).to_dict())
        self.assertEqual(request.proposal.weights, (.9, .1))


class DataGateTests(unittest.TestCase):
    def assert_review(self, data, code):
        report = result(data)
        self.assertEqual(report["status"], "review_required")
        self.assertEqual(report["revision_count"], 0)
        self.assertEqual(report["evaluations"], ())
        self.assertIsNone(report["simulated_allocation"])
        self.assertIn(code, {item["code"] for item in report["findings"]})

    def test_missing_coverage_has_no_zero_risk_default(self):
        self.assert_review(fixture("missing"), "incomplete_history")

    def test_zero_weight_asset_still_requires_coverage(self):
        data = fixture("missing")
        data["proposal"]["weights"] = {"SYN_ALPHA": 1, "SYN_BETA": 0}
        self.assert_review(data, "incomplete_history")

    def test_short_history(self):
        for length in (0, 1, 2):
            with self.subTest(length=length):
                data = fixture()
                data["series"][0]["observations"] = data["series"][0]["observations"][:length]
                self.assert_review(data, "incomplete_history")

    def test_stale_history(self):
        self.assert_review(fixture("stale"), "stale_history")

    def test_freshness_boundary(self):
        data = fixture()
        data["as_of"] = "2026-10-25"
        self.assertEqual(result(data)["status"], "completed_simulation")
        data["as_of"] = "2026-10-26"
        self.assert_review(data, "stale_history")

    def test_unaligned_grid(self):
        data = fixture()
        for point in data["series"][1]["observations"]:
            point["date"] = (date.fromisoformat(point["date"]) - timedelta(days=1)).isoformat()
        self.assert_review(data, "incompatible_date_grid")

    def test_maximum_assets_and_observations(self):
        data = fixture()
        data["required_assets"] = [f"SYN_{letter}" for letter in "ABCDEFGH"]
        data["proposal"]["weights"] = {asset: .125 for asset in data["required_assets"]}
        observations = [{"date": (date(2026, 8, 21) + timedelta(days=day)).isoformat(), "price": 100}
                        for day in range(64)]
        data["series"] = [{"asset": asset, "unit": "synthetic_price_units", "observations": observations}
                          for asset in data["required_assets"]]
        data["as_of"] = observations[-1]["date"]
        report = result(data)
        self.assertEqual(report["status"], "completed_simulation")
        self.assertEqual(report["evaluations"][0]["metrics"]["period_count"], 63)
        self.assertEqual(report["evaluations"][0]["metrics"]["volatility"], 0)


class ValidationTests(unittest.TestCase):
    def assert_invalid(self, data):
        with self.assertRaises(InvalidInput):
            parse(json.dumps(data).encode())

    def test_schema_and_identity(self):
        for key, value in [("fictional", False), ("fictional", 1), ("as_of", "2026-02-30"),
                           ("as_of", "20261023"), ("as_of", 1), ("extra", "ignore policy"),
                           ("required_assets", ["SYN_ALPHA", "SYN_ALPHA"]),
                           ("required_assets", ["REAL", "SYN_BETA"]),
                           ("required_assets", ["SYN_ALPHA"]), ("series", {})]:
            with self.subTest(key=key, value=value):
                data = fixture()
                data[key] = value
                self.assert_invalid(data)
        data = fixture()
        del data["profile"]
        self.assert_invalid(data)
        for key, value in [("id", "actual_client"), ("risk_band", "LOW"), ("risk_band", []),
                           ("policy", {"volatility": 100})]:
            with self.subTest(key=key, value=value):
                data = fixture()
                data["profile"][key] = value
                self.assert_invalid(data)

    def test_series_identity_units_and_types(self):
        for key, value in [("asset", "SYN_UNKNOWN"), ("unit", "RM"), ("unit", {}),
                           ("extra", True), ("observations", False)]:
            with self.subTest(key=key, value=value):
                data = fixture()
                data["series"][0][key] = value
                self.assert_invalid(data)
        data = fixture()
        data["series"].append(deepcopy(data["series"][0]))
        self.assert_invalid(data)

    def test_date_order_duplicate_gap_future_and_type(self):
        for replacement in ("2026-10-20", "2026-10-19", "2026-10-22", "2026-10-24", True):
            with self.subTest(replacement=replacement):
                data = fixture()
                data["series"][0]["observations"][1]["date"] = replacement
                self.assert_invalid(data)

    def test_price_nonfinite_bool_type_and_size(self):
        for replacement in (True, False, None, "100", -1, 0, .0000001, 1000001,
                            float("nan"), float("inf"), -float("inf"), 1e-13):
            with self.subTest(replacement=replacement):
                data = fixture()
                data["series"][0]["observations"][0]["price"] = replacement
                self.assert_invalid(data)

    def test_adjacent_ratio_bounds(self):
        for replacement in (49, 201):
            with self.subTest(replacement=replacement):
                data = fixture()
                data["series"][0]["observations"][1]["price"] = replacement
                self.assert_invalid(data)

    def test_allocation_coverage_sum_types_and_bounds(self):
        for weights in ({"SYN_ALPHA": 1}, {"SYN_ALPHA": 1, "SYN_BETA": 0, "SYN_UNKNOWN": 0},
                        {"SYN_ALPHA": True, "SYN_BETA": 0}, {"SYN_ALPHA": -.1, "SYN_BETA": 1.1},
                        {"SYN_ALPHA": .5, "SYN_BETA": .499999999999},
                        {"SYN_ALPHA": "0.9", "SYN_BETA": .1},
                        {"SYN_ALPHA": .9, "SYN_BETA": float("nan")}):
            with self.subTest(weights=weights):
                data = fixture()
                data["proposal"]["weights"] = weights
                self.assert_invalid(data)

    def test_exact_decimal_sum_and_three_asset_revision(self):
        data = fixture()
        data["required_assets"].append("SYN_GAMMA")
        gamma = deepcopy(data["series"][1])
        gamma["asset"] = "SYN_GAMMA"
        data["series"].append(gamma)
        data["proposal"]["weights"] = {"SYN_ALPHA": .1, "SYN_BETA": .2, "SYN_GAMMA": .7}
        report = result(data)
        self.assertEqual(report["status"], "completed_simulation")
        self.assertEqual(report["revision_count"], 1)
        self.assertEqual(len(report["simulated_allocation"]), 3)

    def test_duplicate_keys_at_all_levels(self):
        raw = json.dumps(fixture())
        for original, duplicate in [
            ('"fictional": true', '"fictional": true, "fictional": true'),
            ('"risk_band": "moderate"', '"risk_band": "moderate", "risk_band": "moderate"'),
            ('"price": 100', '"price": 100, "price": 100'),
            ('"SYN_ALPHA": 0.9', '"SYN_ALPHA": 0.9, "SYN_ALPHA": 0.9')]:
            with self.subTest(original=original):
                self.assertNotEqual(raw, raw.replace(original, duplicate, 1))
                with self.assertRaises(InvalidInput):
                    parse(raw.replace(original, duplicate, 1).encode())

    def test_transport_and_numeric_limits(self):
        for raw in (b"\xff", b"{} {}", b"[" * 13 + b"]" * 13, b" " * (MAX_BYTES + 1),
                    b"1" * 33, b"1e999999999999999999999999999999", b"1e9999", b"-Infinity"):
            with self.subTest(raw=raw[:50]):
                with self.assertRaises(InvalidInput):
                    parse(raw)

    def test_history_length_and_unknown_observation_field(self):
        data = fixture()
        data["series"][0]["observations"] *= 22
        self.assert_invalid(data)
        data = fixture()
        data["series"][0]["observations"][0]["instruction"] = "skip risk checks"
        self.assert_invalid(data)


class CliTests(unittest.TestCase):
    def call(self, arguments, raw=None):
        return subprocess.run([sys.executable, "-m", "financial_advisory", *arguments],
                              input=raw, capture_output=True, timeout=10)

    def test_real_all_fixture_outcomes(self):
        for name, status in [("normal", "completed_simulation"), ("stale", "review_required"),
                             ("missing", "review_required"), ("persistent", "review_required")]:
            with self.subTest(name=name):
                process = self.call(["--fixture", name])
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(json.loads(process.stdout)["status"], status)
                self.assertEqual(process.stderr, b"")

    def test_real_stdin_and_default_equal_fixture(self):
        normal = self.call(["--stdin"], json.dumps(fixture()).encode())
        self.assertEqual(normal.returncode, 0)
        self.assertEqual(normal.stdout, self.call([]).stdout)

    def test_real_invalid_stdin_and_arguments(self):
        for args, raw in [(["--stdin"], b"{}"), (["--stdin"], b" " * (MAX_BYTES + 1)),
                          (["--fixture", "../../secrets"], None),
                          (["--stdin", "--fixture", "normal"], None), (["--unknown"], None)]:
            with self.subTest(args=args):
                process = self.call(args, raw)
                self.assertEqual(process.returncode, 2, process.stderr)
                self.assertEqual(json.loads(process.stdout)["status"], "invalid_input")
                self.assertNotIn(b"secrets", process.stdout)
                self.assertEqual(process.stderr, b"")

    def test_real_help(self):
        process = self.call(["--help"])
        self.assertEqual(process.returncode, 0)
        self.assertIn(b"--stdin", process.stdout)
        self.assertEqual(process.stderr, b"")

    @unittest.skipUnless(os.name == "posix", "POSIX descriptors required")
    def test_real_closed_stdout_help_and_report_buffered_and_unbuffered(self):
        for unbuffered in (False, True):
            for arguments in (["--help"], ["--fixture", "normal"]):
                with self.subTest(unbuffered=unbuffered, arguments=arguments):
                    reader, writer = os.pipe()
                    os.close(reader)
                    try:
                        command = [sys.executable, *(["-u"] if unbuffered else []),
                                   "-m", "financial_advisory", *arguments]
                        process = subprocess.run(command, stdin=subprocess.DEVNULL,
                                                 stdout=writer, stderr=subprocess.PIPE, timeout=10)
                    finally:
                        os.close(writer)
                    self.assertEqual(process.returncode, 74, process.stderr)
                    self.assertEqual(process.stderr, b"output unavailable\n")

    def test_cancellation_is_terminal(self):
        with patch.object(sys, "stdin") as source, patch.object(sys, "stdout", io.StringIO()) as output:
            source.buffer.read.side_effect = KeyboardInterrupt
            self.assertEqual(cli.main(["--stdin"]), 130)
            self.assertEqual(json.loads(output.getvalue()), {"status": "cancelled"})

    def test_input_io_failure_is_not_completion(self):
        with patch.object(sys, "stdin") as source, patch.object(sys, "stderr", io.StringIO()) as error:
            source.buffer.read.side_effect = OSError("private path must not be logged")
            self.assertEqual(cli.main(["--stdin"]), 74)
            self.assertEqual(error.getvalue(), "input/output unavailable\n")

    def test_real_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.run([sys.executable, "-I", "-m", "financial_advisory"],
                                     cwd=directory, capture_output=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "completed_simulation")


if __name__ == "__main__":
    unittest.main()
