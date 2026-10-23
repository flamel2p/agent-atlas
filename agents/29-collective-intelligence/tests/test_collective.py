"""Behavior checks use independent arithmetic and real CLI subprocesses."""

from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import copy
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import unittest
from unittest.mock import patch

from collective_intelligence import load_request, run_session
from collective_intelligence import core
from collective_intelligence.core import InvalidInput

CASE = Path(__file__).resolve().parents[1]


def fixture(name="baseline"):
    return json.loads((CASE / "fixtures" / f"{name}.json").read_text())


def request(data):
    return load_request(json.dumps(data).encode())


class SessionTests(unittest.TestCase):
    def test_independent_weighted_scores_and_proposed_only_rubric(self):
        result = run_session(request(fixture()))
        self.assertEqual(result.status, "converged")
        self.assertEqual([d.score for d in result.rounds[-1].decisions],
                         [Fraction(25, 3), Fraction(35, 4), Fraction(17, 5)])
        self.assertEqual([d.selection for d in result.rounds[-1].decisions], ["accept", "accept", "reject"])
        self.assertEqual(result.rubric, (result.proposals[0].criterion, result.proposals[1].criterion))
        self.assertFalse(result.to_dict()["correctness_claim"])
        self.assertFalse(result.to_dict()["provisional"])

    def test_complete_coverage_and_no_self_review(self):
        result = run_session(request(fixture()))
        authors = {p.criterion.id: p.author_id for p in result.proposals}
        expected = {(r, c) for c, a in authors.items()
                    for r in ("pedagogy", "domain", "assessment") if r != a}
        for record in result.rounds:
            self.assertEqual(len(record.critiques), 6)
            self.assertEqual(set(record.expected_edges), expected)
            self.assertEqual({(c.reviewer_id, c.criterion_id) for c in record.critiques}, expected)
            self.assertEqual(record.missing_edges, ())
            self.assertTrue(all(c.reviewer_id != authors[c.criterion_id] for c in record.critiques))

    def test_initial_snapshot_identity_is_immutable_and_no_prior_argument(self):
        seen = []
        original = core.propose
        def observe(role, snapshot):
            seen.append(snapshot)
            return original(role, snapshot)
        with patch.object(core, "propose", observe):
            result = run_session(request(fixture()))
        self.assertEqual(len(seen), 3)
        self.assertTrue(all(snapshot is seen[0] for snapshot in seen))
        self.assertTrue(all(p.snapshot is seen[0] for p in result.proposals))
        with self.assertRaises(FrozenInstanceError):
            seen[0].capacity = 999
        with self.assertRaises(FrozenInstanceError):
            result.proposals[0].criterion.text = "Altered"

    def test_host_rejects_adapter_proposal_and_review_forgery(self):
        original = core.propose
        def forged(role, snapshot):
            return replace(original(role, snapshot), author_id="forged")
        with patch.object(core, "propose", forged), self.assertRaises(InvalidInput):
            run_session(request(fixture()))
        bad = core.Critique("forged", "pedagogy", "c-pedagogy", Fraction(9), "Self score")
        with patch.object(core, "fixture_reviews", return_value=(bad,)), self.assertRaises(InvalidInput):
            run_session(request(fixture()))

    def test_host_weights_are_explicit_positive_and_finite(self):
        self.assertEqual([r.weight for r in core.ROLES], [3, 2, 1])
        for bad in (Fraction(0), Fraction(-1), True, float("inf"), float("nan")):
            with self.subTest(weight=bad), self.assertRaises(InvalidInput):
                core.validate_roles((replace(core.ROLES[0], weight=bad), *core.ROLES[1:]))

    def test_replay_reason_dissent_and_all_decision_links_are_faithful(self):
        data = fixture("replay")
        reason = "Reject: prose cannot demonstrate queue behavior."
        data["review_rounds"][1]["critiques"][-1]["reason"] = reason
        result = run_session(request(data))
        self.assertEqual(result.status, "converged")
        dissent = result.to_dict()["dissent"]
        self.assertEqual([c["id"] for c in dissent], ["r2-pedagogy-c-assessment", "r2-domain-c-assessment"])
        self.assertEqual(dissent[-1]["reason"], reason)
        for record in result.rounds:
            for decision in record.decisions:
                self.assertEqual(decision.critique_ids, tuple(c.id for c in record.critiques
                                 if c.criterion_id == decision.criterion.id))

    def test_single_round_is_budget_exhaustion(self):
        data = fixture()
        data["max_rounds"] = 1
        result = run_session(request(data))
        self.assertEqual(result.status, "unresolved")
        self.assertEqual(result.unresolved, ("budget_exhausted",))
        self.assertEqual(len(result.rounds), 1)
        self.assertTrue(result.to_dict()["provisional"])

    def test_missing_reviewer_never_shrinks_denominator(self):
        result = run_session(request(fixture("missing-reviewer")))
        decision = result.rounds[-1].decisions[0]
        self.assertEqual(result.status, "unresolved")
        self.assertEqual(len(result.rounds), 2)
        self.assertIsNone(decision.score)
        self.assertEqual((decision.expected_weight, decision.observed_weight), (3, 2))
        self.assertIn("c-pedagogy:missing_reviews", result.unresolved)
        self.assertEqual(len(result.rounds[-1].missing_edges), 2)
        self.assertNotIn("c-pedagogy", [c.id for c in result.rubric])

    def test_conflict_cannot_be_overruled_by_host_weight(self):
        result = run_session(request(fixture("conflicting-scores")))
        decision = result.rounds[-1].decisions[0]
        self.assertGreater(decision.score, 6)
        self.assertEqual(decision.selection, "defer")
        self.assertIn("contradictory_scores", decision.issues)
        self.assertEqual(result.status, "unresolved")
        self.assertTrue({"r2-domain-c-pedagogy", "r2-assessment-c-pedagogy"} <= {c.id for c in result.dissent})

    def test_threshold_and_reviewer_ties_are_unresolved(self):
        result = run_session(request(fixture("threshold-tie")))
        self.assertEqual(result.rounds[-1].decisions[-1].issues, ("threshold_tie", "reviewer_tie"))
        self.assertEqual(result.status, "unresolved")
        data = fixture("replay")
        for record in data["review_rounds"]:
            record["critiques"][0]["score"] = 6
        result = run_session(request(data))
        self.assertIn("reviewer_tie", result.rounds[-1].decisions[0].issues)
        self.assertEqual(result.status, "unresolved")

    def test_exact_convergence_movement_limit(self):
        data = fixture("replay")
        data["review_rounds"][1]["critiques"][2]["score"] = 9.333333333333
        self.assertEqual(run_session(request(data)).status, "converged")
        data["review_rounds"][1]["critiques"][2]["score"] = 9.333333333334
        result = run_session(request(data))
        self.assertEqual(result.status, "unresolved")
        self.assertEqual(result.unresolved, ("budget_exhausted",))

    def test_historical_dissent_survives_reconsideration(self):
        data = fixture("replay")
        first = data["review_rounds"][0]["critiques"][0]
        first.update(score=1, reason="First-round objection retained after reconsideration.")
        result = run_session(request(data))
        self.assertEqual(result.status, "unresolved")
        self.assertEqual(result.rounds[0].critiques[0].reason, first["reason"])
        self.assertEqual(result.rounds[0].decisions[0].selection, "defer")

    def test_empty_matrix_is_unresolved(self):
        data = fixture("replay")
        for record in data["review_rounds"]:
            record["critiques"] = []
        result = run_session(request(data))
        self.assertEqual(len(result.rounds[-1].missing_edges), 6)
        self.assertEqual(result.rubric, ())
        self.assertEqual(result.status, "unresolved")

    def test_exact_scores_survive_display_rounding(self):
        data = fixture("replay")
        data["review_rounds"][1]["critiques"][2]["score"] = 9.333333333333
        report = run_session(request(data)).to_dict()
        self.assertEqual(report["rounds"][1]["critiques"][2]["score_exact"],
                         {"numerator": 9333333333333, "denominator": 1000000000000})

    def test_run_state_is_independent(self):
        before = run_session(request(fixture()))
        run_session(request(fixture("conflicting-scores")))
        self.assertEqual(before, run_session(request(fixture())))


class BoundaryTests(unittest.TestCase):
    def rejects(self, data):
        with self.assertRaises(InvalidInput):
            request(data)

    def test_root_schema_and_budget_types(self):
        for data in (None, [], {}, {**fixture(), "extra": 1}, {**fixture(), "max_rounds": True},
                     {**fixture(), "max_rounds": 0}, {**fixture(), "max_rounds": 3},
                     {**fixture(), "max_rounds": 1.0}, {**fixture(), "problem_id": "other"},
                     {**fixture(), "review_rounds": []}):
            with self.subTest(data=data):
                self.rejects(data)

    def test_scores(self):
        for score in (True, False, "8", None, -1, 11, float("nan"), float("inf"), 1e-13):
            data = fixture("replay")
            data["review_rounds"][0]["critiques"][0]["score"] = score
            with self.subTest(score=score):
                self.rejects(data)

    def test_graph_references_identity_and_critique_fields(self):
        for key, value in (("id", "forged"), ("reviewer_id", "unknown"), ("reviewer_id", "pedagogy"),
                           ("criterion_id", "invented"), ("reason", ""), ("reason", "   "),
                           ("reason", "x" * 241), ("reason", True), ("unknown", 1)):
            data = fixture("replay")
            data["review_rounds"][0]["critiques"][0][key] = value
            with self.subTest(key=key):
                self.rejects(data)
        data = fixture("replay")
        data["review_rounds"][0]["critiques"][1] = copy.deepcopy(data["review_rounds"][0]["critiques"][0])
        self.rejects(data)

    def test_round_identity_count_and_schema(self):
        for change in (lambda d: d["review_rounds"][0].update(number=True),
                       lambda d: d["review_rounds"][0].update(number=2),
                       lambda d: d["review_rounds"][0].update(extra=0),
                       lambda d: d["review_rounds"][0].update(critiques={}),
                       lambda d: d["review_rounds"].append(d["review_rounds"][0])):
            data = fixture("replay")
            change(data)
            self.rejects(data)

    def test_all_replay_validated_before_adapter_execution(self):
        data = fixture("replay")
        data["review_rounds"][1]["critiques"][0]["id"] = "bad"
        with patch.object(core, "propose", side_effect=AssertionError("Must not start")):
            self.rejects(data)

    def test_valid_byte_limit_and_duplicate_keys_in_valid_documents(self):
        raw = json.dumps(fixture()).encode()
        padded = raw + b" " * (32768 - len(raw))
        self.assertEqual(run_session(load_request(padded)).status, "converged")
        with self.assertRaises(InvalidInput):
            load_request(padded + b" ")
        duplicate = raw.replace(b'"max_rounds": 2', b'"max_rounds": 2, "max_rounds": 2')
        with self.assertRaises(InvalidInput):
            load_request(duplicate)
        nested = json.dumps(fixture("replay")).encode().replace(b'"score": 8', b'"score": 8, "score": 8', 1)
        with self.assertRaises(InvalidInput):
            load_request(nested)

    def test_syntax_duplicates_unicode_and_resource_limits(self):
        examples = [b'{"problem_id":1,"problem_id":2}', b'{"a":{"x":1,"x":2}}', b'NaN', b'Infinity',
                    b'1e999999999', b'1e-999999999', b'12345678901234567890123456789012345',
                    b'{', b'\xff', b'"\\ud800"', b'x' * 32769, b'[' * 9 + b'0' + b']' * 9,
                    json.dumps(list(range(33))).encode(), json.dumps({"x" * 1025: 0}).encode(),
                    json.dumps({str(i): 0 for i in range(33)}).encode(),
                    json.dumps([[0] * 32 for _ in range(32)]).encode()]
        for raw in examples:
            with self.subTest(raw=raw[:30]), self.assertRaises(InvalidInput):
                load_request(raw)

    def test_depth_scanner_ignores_escaped_string_delimiters(self):
        data = fixture("replay")
        data["review_rounds"][0]["critiques"][0]["reason"] = '\\"[[[[[[[[[[{{{{{{{{{{'
        self.assertEqual(run_session(request(data)).status, "converged")


class ProcessTests(unittest.TestCase):
    def test_read_only_stdout_retains_documented_failure(self):
        for unbuffered in (False, True):
            for arguments in (['--help'], ['--bad']):
                descriptor = os.open(os.devnull, os.O_RDONLY)
                environment = {**os.environ, 'PYTHONUNBUFFERED': '1' if unbuffered else '0'}
                try:
                    result = self.invoke(arguments, raw=b'', env=environment, stdout=descriptor)
                finally:
                    os.close(descriptor)
                with self.subTest(unbuffered=unbuffered, arguments=arguments):
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertEqual(result.stderr, b'')

    def invoke(self, args=(), raw=None, env=None, stdout=subprocess.PIPE):
        return subprocess.run([sys.executable, "-m", "collective_intelligence", *args], input=raw,
                              stdout=stdout, stderr=subprocess.PIPE, env=env, timeout=10, cwd=CASE)

    def test_actual_cli_all_fixtures(self):
        for name, status in (("baseline", "converged"), ("replay", "converged"),
                             ("missing-reviewer", "unresolved"), ("conflicting-scores", "unresolved"),
                             ("threshold-tie", "unresolved")):
            with self.subTest(name=name):
                process = self.invoke(raw=json.dumps(fixture(name)).encode())
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(process.stderr, b"")
                self.assertEqual(json.loads(process.stdout)["status"], status)

    def test_errors_are_bounded_sanitized_without_input_echo(self):
        marker = "PRIVATE_MARKER_938"
        for args, raw in (((marker,), b''), (("--help", marker), b''), (("-h",), b''),
                          ((), marker.encode()), ((), b'x' * 32769), ((), b'\xff')):
            process = self.invoke(args, raw)
            self.assertEqual(process.returncode, 2)
            self.assertEqual(json.loads(process.stdout)["status"], "invalid-input")
            self.assertNotIn(marker.encode(), process.stdout + process.stderr)
            self.assertEqual(process.stderr, b"")
            self.assertLess(len(process.stdout), 128)

    def test_real_process_cancellation_while_reading_stdin(self):
        # The handshake occurs inside read(), so SIGINT reaches the CLI handler.
        script = (
            "import sys; from collective_intelligence.cli import main; "
            "original=sys.stdin.buffer; "
            "Proxy=type('Proxy',(),{'read':lambda self,n:(sys.stderr.write('ready\\n'),"
            "sys.stderr.flush(),original.read(n))[-1]}); "
            "sys.stdin=type('Input',(),{'buffer':Proxy()})(); sys.exit(main())"
        )
        process = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=CASE)
        self.assertEqual(process.stderr.readline(), b"ready\n")
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 130)
        self.assertEqual(json.loads(stdout)["status"], "cancelled")
        self.assertEqual(stderr, b"")

    def test_help_without_input(self):
        process = self.invoke(("--help",), b'')
        self.assertEqual(process.returncode, 0)
        self.assertIn(b"collective-intelligence", process.stdout)
        self.assertEqual(process.stderr, b"")

    def test_closed_stdout_buffered_unbuffered_help_results_errors(self):
        for unbuffered in (False, True):
            env = dict(os.environ, PYTHONUNBUFFERED="1" if unbuffered else "0")
            for args, raw in ((("--help",), b''), ((), json.dumps(fixture()).encode()), (("--bad",), b'')):
                with self.subTest(unbuffered=unbuffered, args=args):
                    reader, writer = os.pipe()
                    os.close(reader)
                    try:
                        process = self.invoke(args, raw, env=env, stdout=writer)
                    finally:
                        os.close(writer)
                    self.assertEqual(process.returncode, 0, process.stderr)
                    self.assertEqual(process.stderr, b"")
