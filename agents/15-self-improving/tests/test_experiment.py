"""Behavior checks use explicit FAQ choices and independent JSON hash formulas."""

import copy
from dataclasses import FrozenInstanceError, asdict
import hashlib
from importlib.resources import files
import json
import unittest

from self_improving import ScenarioName, load_scenario, run_experiment
from self_improving.experiment import (
    DevelopmentRejectedReport, EvaluatedReport, NoCandidateReport,
)
from self_improving.scenarios import _decode_bundle


def bundle(name=ScenarioName.IMPROVEMENT):
    root = files("self_improving").joinpath("fixtures", name.value)
    return [json.loads(root.joinpath(filename).read_text()) for filename in
            ("selection.json", "curators.json", "holdout.json")]


def decode(parts):
    return _decode_bundle("mutation", *(json.dumps(part).encode() for part in parts))


def json_hash(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(data.encode()).hexdigest()


class ExperimentTests(unittest.TestCase):
    def test_improvement_is_one_topic_scoped_review_record(self):
        report = run_experiment(load_scenario(ScenarioName.IMPROVEMENT))
        self.assertIsInstance(report, EvaluatedReport)
        data = report.to_dict()
        self.assertEqual(data["status"], "review_required")
        self.assertEqual((data["heldout"]["baseline_correct"], data["heldout"]["candidate_correct"]), (4, 7))
        self.assertEqual(data["proposal"]["supporting_feedback_ids"], ["feedback-request", "feedback-window"])
        self.assertEqual(data["baseline"]["config"], {"recency_topic": None})
        self.assertEqual(data["proposal"]["candidate"]["config"], {"recency_topic": "refunds"})
        self.assertEqual(data["serving_version_id"], data["baseline"]["version_id"])
        self.assertEqual(data["proposal"]["candidate"]["parent_version_id"], data["baseline"]["version_id"])
        cases = {case["query"]["query_id"]: case for case in data["heldout"]["cases"]}
        for qid in ("recent-deadline", "recent-policy", "recent-status"):
            self.assertEqual(cases[qid]["baseline"]["selected_document_id"], "a-policy-old")
            self.assertEqual(cases[qid]["candidate"]["selected_document_id"], "z-policy-current")
        for qid, expected in (("stable-access", "a-access"), ("stable-billing", "a-billing"),
                              ("stable-specialist", "z-specialist"), ("stable-no-match", None)):
            self.assertEqual(cases[qid]["baseline"]["selected_document_id"], expected)
            self.assertEqual(cases[qid]["candidate"]["selected_document_id"], expected)
        self.assertEqual(data["heldout"]["lost_query_ids"], [])

    def test_aggregate_gain_cannot_hide_a_protected_regression(self):
        report = run_experiment(load_scenario(ScenarioName.REGRESSION)).to_dict()
        self.assertEqual(report["status"], "rejected_regression")
        self.assertEqual((report["heldout"]["baseline_correct"], report["heldout"]["candidate_correct"]), (5, 7))
        self.assertEqual(report["heldout"]["lost_query_ids"], ["stable-legacy-window"])
        lost = next(case for case in report["heldout"]["cases"] if case["query"]["query_id"] == "stable-legacy-window")
        self.assertEqual(lost["baseline"]["selected_document_id"], "a-policy-old")
        self.assertEqual(lost["candidate"]["selected_document_id"], "z-policy-current")
        self.assertEqual(report["serving_version_id"], report["baseline"]["version_id"])

    def test_insufficient_and_poisoned_have_no_fabricated_metrics(self):
        for name in (ScenarioName.INSUFFICIENT, ScenarioName.POISONED):
            with self.subTest(scenario=name):
                result = run_experiment(load_scenario(name))
                self.assertIsInstance(result, NoCandidateReport)
                data = result.to_dict()
                self.assertEqual(data["status"], "no_proposal_insufficient")
                for absent in ("proposal", "development", "heldout"):
                    self.assertNotIn(absent, data)
        poison = run_experiment(load_scenario(ScenarioName.POISONED)).to_dict()
        reasons = {item["reason"] for item in poison["feedback"]}
        self.assertEqual(reasons, {"conflicted_trace", "cross_topic", "curator_mismatch", "irrelevant_target",
                                  "not_newer", "replay_mismatch", "unknown_curator", "unknown_target",
                                  "unknown_trace", "wrong_baseline"})
        self.assertTrue(all(item["disposition"] == "excluded" for item in poison["feedback"]))

    def test_development_loss_stops_before_heldout_evaluation(self):
        report = run_experiment(load_scenario(ScenarioName.DEVELOPMENT_REJECTION))
        self.assertIsInstance(report, DevelopmentRejectedReport)
        self.assertEqual(report.to_dict()["status"], "rejected_development")
        self.assertEqual(report.development.lost_query_ids, ("dev-legacy-window",))
        self.assertNotIn("heldout", report.to_dict())

    def test_no_gain_requires_both_strict_gains(self):
        report = run_experiment(load_scenario(ScenarioName.NO_GAIN)).to_dict()
        self.assertEqual(report["status"], "rejected_no_gain")
        self.assertEqual(report["gate_reasons"], ["no_strict_recent_group_gain", "no_strict_total_gain"])
        self.assertEqual((report["heldout"]["baseline_correct"], report["heldout"]["candidate_correct"]), (2, 2))

    def test_every_terminal_branch_preserves_frozen_input_and_repeats_exactly(self):
        for name in ScenarioName:
            with self.subTest(scenario=name):
                scenario = load_scenario(name)
                snapshot = asdict(scenario)
                first = run_experiment(scenario)
                second = run_experiment(scenario)
                self.assertEqual(first.to_json(), second.to_json())
                self.assertEqual(asdict(scenario), snapshot)
                self.assertEqual(first.serving_version_id, scenario.selection.baseline.version_id)
                with self.assertRaises(FrozenInstanceError):
                    scenario.selection.baseline.config.recency_topic = "access"
                detached = first.to_dict()
                detached["baseline"]["config"]["recency_topic"] = "access"
                self.assertIsNone(first.baseline.config.recency_topic)

    def test_report_corpus_and_version_hashes_are_independently_recomputable(self):
        scenario = load_scenario(ScenarioName.IMPROVEMENT)
        data = run_experiment(scenario).to_dict()
        report_digest = data.pop("report_digest")
        self.assertEqual(report_digest, json_hash(data))
        corpus_json = json.loads(json.dumps([asdict(doc) for doc in scenario.selection.corpus]))
        self.assertEqual(data["corpus_digest"], json_hash(corpus_json))
        for version in (data["baseline"], data["proposal"]["candidate"]):
            version = dict(version)
            version_id = version.pop("version_id")
            self.assertEqual(version_id, json_hash(version))
            self.assertEqual(version["corpus_digest"], data["corpus_digest"])
            self.assertEqual(version["algorithm_version"], data["algorithm_version"])
        self.assertEqual(data["proposal"]["candidate"]["evidence_digest"], data["proposal"]["evidence_digest"])
        self.assertEqual(data["proposal"]["evidence_digest"], json_hash(data["proposal"]["supporting_evidence"]))

    def test_heldout_label_changes_cannot_change_candidate_or_support(self):
        original = bundle()
        first = run_experiment(decode(original)).to_dict()
        altered = copy.deepcopy(original)
        for case in altered[2]["cases"]:
            if case["group"] == "recent":
                case["expected_document_id"] = "a-policy-old"
        second = run_experiment(decode(altered)).to_dict()
        self.assertEqual(first["proposal"], second["proposal"])
        self.assertEqual(first["selection_digest"], second["selection_digest"])
        self.assertNotEqual(first["holdout_digest"], second["holdout_digest"])
        self.assertNotEqual(first["report_digest"], second["report_digest"])
        self.assertEqual(first["status"], "review_required")
        self.assertEqual(second["status"], "rejected_regression")

    def test_corpus_and_support_changes_have_distinct_lineage(self):
        original = bundle()
        baseline = run_experiment(decode(original)).to_dict()
        changed_corpus = copy.deepcopy(original)
        changed_corpus[0]["corpus"][0]["answer"] += " Curator wording update."
        new_baseline_id = decode(changed_corpus).selection.baseline.version_id
        for trace in changed_corpus[0]["traces"]:
            trace["baseline_version_id"] = new_baseline_id
        corpus_report = run_experiment(decode(changed_corpus)).to_dict()
        self.assertEqual(corpus_report["status"], "review_required")
        self.assertNotEqual(baseline["corpus_digest"], corpus_report["corpus_digest"])
        self.assertNotEqual(baseline["baseline"]["version_id"], corpus_report["baseline"]["version_id"])
        self.assertNotEqual(baseline["proposal"]["candidate"]["version_id"], corpus_report["proposal"]["candidate"]["version_id"])
        changed_support = copy.deepcopy(original)
        changed_support[0]["feedback"][0]["feedback_id"] = "renamed-support-record"
        support_report = run_experiment(decode(changed_support)).to_dict()
        self.assertEqual(support_report["baseline"], baseline["baseline"])
        self.assertNotEqual(support_report["proposal"]["evidence_digest"], baseline["proposal"]["evidence_digest"])
        self.assertNotEqual(support_report["proposal"]["candidate"]["version_id"], baseline["proposal"]["candidate"]["version_id"])

    def test_copied_feedback_and_query_signatures_cannot_multiply_support(self):
        duplicate_trace = bundle(ScenarioName.INSUFFICIENT)
        copied = dict(duplicate_trace[0]["feedback"][0], feedback_id="copy-feedback")
        duplicate_trace[0]["feedback"].append(copied)
        duplicate_query = bundle()
        duplicate_query[0]["traces"][1]["query"]["tokens"] = list(reversed(duplicate_query[0]["traces"][0]["query"]["tokens"]))
        for parts, expected in ((duplicate_trace, "duplicate_trace"), (duplicate_query, "duplicate_query_signature")):
            with self.subTest(reason=expected):
                data = run_experiment(decode(parts)).to_dict()
                self.assertEqual(data["status"], "no_proposal_insufficient")
                self.assertIn(expected, [item["reason"] for item in data["feedback"]])

    def test_a_conflict_excludes_the_whole_trace(self):
        parts = bundle()
        parts[0]["feedback"].append(dict(parts[0]["feedback"][0], feedback_id="contradiction", target_document_id="z-specialist"))
        data = run_experiment(decode(parts)).to_dict()
        self.assertEqual(data["status"], "no_proposal_insufficient")
        conflicted = [item for item in data["feedback"] if item["trace_id"] == "trace-window"]
        self.assertEqual(len(conflicted), 2)
        self.assertTrue(all(item["reason"] == "conflicted_trace" for item in conflicted))

    def test_multiple_supported_topics_are_explicitly_ambiguous(self):
        parts = bundle()
        baseline_id = parts[0]["traces"][0]["baseline_version_id"]
        for token in ("password", "reset"):
            tid = "trace-" + token
            rid = "curator-" + token
            parts[0]["traces"].append(dict(trace_id=tid,
                query=dict(query_id="feedback-" + token, topic="access", tokens=[token]),
                baseline_version_id=baseline_id, observed_document_id="a-access"))
            parts[0]["feedback"].append(dict(feedback_id="feedback-" + token, trace_id=tid,
                target_document_id="z-access-new", curator_record_id=rid))
            parts[1]["records"].append(dict(record_id=rid, trace_id=tid, target_document_id="z-access-new"))
        report = run_experiment(decode(parts)).to_dict()
        self.assertEqual(report["status"], "no_proposal_ambiguous")
        self.assertEqual(report["qualifying_topics"], ["access", "refunds"])
        self.assertNotIn("proposal", report)

    def test_newer_lower_overlap_and_cross_topic_entries_do_not_win(self):
        parts = bundle()
        parts[2]["cases"].extend([
            dict(query=dict(query_id="recent-overlap-priority", topic="refunds", tokens=["refund", "policy", "deadline", "specialist"]),
                 expected_document_id="z-policy-current", group="recent"),
            dict(query=dict(query_id="stable-topic-boundary", topic="access", tokens=["refund", "account"]),
                 expected_document_id="a-access", group="stable"),
        ])
        report = run_experiment(decode(parts)).to_dict()
        cases = {case["query"]["query_id"]: case for case in report["heldout"]["cases"]}
        overlap = cases["recent-overlap-priority"]["candidate"]
        self.assertEqual(overlap["selected_document_id"], "z-policy-current")
        self.assertEqual(overlap["ranking"][0]["overlap"], 3)
        self.assertEqual(next(item["overlap"] for item in overlap["ranking"] if item["document_id"] == "z-specialist"), 2)
        self.assertNotIn("z-unused", [item["document_id"] for item in overlap["ranking"]])
        topic = cases["stable-topic-boundary"]["candidate"]
        self.assertEqual(topic["selected_document_id"], "a-access")
        self.assertEqual({item["document_id"] for item in topic["ranking"]}, {"a-access", "z-access-new"})

    def test_candidate_must_fix_every_selected_correction(self):
        parts = bundle()
        for feedback in parts[0]["feedback"]:
            feedback["target_document_id"] = "z-specialist"
        for record in parts[1]["records"]:
            record["target_document_id"] = "z-specialist"
        data = run_experiment(decode(parts)).to_dict()
        self.assertEqual(data["status"], "rejected_development")
        self.assertEqual(data["gate_reasons"], ["candidate_does_not_fix_all_supporting_corrections"])
        self.assertNotIn("heldout", data)

    def test_already_correct_feedback_does_not_count_as_a_failure(self):
        parts = bundle()
        parts[0]["feedback"][0]["target_document_id"] = "a-policy-old"
        parts[1]["records"][0]["target_document_id"] = "a-policy-old"
        data = run_experiment(decode(parts)).to_dict()
        self.assertEqual(data["status"], "no_proposal_insufficient")
        self.assertIn("not_baseline_failure", [item["reason"] for item in data["feedback"]])


if __name__ == "__main__":
    unittest.main()
