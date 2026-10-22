"""Behavior checks for the public analysis boundary and the real CLI.

Fixtures here are original synthetic records. Independent integer-cents totals,
known sample statistics, XML inspection, and injected filesystem failures check
observable contracts instead of copying internal calculation helpers.
"""

import contextlib
import csv
import dataclasses
import hashlib
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from decimal import Decimal, Inexact, Rounded, getcontext, localcontext
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

from data_analysis_agent import analyze
from data_analysis_agent import cli
from data_analysis_agent.domain import BUILTIN_SOURCE, MAX_BYTES, Completed, Failure, NeedsClarification, NoData, to_wire
from data_analysis_agent.rendering import outcome_json, render_svg


QUARTER = "from 2026-07-01 to 2026-09-30"
RANK = f"top 3 products by revenue_rm {QUARTER}"
NS = {"svg": "http://www.w3.org/2000/svg"}
FIXTURE = files("data_analysis_agent").joinpath("data/quarterly_activity.csv").read_bytes()


def csv_bytes(rows, header=("date", "product", "units", "revenue_rm")):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def report(question, contents=FIXTURE, label="test:synthetic-records"):
    outcome = analyze(question, contents, label)
    if not isinstance(outcome, Completed):
        raise AssertionError(outcome)
    return outcome.report


class AnalysisTests(unittest.TestCase):
    def test_quarter_ranking_independent_cents_and_provenance(self):
        result = report(RANK, label=BUILTIN_SOURCE)
        expected = {"Desk lamp": 1275150, "Travel mug": 962775, "Field notebook": 784010, "Cable kit": 456038}
        independent = {}
        for row in csv.DictReader(io.StringIO(FIXTURE.decode())):
            if "2026-07-01" <= row["date"] <= "2026-09-30":
                whole, fraction = row["revenue_rm"].split(".")
                independent[row["product"]] = independent.get(row["product"], 0) + int(whole) * 100 + int(fraction)
        self.assertEqual(independent, expected)
        self.assertEqual([(p.product, int(p.total * 100)) for p in result.calculation.products], [(k, expected[k]) for k in ("Desk lamp", "Travel mug", "Field notebook")])
        self.assertEqual([p.contributing_record_ordinals for p in result.calculation.products], [(3, 7, 11), (5, 9, 13), (2, 6, 10)])
        self.assertEqual(to_wire(result.quality), {"total_records": 14, "in_period_records": 12, "outside_period_records": 2, "used_records": 12, "missing_metric_records": 0, "missing_record_ordinals": []})
        self.assertEqual(result.provenance.dataset_sha256, hashlib.sha256(FIXTURE).hexdigest())
        self.assertEqual(result.provenance.source_kind, "built_in_synthetic")
        self.assertEqual(result.chart.kind, "bar")
        self.assertEqual([p.value for p in result.chart.data], [p.total for p in result.calculation.products])
        self.assertEqual([str(p.total) for p in result.calculation.products], ["12751.50", "9627.75", "7840.10"])

    def test_inclusive_narrowing_and_request_isolation(self):
        original = report(RANK)
        narrowed = report("top 10 products by revenue_rm from 2026-09-30 to 2026-09-30")
        self.assertEqual(narrowed.quality.used_records, 4)
        self.assertEqual(narrowed.quality.outside_period_records, 10)
        self.assertEqual([str(p.total) for p in narrowed.calculation.products], ["4675.55", "3501.00", "2613.05", "2400.20"])
        self.assertEqual(report(RANK), original)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            original.plan.limit = 1

    def test_ties_use_exact_label_and_limit_is_at_most_n(self):
        data = csv_bytes([("2026-07-01", name, 1, "0.10") for name in ("z", "a", "A")])
        result = report(f"TOP 10 PRODUCTS BY REVENUE_RM {QUARTER.upper()}", data)
        self.assertEqual([p.product for p in result.calculation.products], ["A", "a", "z"])
        self.assertEqual([str(p.total) for p in result.calculation.products], ["0.10"] * 3)

    def test_missing_selected_values_and_other_metric_independence(self):
        data = csv_bytes([
            ("2026-07-01", "A", "", "0.10"),
            ("2026-08-01", "A", 0, "0.20"),
            ("2026-07-01", "B", "", ""),
            ("2026-08-01", "B", 5, ""),
            ("2026-07-01", "C", "", ""),
            ("2026-10-01", "D", "", ""),
        ])
        revenue = report(RANK, data)
        self.assertEqual([(p.product, str(p.total)) for p in revenue.calculation.products], [("A", "0.30")])
        self.assertEqual(revenue.quality.missing_record_ordinals, (3, 4, 5))
        self.assertEqual(revenue.quality.outside_period_records, 1)
        self.assertTrue(any("Incomplete observed subtotals" in text for text in revenue.interpretation))
        units = report(f"top 3 products by units {QUARTER}", data)
        self.assertEqual([(p.product, str(p.total)) for p in units.calculation.products], [("B", "5"), ("A", "0")])
        self.assertEqual(units.quality.missing_record_ordinals, (1, 3, 5))
        self.assertEqual(units.calculation.products[1].contributing_record_ordinals, (2,))

    def test_empty_interval_and_all_missing_are_distinct_no_data_counts(self):
        data = csv_bytes([("2026-07-01", "A", 0, ""), ("2026-07-02", "B", 1, "")])
        all_missing = analyze(RANK, data, "input")
        outside = analyze("monthly units from 2026-08-01 to 2026-08-31", data, "input")
        self.assertIsInstance(all_missing, NoData)
        self.assertEqual(all_missing.quality.missing_record_ordinals, (1, 2))
        self.assertEqual(all_missing.quality.used_records, 0)
        self.assertEqual(outside.quality.in_period_records, 0)
        self.assertEqual(outside.quality.outside_period_records, 2)
        self.assertNotIn("chart", to_wire(all_missing))
        self.assertNotIn("calculation", to_wire(outside))

    def test_monthly_order_clipping_missing_zero_and_null(self):
        data = csv_bytes([
            ("2026-03-03", "A", 0, "0.00"),
            ("2026-01-20", "A", 2, "1.00"),
            ("2026-04-02", "A", 5, "2.00"),
            ("2026-02-02", "A", "", "3.00"),
            ("2026-01-05", "A", 900, "9.00"),
        ])
        result = report("monthly units from 2026-01-15 to 2026-04-10", data)
        buckets = result.calculation.months
        self.assertEqual([b.month for b in buckets], ["2026-01", "2026-02", "2026-03", "2026-04"])
        self.assertEqual([b.total for b in buckets], [Decimal(2), None, Decimal(0), Decimal(5)])
        self.assertEqual([b.partial_calendar_month for b in buckets], [True, False, False, True])
        self.assertEqual(buckets[0].interval_start, date(2026, 1, 15))
        self.assertEqual(buckets[-1].interval_end, date(2026, 4, 10))
        self.assertEqual(buckets[1].missing_record_ordinals, (4,))
        self.assertEqual(buckets[1].missing_metric_records, 1)
        self.assertEqual([b.contributing_record_ordinals for b in buckets], [(2,), (), (1,), (3,)])
        xml = ET.fromstring(render_svg(result.chart))
        lines = xml.findall("svg:g/svg:polyline", NS)
        self.assertEqual(len(lines), 1)
        points = lines[0].attrib["points"].split()
        circles = xml.findall("svg:g/svg:circle", NS)
        self.assertEqual([c.attrib["data-value"] for c in circles], ["2", "0", "5"])
        self.assertEqual(points, [f'{c.attrib["cx"]},{c.attrib["cy"]}' for c in circles[1:]])

    def test_one_observed_month_uses_table_even_with_empty_months(self):
        data = csv_bytes([("2026-08-01", "A", 0, "0.00")])
        result = report(f"monthly units {QUARTER}", data)
        self.assertEqual(result.chart.kind, "table")
        self.assertEqual([item.value for item in result.chart.data], [None, Decimal(0), None])
        xml = ET.fromstring(render_svg(result.chart))
        self.assertIn("No observed value", " ".join(xml.itertext()))
        self.assertEqual(len(xml.findall(".//svg:polyline", NS)), 0)

    def test_monthly_maximum_span_has_thirteen_buckets(self):
        data = csv_bytes([("2026-01-02", "A", 1, "1")])
        result = report("monthly units from 2026-01-02 to 2027-01-02", data)
        self.assertEqual(len(result.calculation.months), 13)
        self.assertEqual(result.calculation.months[-1].month, "2027-01")
        self.assertTrue(result.calculation.months[0].partial_calendar_month)
        self.assertTrue(result.calculation.months[-1].partial_calendar_month)

    def test_describe_uses_records_and_sample_denominator(self):
        data = csv_bytes([("2026-07-01", "A", 1, "0.01"), ("2026-07-02", "A", 2, "0.02"), ("2026-07-01", "B", 3, "0.03"), ("2026-07-02", "B", 4, "0.04")])
        for metric, expected in (
            ("units", {"sum": "10", "minimum": "1", "maximum": "4", "mean": "2.500000", "median": "2.500000", "sample_standard_deviation": "1.290994"}),
            ("revenue_rm", {"sum": "0.10", "minimum": "0.01", "maximum": "0.04", "mean": "0.025000", "median": "0.025000", "sample_standard_deviation": "0.012910"}),
        ):
            with self.subTest(metric=metric):
                result = report(f"describe {metric} {QUARTER}", data)
                self.assertEqual(result.calculation.count, 4)
                for name, value in expected.items():
                    self.assertEqual(str(getattr(result.calculation, name)), value)
                self.assertEqual(result.calculation.contributing_record_ordinals, (1, 2, 3, 4))
                self.assertEqual(result.chart.kind, "table")
                self.assertEqual(dict((item.label, item.value) for item in result.chart.data)["sample_standard_deviation"], result.calculation.sample_standard_deviation)

    def test_singleton_describe_has_undefined_sample_deviation(self):
        result = report(f"describe units {QUARTER}", csv_bytes([("2026-07-01", "A", 0, "0.00")]))
        self.assertEqual(result.calculation.count, 1)
        self.assertIsNone(result.calculation.sample_standard_deviation)
        self.assertIn("n-1 is zero", result.calculation.standard_deviation_note)
        self.assertEqual(str(result.calculation.mean), "0.000000")
        self.assertIn("Undefined for one observation", render_svg(result.chart))

    def test_half_even_mean_and_local_decimal_context(self):
        rows = [(str(date(2026, 1, 1) + timedelta(days=index)), "A", 0, "0.00") for index in range(128)]
        for numerator, expected in ((1, "0.007812"), (3, "0.023438")):
            with self.subTest(numerator=numerator):
                rows[0] = ("2026-01-01", "A", numerator, "0.00")
                with localcontext() as context:
                    context.prec = 2
                    context.traps[Inexact] = True
                    context.traps[Rounded] = True
                    original_flags = dict(getcontext().flags)
                    result = report("describe units from 2026-01-01 to 2026-12-31", csv_bytes(rows))
                    self.assertEqual(str(result.calculation.mean), expected)
                    self.assertEqual(context.prec, 2)
                    self.assertEqual(getcontext().flags, original_flags)
                    ET.fromstring(render_svg(result.chart))

    def test_exact_large_sums_at_all_row_product_and_number_limits(self):
        rows = [(str(date(2026, 7, 1) + timedelta(days=index // 20)), f"P{index % 20:02d}", "1000000000", "1000000000.00") for index in range(1000)]
        data = csv_bytes(rows)
        money = report(f"describe revenue_rm {QUARTER}", data)
        units = report(f"describe units {QUARTER}", data)
        self.assertEqual(str(money.calculation.sum), "1000000000000.00")
        self.assertEqual(str(units.calculation.sum), "1000000000000")
        self.assertEqual(str(money.calculation.sample_standard_deviation), "0.000000")
        self.assertEqual(money.quality.used_records, 1000)

    def test_hash_is_exact_bytes_and_synthetic_claim_requires_fixture_identity(self):
        changed_line_endings = FIXTURE.replace(b"\n", b"\r\n")
        original = report(RANK, label=BUILTIN_SOURCE)
        changed = report(RANK, changed_line_endings, BUILTIN_SOURCE)
        supplied = report(RANK, FIXTURE, "file:copied-fixture.csv")
        self.assertEqual(changed.calculation, original.calculation)
        self.assertNotEqual(changed.provenance.dataset_sha256, original.provenance.dataset_sha256)
        self.assertEqual(changed.provenance.dataset_sha256, hashlib.sha256(changed_line_endings).hexdigest())
        self.assertEqual(changed.provenance.source_kind, "user_supplied")
        self.assertEqual(supplied.provenance.source_kind, "user_supplied")

    def test_xml_escapes_labels_and_json_has_only_decimal_strings(self):
        label = '<script>&"\'unsafe'
        data = csv_bytes([("2026-07-01", label, 1, "0.10"), ("2026-07-02", label, 2, "0.20")])
        outcome = analyze(RANK, data, "file:source")
        payload = json.loads(outcome_json(outcome))
        self.assertEqual(payload["report"]["calculation"]["products"][0]["total"], "0.30")
        xml = ET.fromstring(render_svg(outcome.report.chart))
        self.assertIsNone(xml.find(".//svg:script", NS))
        rect = xml.find('.//svg:rect[@data-label]', NS)
        self.assertEqual(rect.attrib["data-label"], label)
        self.assertEqual(rect.attrib["data-value"], "0.30")
        self.assertIn(label, " ".join(xml.itertext()))
        self.assertIsNotNone(xml.find('.//svg:line[@data-role="zero-baseline"]', NS))

    def test_zero_charts_have_finite_coordinates(self):
        data = csv_bytes([("2026-07-01", "A", 0, "0.00"), ("2026-08-01", "A", 0, "0.00")])
        for question in (RANK, f"monthly units {QUARTER}"):
            with self.subTest(question=question):
                text = render_svg(report(question, data).chart)
                ET.fromstring(text)
                self.assertNotIn("NaN", text)
                self.assertNotIn("Infinity", text)

    def test_maximum_labels_and_large_axis_values_fit_svg_bounds(self):
        data = csv_bytes([
            (str(date(2026, 7, 1) + timedelta(days=index // 20)),
             "W" * 38 + f"{index % 20:02d}", "1000000000", "1000000000.00")
            for index in range(1000)
        ])
        bar = ET.fromstring(render_svg(report(RANK, data).chart))
        for label in bar.findall('.//svg:text[@textLength]', NS):
            self.assertLess(float(label.attrib["x"]) + float(label.attrib["textLength"]), 390)
        result = report(f"monthly revenue_rm {QUARTER}", data)
        line = ET.fromstring(render_svg(result.chart))
        maximum_label = line.find('.//svg:text[@textLength]', NS)
        self.assertGreater(float(maximum_label.attrib["x"]) - float(maximum_label.attrib["textLength"]), 0)
        circles = line.findall('.//svg:circle', NS)
        self.assertEqual([circle.attrib["data-value"] for circle in circles], [str(item.value) for item in result.chart.data if item.value is not None])
        self.assertTrue(all(circle.find("svg:title", NS) is not None for circle in circles))


class ValidationTests(unittest.TestCase):
    def test_complete_question_grammar_rejects_unsupported_intent_before_dataset(self):
        questions = [
            "", "x" * 257, f"top 0 products by revenue_rm {QUARTER}", f"top 11 products by revenue_rm {QUARTER}",
            f"top +3 products by revenue_rm {QUARTER}", f"top ٣ products by revenue_rm {QUARTER}",
            f"top 3 products by profit {QUARTER}", f"monthly unıts {QUARTER}",
            RANK + "; write /tmp/pwn", RANK + " and normalize", "please " + RANK,
            "top 3 products by revenue_rm from 2026-07-01", "monthly units for Q3 2026",
            "describe units from 2026-02-29 to 2026-03-01", "describe units from 2026-9-01 to 2026-09-30",
            "monthly units from 1999-12-31 to 2000-01-01", "monthly units from 2100-12-31 to 2101-01-01",
            "monthly units from 2026-07-02 to 2026-07-01", "monthly units from 2026-01-01 to 2027-01-02",
            "monthly units from ２０２６-07-01 to 2026-09-30", "monthly\tunits " + QUARTER,
        ]
        for question in questions:
            with self.subTest(question=question):
                outcome = analyze(question, b"not csv", "input")
                self.assertIsInstance(outcome, NeedsClarification)
                self.assertNotIn("calculation", to_wire(outcome))

    def test_valid_boundaries_case_and_surrounding_whitespace(self):
        result = report(" \nTOP 03 PRODUCTS BY UNITS FROM 2026-07-01 TO 2026-09-30\t")
        self.assertEqual(result.plan.limit, 3)
        self.assertEqual(result.plan.metric, "units")
        for day in ("2000-02-29", "2100-12-31"):
            with self.subTest(day=day):
                data = csv_bytes([(day, "A" * 40, "0000000000000", "0000000000.00")])
                self.assertEqual(report(f"describe units from {day} to {day}", data).calculation.count, 1)

    def test_exact_csv_schema_and_all_records_validated(self):
        good = ["2026-07-01", "A", "1", "1.00"]
        malformed = [
            b"", b"\xff", b"\xef\xbb\xbf" + csv_bytes([good]),
            csv_bytes([], header=("date", "product", "units", "revenue_rm")),
            csv_bytes([good], header=("date", "product", "revenue_rm", "units")),
            csv_bytes([good], header=("date", "product", "units", "units")),
            csv_bytes([good], header=("date", "product", "units", "revenue_rm", "extra")),
            csv_bytes([good[:3]]), csv_bytes([good + ["extra"]]), csv_bytes([good, good]),
            csv_bytes([good]) + b"\n", b'date,product,units,revenue_rm\n2026-07-01,"unterminated,1,1.00',
            csv_bytes([good, ("2026-10-01", "SECRET_PRIVATE_CELL", "NaN", "1.00")]),
        ]
        for data in malformed:
            with self.subTest(data=data[:70]):
                outcome = analyze(RANK, data, "input")
                self.assertIsInstance(outcome, Failure)
                self.assertEqual(outcome.status, "invalid_dataset")
                self.assertNotIn("SECRET_PRIVATE_CELL", outcome.message)

    def test_numeric_lexical_domain(self):
        invalid = [" ", "1 ", "+1", "-1", "1e2", "NaN", "Infinity", "1_000", "١", "１", "9" * 14, "1000000001"]
        for metric in ("units", "revenue_rm"):
            for token in invalid + (["1.0"] if metric == "units" else ["0.001", "1.", ".5", "1000000000.01"]):
                with self.subTest(metric=metric, token=token):
                    cells = ["2026-07-01", "A", "1", "1.00"]
                    cells[2 if metric == "units" else 3] = token
                    self.assertEqual(analyze(RANK, csv_bytes([cells]), "input").status, "invalid_dataset")

    def test_product_date_row_and_byte_bounds(self):
        for product in ("", " A", "A ", "A\nB", "A\tB", "A\x7f", "é", "A" * 41):
            with self.subTest(product=repr(product)):
                self.assertEqual(analyze(RANK, csv_bytes([("2026-07-01", product, 1, "1")]), "input").status, "invalid_dataset")
        for day in ("1999-01-01", "2101-01-01", "2026-02-29", "2026-7-01", "2026-W27-3"):
            with self.subTest(day=day):
                self.assertEqual(analyze(RANK, csv_bytes([(day, "A", 1, "1")]), "input").status, "invalid_dataset")
        rows = [(str(date(2026, 1, 1) + timedelta(days=index // 20)), f"P{index % 20}", 1, "1") for index in range(1001)]
        for data in (csv_bytes(rows), csv_bytes([("2026-07-01", f"P{i}", 1, "1") for i in range(21)]), b"a" * (MAX_BYTES + 1)):
            with self.subTest(size=len(data)):
                self.assertEqual(analyze(RANK, data, "input").status, "invalid_dataset")

    def test_multiline_invalid_record_uses_record_ordinal(self):
        data = csv_bytes([("2026-07-01", "A", 1, "1"), ("2026-07-02", "bad\nlabel", 1, "1")])
        outcome = analyze(RANK, data, "input")
        self.assertIn("Record 2", outcome.message)
        self.assertNotIn("bad", outcome.message)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)

    def command(self, *args):
        return [sys.executable, "-m", "data_analysis_agent.cli", *args]

    def run_cli(self, *args):
        process = subprocess.run(self.command(*args), cwd=self.root, capture_output=True, text=True, timeout=10)
        return process, json.loads(process.stdout)

    def run_main(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cli.main(list(args))
        return code, json.loads(output.getvalue())

    def test_real_cli_defaults_write_nothing_and_help_runs(self):
        process, result = self.run_cli("--question", RANK)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["report"]["provenance"]["source_kind"], "built_in_synthetic")
        self.assertEqual(list(self.root.iterdir()), [])
        help_result = subprocess.run(self.command("--help"), cwd=self.root, capture_output=True, text=True, timeout=10)
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("--dataset", help_result.stdout)

    def test_real_cli_publishes_same_json_and_chart_preserving_source(self):
        source = self.root / "source.csv"
        source.write_bytes(FIXTURE)
        destination = self.root / "result"
        process, result = self.run_cli("--question", RANK, "--dataset", str(source), "--output", str(destination))
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads((destination / "report.json").read_text()), result)
        self.assertEqual(source.read_bytes(), FIXTURE)
        self.assertEqual(result["report"]["provenance"]["source_kind"], "user_supplied")
        self.assertEqual(sorted(p.name for p in destination.iterdir()), ["chart.svg", "report.json"])
        xml = ET.parse(destination / "chart.svg")
        values = [element.attrib["data-value"] for element in xml.findall('.//svg:rect[@data-value]', NS)]
        self.assertEqual(values, [datum["value"] for datum in result["report"]["chart"]["data"]])

    def test_real_cli_existing_destinations_and_symlink_parents_fail_unchanged(self):
        existing = self.root / "existing"
        existing.mkdir()
        (existing / "keep.txt").write_text("keep")
        file = self.root / "file"
        file.write_text("keep-file")
        link = self.root / "link"
        link.symlink_to(existing, target_is_directory=True)
        dangling = self.root / "dangling"
        dangling.symlink_to(self.root / "absent")
        for destination in (existing, file, link, dangling, link / "new", link / ".." / "escape", self.root / "absent-parent" / "new"):
            with self.subTest(destination=destination):
                process, result = self.run_cli("--question", RANK, "--output", str(destination))
                self.assertEqual((process.returncode, result["status"]), (3, "output_error"))
        self.assertEqual((existing / "keep.txt").read_text(), "keep")
        self.assertEqual(list(existing.iterdir()), [existing / "keep.txt"])
        self.assertEqual(file.read_text(), "keep-file")
        self.assertTrue(link.is_symlink())
        self.assertTrue(dangling.is_symlink())
        self.assertFalse((self.root / "escape").exists())

    def test_real_cli_nonregular_input_missing_file_and_byte_limit(self):
        source = self.root / "source.csv"
        source.write_bytes(FIXTURE)
        symlink = self.root / "symlink.csv"
        symlink.symlink_to(source)
        fifo = self.root / "pipe.csv"
        os.mkfifo(fifo)
        for path in (self.root, symlink, fifo, self.root / "missing.csv"):
            with self.subTest(path=path):
                process, result = self.run_cli("--question", RANK, "--dataset", str(path))
                self.assertEqual((process.returncode, result["status"]), (3, "input_error"))
                self.assertEqual(process.stderr, "")
        oversized = self.root / "large.csv"
        oversized.write_bytes(b"x" * (MAX_BYTES + 1))
        process, result = self.run_cli("--question", RANK, "--dataset", str(oversized))
        self.assertEqual((process.returncode, result["status"]), (3, "invalid_dataset"))

    def test_clarification_does_not_open_dataset_or_create_output(self):
        destination = self.root / "result"
        with patch.object(cli, "read_dataset", side_effect=AssertionError("read was not authorized")):
            code, result = self.run_main("--question", "delete files", "--dataset", "/missing", "--output", str(destination))
        self.assertEqual((code, result["status"]), (2, "needs_clarification"))
        self.assertFalse(destination.exists())

    def test_no_data_and_invalid_dataset_produce_no_artifacts(self):
        source = self.root / "source.csv"
        destination = self.root / "result"
        for data, expected, code in ((csv_bytes([("2026-07-01", "A", 1, "")]), "no_data", 2), (b"private raw text", "invalid_dataset", 3)):
            with self.subTest(expected=expected):
                source.write_bytes(data)
                process, result = self.run_cli("--question", RANK, "--dataset", str(source), "--output", str(destination))
                self.assertEqual((process.returncode, result["status"]), (code, expected))
                self.assertFalse(destination.exists())
                self.assertNotIn("private raw text", process.stdout)

    def test_read_is_bounded_even_when_stat_underreports_size(self):
        source = self.root / "source.csv"
        source.write_bytes(b"x" * (MAX_BYTES + 100))
        fake_stat = os.stat_result((source.stat().st_mode, 0, 0, 0, 0, 0, 1, 0, 0, 0))
        original_fdopen = os.fdopen
        amounts = []

        class BoundedReader:
            def __init__(self, descriptor, mode):
                self.stream = original_fdopen(descriptor, mode)

            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.stream.close()

            def fileno(self):
                return self.stream.fileno()

            def read(self, amount):
                amounts.append(amount)
                return self.stream.read(amount)

        with patch.object(cli.os, "fstat", return_value=fake_stat), patch.object(cli.os, "fdopen", BoundedReader):
            with self.assertRaisesRegex(cli.InvalidDataset, "256 KiB"):
                cli.read_dataset(source)
        self.assertEqual(len(amounts), 1)
        self.assertGreater(amounts[0], 0)
        self.assertLessEqual(amounts[0], MAX_BYTES + 1)

    def test_competing_cli_commands_have_exactly_one_output_owner(self):
        destination = self.root / "shared"
        commands = [subprocess.Popen(self.command("--question", RANK, "--output", str(destination)), cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        results = []
        for process in commands:
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(stderr, "")
            results.append((process.returncode, json.loads(stdout)))
        self.assertEqual(sorted(code for code, _ in results), [0, 3])
        winner = next(result for code, result in results if code == 0)
        self.assertEqual(json.loads((destination / "report.json").read_text()), winner)
        self.assertEqual(next(result["status"] for code, result in results if code == 3), "output_error")
        ET.parse(destination / "chart.svg")

    def test_write_failures_and_keyboard_interrupt_clean_owned_artifacts(self):
        original_open = Path.open

        class InterruptedWriter:
            def __init__(self, stream, failure):
                self.stream, self.failure = stream, failure

            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.stream.close()

            def write(self, text):
                self.stream.write(text[:20])
                raise self.failure

        for failure, expected, code in ((OSError("injected write failure"), "output_error", 3), (KeyboardInterrupt(), "cancelled", 130)):
            with self.subTest(expected=expected):
                destination = self.root / expected

                def faulty_open(path, *args, **kwargs):
                    stream = original_open(path, *args, **kwargs)
                    return InterruptedWriter(stream, failure) if path.name == "chart.svg" else stream

                with patch.object(Path, "open", faulty_open):
                    actual_code, result = self.run_main("--question", RANK, "--output", str(destination))
                self.assertEqual((actual_code, result["status"]), (code, expected))
                self.assertFalse(destination.exists())
                self.assertEqual(list(self.root.iterdir()), [])

    def test_sigint_during_ownership_acquisition_cleans_output_and_restores_handler(self):
        original_mkdir, original_open = Path.mkdir, Path.open
        previous_handler = signal.getsignal(signal.SIGINT)
        for acquisition in ("directory", "report.json", "chart.svg"):
            with self.subTest(acquisition=acquisition):
                destination = self.root / acquisition
                opened = []

                def interrupted_mkdir(path, *args, **kwargs):
                    result = original_mkdir(path, *args, **kwargs)
                    if path == destination and acquisition == "directory":
                        os.kill(os.getpid(), signal.SIGINT)
                    return result

                def interrupted_open(path, *args, **kwargs):
                    stream = original_open(path, *args, **kwargs)
                    if path.parent == destination and path.name == acquisition:
                        opened.append(stream)
                        os.kill(os.getpid(), signal.SIGINT)
                    return stream

                with patch.object(Path, "mkdir", interrupted_mkdir), patch.object(Path, "open", interrupted_open):
                    code, result = self.run_main("--question", RANK, "--output", str(destination))
                self.assertEqual((code, result["status"]), (130, "cancelled"))
                self.assertFalse(destination.exists())
                self.assertTrue(all(stream.closed for stream in opened))
                self.assertIs(signal.getsignal(signal.SIGINT), previous_handler)
                code, result = self.run_main("--question", RANK, "--output", str(destination))
                self.assertEqual((code, result["status"]), (0, "completed"))
                self.assertEqual(sorted(path.name for path in destination.iterdir()), ["chart.svg", "report.json"])

    def test_cancelled_input_and_programming_failures_do_not_become_success(self):
        with patch.object(cli, "read_dataset", side_effect=KeyboardInterrupt()):
            code, result = self.run_main("--question", RANK)
        self.assertEqual((code, result["status"]), (130, "cancelled"))
        with patch.object(cli, "analyze", side_effect=RuntimeError("implementation defect")):
            with self.assertRaisesRegex(RuntimeError, "implementation defect"):
                self.run_main("--question", RANK)


if __name__ == "__main__":
    unittest.main()
