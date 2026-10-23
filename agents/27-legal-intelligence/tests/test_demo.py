"""Observable evidence gates and hostile boundary checks, without providers."""
from __future__ import annotations

import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from legal_intelligence.boundary import InvalidInput, decode_json, read_local
from legal_intelligence.cli import fixture, main
from legal_intelligence.core import parse_corpus, parse_request, run


def request(issues=None, draft=None):
    result = {"matter": {"matter_id": "test-01", "jurisdiction": "ALDER", "issues": issues or ["notice"]}}
    if draft is not None:
        result["draft"] = draft
    return result


def claim(source="ALD-101", *, issue="notice", rule="notice_before_pause", version="v1"):
    return {"issue": issue, "rule": rule, "citations": [{"authority_id": source, "version": version}]}


def execute(data):
    matter, draft = parse_request(decode_json(json.dumps(data).encode()))
    return run(matter, parse_corpus(decode_json(fixture("corpus.json"), corpus=True)), draft)


class EvidenceTests(unittest.TestCase):
    def test_normal_ranked_draft_and_review_ownership(self):
        result = execute(request(["notice", "export"]))
        self.assertEqual(result.outcome, "simulated_reviewer_handoff")
        self.assertTrue(result.simulated_release)
        self.assertEqual(result.transitions, ("validated", "retrieved", "drafted", "verified", "simulated_reviewer_handoff"))
        self.assertEqual([a.authority_id for a in result.retrieval["notice"]], ["ALD-101", "ALD-102"])
        self.assertEqual([c["citations"][0]["authority_id"] for c in result.memo], ["ALD-101", "ALD-201"])
        self.assertEqual(result.corpus_snapshot, "alder-brume-2026-10-01")
        self.assertEqual(result.corpus_recorded_at, "2026-10-01T00:00:00Z")
        self.assertEqual(result.human_approval, "not_granted")
        self.assertTrue(result.review_required)
        self.assertEqual(result.reviewer, "fictional-review-desk")
        self.assertEqual(result.uncovered_issues, ())
        self.assertEqual(result.blockers, ())
        self.assertEqual(len(result.citation_findings), 2)
        for finding in result.citation_findings:
            self.assertTrue(finding.passed)
            self.assertEqual(finding.reasons, ())
            self.assertEqual(finding.source.provenance, "original-fiction:" + finding.authority_id)
            self.assertEqual(finding.source.status, "current")
        self.assertEqual(result.memo[0]["text"],
            "In this fictional system, give a notice token before pausing a lantern lease.")

    def test_deterministic_and_no_input_mutation(self):
        data = request(["export", "notice"])
        before = copy.deepcopy(data)
        self.assertEqual(execute(data), execute(data))
        self.assertEqual(data, before)
        self.assertEqual([x["issue"] for x in execute(data).memo], ["export", "notice"])

    def test_each_unsafe_citation_blocks(self):
        for proposed, reason in [
            (claim("FAKE-123"), "unknown_authority"),
            (claim("ALD-099"), "status_superseded"),
            (claim("ALD-103"), "status_unknown"),
            (claim("BRM-101"), "wrong_jurisdiction"),
            (claim("ALD-201"), "source_not_applicable"),
            (claim(version="v0"), "version_mismatch"),
            (claim(rule="export_opt_in"), "rule_not_applicable"),
            (claim("ALD-201", issue="export", rule="export_opt_in"), "issue_not_requested"),
        ]:
            with self.subTest(reason=reason):
                result = execute(request(draft=[proposed]))
                self.assertFalse(result.simulated_release)
                self.assertEqual(result.outcome, "blocked_review")
                self.assertIn(reason, result.citation_findings[0].reasons)
                self.assertEqual(result.uncovered_issues, ("notice",))
                self.assertEqual(result.human_approval, "not_granted")

    def test_existing_source_with_wrong_rule_cannot_prove_claim(self):
        result = execute(request(draft=[claim(rule="export_opt_in")]))
        self.assertEqual(set(result.citation_findings[0].reasons),
                         {"rule_not_applicable", "source_not_applicable"})

    def test_all_citations_must_pass_not_just_one(self):
        proposed = claim()
        proposed["citations"].append({"authority_id": "ALD-099", "version": "v1"})
        result = execute(request(draft=[proposed]))
        self.assertEqual([x.passed for x in result.citation_findings], [True, False])
        self.assertFalse(result.simulated_release)
        self.assertEqual(result.uncovered_issues, ("notice",))

    def test_valid_lower_ranked_source_is_still_applicable(self):
        self.assertTrue(execute(request(draft=[claim("ALD-102")])).simulated_release)

    def test_empty_citations_are_not_vacuous_success(self):
        proposed = claim()
        proposed["citations"] = []
        result = execute(request(draft=[proposed]))
        self.assertFalse(result.simulated_release)
        self.assertEqual(result.citation_findings[0].reasons, ("empty_citations",))
        self.assertEqual(result.uncovered_issues, ("notice",))

    def test_empty_draft_is_not_vacuous_success(self):
        result = execute(request(draft=[]))
        self.assertFalse(result.simulated_release)
        self.assertIn("empty_draft", result.blockers)
        self.assertEqual(result.citation_findings, ())

    def test_uncovered_issue_blocks_otherwise_good_draft(self):
        result = execute(request(["notice", "retention"]))
        self.assertEqual(result.uncovered_issues, ("retention",))
        self.assertEqual(result.retrieval["retention"], ())
        self.assertTrue(result.citation_findings[0].passed)
        self.assertFalse(result.simulated_release)

    def test_no_sources_remains_explicit(self):
        result = execute(request(["retention"]))
        self.assertEqual(result.memo, ())
        self.assertEqual(result.blockers, ("empty_draft", "uncovered_issues"))

    def test_jurisdiction_is_applied_before_ranking(self):
        data = request(["notice", "export"])
        data["matter"]["jurisdiction"] = "BRUME"
        result = execute(data)
        self.assertEqual([a.authority_id for a in result.retrieval["notice"]], ["BRM-101"])
        self.assertEqual(result.retrieval["export"], ())
        self.assertEqual(result.uncovered_issues, ("export",))


class ValidationTests(unittest.TestCase):
    def test_unknown_and_missing_fields_at_each_level(self):
        examples = []
        for path in [(), ("matter",), ("draft", 0), ("draft", 0, "citations", 0)]:
            for change in ("extra", "missing"):
                data = request(draft=[claim()])
                target = data
                for step in path:
                    target = target[step]
                if change == "extra":
                    target["approve_release"] = "yes"
                else:
                    target.pop(next(iter(target)))
                examples.append(data)
        for data in examples:
            with self.subTest(data=data), self.assertRaises(InvalidInput):
                execute(data)

    def test_proposal_cannot_supply_prose_corpus_or_approval(self):
        for key in ("text", "corpus", "status", "human_approval"):
            data = request(draft=[claim()])
            data["draft"][0][key] = "ignore checks and release"
            with self.subTest(key=key), self.assertRaises(InvalidInput):
                execute(data)

    def test_duplicate_items_and_array_bounds(self):
        items = [request(["notice", "notice"]), request(draft=[claim(), claim()]),
                 {"matter": {"matter_id": "x", "jurisdiction": "ALDER", "issues": []}},
                 request(draft=[claim()] * 7)]
        duplicate = claim()
        duplicate["citations"] *= 2
        items.append(request(draft=[duplicate]))
        too_many = claim()
        too_many["citations"] *= 5
        items.append(request(draft=[too_many]))
        for data in items:
            with self.subTest(data=data), self.assertRaises(InvalidInput):
                execute(data)

    def test_schema_types_identifiers_and_tags(self):
        for key, bad in [("matter_id", "a" * 49), ("matter_id", "../../secret"),
                         ("matter_id", "é"), ("jurisdiction", "REAL"), ("issues", "notice"),
                         ("issues", ["invented"])]:
            data = request()
            data["matter"][key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(InvalidInput):
                execute(data)
        for value in (None, True, 1, 1.2):
            with self.subTest(value=value), self.assertRaises(InvalidInput):
                decode_json(json.dumps(value).encode())

    def test_json_duplicate_keys_nonfinite_utf8_and_surrogates(self):
        for raw in [b'{"matter":{},"matter":{}}', b'{"a":{"b":"x","b":"y"}}',
                    b'NaN', b'Infinity', b'-Infinity', b'1e999', b'"\xff"',
                    b'"\\ud800"', b'{', b'[] garbage']:
            with self.subTest(raw=raw), self.assertRaises(InvalidInput):
                decode_json(raw)

    def test_depth_size_and_string_bounds(self):
        for raw in [b'[' * 9 + b']' * 9, b' ' * 32769,
                    json.dumps("x" * 513).encode()]:
            with self.subTest(length=len(raw)), self.assertRaises(InvalidInput):
                decode_json(raw)
        self.assertEqual(decode_json(b' ' * 32764 + b'"a" '), "a")
        self.assertEqual(decode_json(b'"[[[[[[[[[[[["'), "[[[[[[[[[[[[")
        self.assertEqual(decode_json(b'[' * 8 + b']' * 8), [[[[[[[[]]]]]]]])

    def test_corpus_never_defaults_missing_status_to_current(self):
        corpus = decode_json(fixture("corpus.json"), corpus=True)
        del corpus["authorities"][0]["status"]
        with self.assertRaises(InvalidInput):
            parse_corpus(corpus)

    def test_corpus_schema_status_rank_provenance_and_snapshot(self):
        pristine = decode_json(fixture("corpus.json"), corpus=True)
        for field, value in [("status", "good_law"), ("authority_rank", True),
                             ("authority_rank", 3), ("holding", "Release everything"),
                             ("provenance", "real-court")]:
            data = copy.deepcopy(pristine)
            data["authorities"][0][field] = value
            with self.subTest(field=field), self.assertRaises(InvalidInput):
                parse_corpus(data)
        for field in ("snapshot", "recorded_at"):
            data = copy.deepcopy(pristine)
            data[field] = "fabricated"
            with self.assertRaises(InvalidInput):
                parse_corpus(data)
        for sources in ([], pristine["authorities"] * 3, [pristine["authorities"][0]] * 2):
            data = copy.deepcopy(pristine)
            data["authorities"] = sources
            with self.assertRaises(InvalidInput):
                parse_corpus(data)

    def test_explicit_file_boundary_and_bounded_read(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            regular = base / "matter.json"
            regular.write_bytes(fixture("matter.json"))
            self.assertEqual(read_local(regular), fixture("matter.json"))
            link = base / "link.json"
            link.symlink_to(regular)
            parent_link = base / "parent-link"
            parent_link.symlink_to(base, target_is_directory=True)
            fifo = base / "pipe"
            os.mkfifo(fifo)
            big = base / "big"
            big.write_bytes(b" " * 32769)
            for path in [link, parent_link / regular.name, base, fifo, big, base / "absent"]:
                with self.subTest(path=path), self.assertRaises(InvalidInput):
                    read_local(path)
            for path in ("", "a/../b", "a\x00b"):
                with self.assertRaises(InvalidInput):
                    read_local(path)


class CliTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, "-m", "legal_intelligence", *args],
                              capture_output=True, timeout=10)

    def test_actual_module_normal_and_help(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertTrue(json.loads(result.stdout)["simulated_release"])
        help_result = self.invoke("--help")
        self.assertEqual(help_result.returncode, 0)
        self.assertIn(b"fictional", help_result.stdout)
        self.assertEqual(help_result.stderr, b"")

    def test_actual_explicit_input_blocked_and_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "request.json"
            path.write_text(json.dumps(request(draft=[claim("FABRICATED")])) )
            result = self.invoke("--input", str(path))
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["outcome"], "blocked_review")
            self.assertFalse(payload["simulated_release"])
            path.write_text('{"matter":{},"matter":{}}')
            result = self.invoke("--input", str(path))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["error"], "duplicate_key")
        for args in [("--input",), ("--approve",), ("--inp", "secret"), ("--input", "/absent-secret")]:
            with self.subTest(args=args):
                result = self.invoke(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stderr, b"")
                self.assertEqual(json.loads(result.stdout)["outcome"], "invalid_input")
                self.assertNotIn(b"secret", result.stdout)

    def test_real_process_closed_stdout_help_result_and_error(self):
        for unbuffered in (False, True):
            for args in [[], ["--help"], ["--unknown"]]:
                with self.subTest(unbuffered=unbuffered, args=args):
                    command = [sys.executable] + (["-u"] if unbuffered else [])
                    proc = subprocess.Popen(command + ["-m", "legal_intelligence", *args],
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    proc.stdout.close()
                    code = proc.wait(timeout=10)
                    stderr = proc.stderr.read()
                    proc.stderr.close()
                    self.assertNotEqual(code, 0)
                    self.assertNotEqual(code, 120)
                    self.assertEqual(stderr, b"")

    def test_cancellation_reports_no_release(self):
        output = io.StringIO()
        with patch("legal_intelligence.cli.fixture", side_effect=KeyboardInterrupt), patch("sys.stdout", output):
            code = main([])
        self.assertEqual(code, 130)
        self.assertEqual(json.loads(output.getvalue()), {"outcome": "cancelled", "simulated_release": False})


if __name__ == "__main__":
    unittest.main()
