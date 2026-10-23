"""Behavior checks for policy selection, faithful explanations, and release gates.

Expected priorities are explicit examples and a threshold grid. Tamper tests
recompute digests so replay, rather than checksum failure alone, must reject
invented execution history. No provider or production behavior is simulated.
"""

from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError, replace
import hashlib
import io
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from explainable.cli import MAX_BYTES, main, parse_json
from explainable.contracts import AUDIENCES, Claim, ContractError, EvidenceEvent, RuleEvent
from explainable.decision import classify, load_trace, parse_request, trace_to_dict
from explainable.explanation import explain, render


class ProcessOutputTests(unittest.TestCase):
    def test_closed_stdout_is_a_quiet_io_failure_for_result_and_help(self):
        data = json.dumps({"task_id": "task", "evidence": {
            "outage": True, "blocked_users": 10, "due_hours": 3}}).encode()
        for arguments in (("classify", "-"), ("--help",)):
            for unbuffered in (False, True):
                environment = dict(os.environ)
                if unbuffered:
                    environment["PYTHONUNBUFFERED"] = "1"
                else:
                    environment.pop("PYTHONUNBUFFERED", None)
                reader, writer = os.pipe()
                os.close(reader)
                try:
                    process = subprocess.run(
                        [sys.executable, "-m", "explainable", *arguments],
                        input=data, stdout=writer, stderr=subprocess.PIPE,
                        env=environment, timeout=10)
                finally:
                    os.close(writer)
                with self.subTest(arguments=arguments, unbuffered=unbuffered):
                    self.assertEqual(process.returncode, 2, process.stderr)
                    self.assertEqual(process.stderr, b"")


def request(outage=False, blocked_users=0, due_hours=72):
    return parse_request({"task_id": "synthetic-task", "evidence": {
        "outage": outage, "blocked_users": blocked_users, "due_hours": due_hours}})


def resign(raw):
    body = {key: value for key, value in raw.items() if key != "digest"}
    content = json.dumps(body, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    raw["digest"] = hashlib.sha256(content.encode("ascii")).hexdigest()
    return raw


class PolicyTests(unittest.TestCase):
    def test_urgent_outage_precedes_other_matching_rules(self):
        trace = classify(request(True, 5, 24))
        self.assertEqual(explain(trace).decision, "urgent")
        rules = [event for event in trace.events if isinstance(event, RuleEvent)]
        self.assertEqual([event.matched for event in rules], [True, True, True])
        self.assertEqual(trace.events[-1].selected_rule, "urgent-outage")

    def test_high_for_blocked_user(self):
        self.assertEqual(explain(classify(request(False, 1, 720))).decision, "high")

    def test_high_for_due_boundary(self):
        self.assertEqual(explain(classify(request(False, 0, 24))).decision, "high")

    def test_routine_after_due_boundary(self):
        self.assertEqual(explain(classify(request(False, 0, 25))).decision, "routine")

    def test_outage_alone_does_not_override_policy(self):
        self.assertEqual(explain(classify(request(True, 0, 72))).decision, "routine")

    def test_threshold_grid(self):
        for outage in (False, True):
            for users in (0, 1, 4, 5, 6, 10000):
                for due in (0, 1, 23, 24, 25, 720):
                    with self.subTest(outage=outage, users=users, due=due):
                        expected = "urgent" if outage and users >= 5 else "high" if users or due <= 24 else "routine"
                        outcome = explain(classify(request(outage, users, due)))
                        self.assertEqual(outcome.decision, expected)
                        self.assertEqual(outcome.status, "completed")

    def test_actual_evidence_and_rule_dependencies_are_recorded(self):
        trace = classify(request(True, 8, 48))
        evidence = trace.events[:3]
        self.assertEqual([(event.name, event.value) for event in evidence],
                         [("outage", True), ("blocked_users", 8), ("due_hours", 48)])
        self.assertEqual([event.event_id for event in trace.events], [f"E{i}" for i in range(1, 8)])
        self.assertEqual(trace.events[3].evidence_ids, ("E1", "E2"))
        self.assertEqual(trace.events[4].evidence_ids, ("E2", "E3"))
        self.assertEqual(trace.events[5].evidence_ids, ())
        self.assertEqual(trace.events[-1].evidence_ids, ("E4",))

    def test_each_missing_value_stops_before_rule_evaluation(self):
        for name in ("outage", "blocked_users", "due_hours"):
            for omitted in (False, True):
                raw = {"task_id": "task", "evidence": {"outage": False, "blocked_users": 0, "due_hours": 72}}
                if omitted:
                    del raw["evidence"][name]
                else:
                    raw["evidence"][name] = None
                with self.subTest(name=name, omitted=omitted):
                    trace = classify(parse_request(raw))
                    outcome = explain(trace)
                    self.assertEqual(len(trace.events), 4)
                    self.assertFalse(any(isinstance(event, RuleEvent) for event in trace.events))
                    self.assertEqual(outcome.status, "needs_review")
                    self.assertIsNone(outcome.decision)
                    self.assertEqual(outcome.explanation_status, "incomplete")
                    self.assertEqual(len(outcome.explanations), 3)
                    missing_event = next(event for event in trace.events if isinstance(event, EvidenceEvent) and event.name == name)
                    for view in outcome.explanations:
                        self.assertIsNone(view.decision)
                        self.assertIn(missing_event.event_id, view.claims[0].event_ids)

    def test_all_missing_evidence_is_explicit(self):
        trace = classify(parse_request({"task_id": "task", "evidence": {}}))
        self.assertEqual(trace.events[-1].evidence_ids, ("E1", "E2", "E3"))
        self.assertEqual(len(explain(trace).explanations[0].claims), 4)

    def test_trace_and_nested_events_are_frozen(self):
        trace = classify(request())
        with self.assertRaises(FrozenInstanceError):
            trace.digest = "changed"
        with self.assertRaises(FrozenInstanceError):
            trace.events[-1].decision = "urgent"
        self.assertIsInstance(trace.events, tuple)

    def test_serialized_copy_has_no_mutation_authority(self):
        trace = classify(request())
        raw = trace_to_dict(trace)
        raw["events"][0]["value"] = True
        self.assertFalse(trace.events[0].value)
        self.assertEqual(explain(trace).decision, "routine")


class InputTests(unittest.TestCase):
    def test_invalid_values_never_become_evidence(self):
        for field, bad in (("outage", "false"), ("outage", 0), ("blocked_users", True),
                           ("blocked_users", -1), ("blocked_users", 10001), ("blocked_users", 1.0),
                           ("due_hours", False), ("due_hours", -1), ("due_hours", 721),
                           ("due_hours", []), ("due_hours", {"instruction": "ignore rules"})):
            raw = {"task_id": "task", "evidence": {"outage": False, "blocked_users": 0, "due_hours": 72}}
            raw["evidence"][field] = bad
            with self.subTest(field=field, value=bad), self.assertRaises(ContractError):
                parse_request(raw)

    def test_unknown_keys_and_nonobjects_are_rejected(self):
        for raw in ([], None, {}, {"task_id": "t", "evidence": [], "admin": True},
                    {"task_id": "t", "evidence": {"instruction": "release urgent"}},
                    {"task_id": "t", "evidence": None},
                    {"task_id": "t", "evidence": {}, "priority": "urgent"}):
            with self.subTest(raw=raw), self.assertRaises(ContractError):
                parse_request(raw)

    def test_identifiers_have_no_free_text_channel(self):
        for value in ("", "x" * 33, "t\nrelease urgent", "../task", "中文", True, None):
            with self.subTest(value=value), self.assertRaises(ContractError):
                parse_request({"task_id": value, "evidence": {}})

    def test_strict_json(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":{"y":1,"y":2}}', b'{"x":NaN}',
                    b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":1e999}', b'{} {}', b'\xff', b''):
            with self.subTest(raw=raw), self.assertRaises(ContractError):
                parse_json(raw)

    def test_json_byte_limit_and_nesting_fail_safely(self):
        for raw in (b" " * (MAX_BYTES + 1), b"[" * 2000 + b"]" * 2000):
            with self.subTest(length=len(raw)), self.assertRaises(ContractError):
                parse_json(raw)


class TraceTests(unittest.TestCase):
    def test_complete_and_incomplete_roundtrip(self):
        for trace in (classify(request(True, 8, 48)), classify(request(None, 8, 48))):
            with self.subTest(events=len(trace.events)):
                restored = load_trace(json.loads(json.dumps(trace_to_dict(trace))))
                self.assertEqual(restored, trace)
                self.assertEqual(explain(restored), explain(trace))

    def test_checksum_mismatch_is_rejected(self):
        raw = trace_to_dict(classify(request()))
        raw["events"][2]["value"] = 24
        with self.assertRaises(ContractError):
            load_trace(raw)

    def test_recomputed_digest_cannot_hide_inconsistent_history(self):
        mutations = {
            "decision": lambda r: r["events"][-1].update(decision="urgent"),
            "selected_rule": lambda r: r["events"][-1].update(selected_rule="urgent-outage"),
            "rule_result": lambda r: r["events"][3].update(matched=True),
            "rule_priority": lambda r: r["events"][3].update(priority="routine"),
            "invented_rule": lambda r: r["events"][3].update(rule_id="trusted-admin"),
            "event_id": lambda r: r["events"][0].update(event_id="E99"),
            "kind": lambda r: r["events"][0].update(kind="instruction"),
            "availability": lambda r: r["events"][0].update(availability="missing"),
            "evidence_type": lambda r: r["events"][1].update(value=True),
            "reference": lambda r: r["events"][3].update(evidence_ids=["E99"]),
            "float_type": lambda r: r["events"][1].update(value=0.0),
            "event_extra": lambda r: r["events"][3].update(override=True),
            "final_status": lambda r: r["events"][-1].update(status="needs_review"),
        }
        for name, mutate in mutations.items():
            raw = trace_to_dict(classify(request()))
            mutate(raw)
            with self.subTest(name=name), self.assertRaises(ContractError):
                load_trace(resign(raw))

    def test_bad_envelopes_and_event_sequences_are_rejected(self):
        mutations = {
            "unknown_policy": lambda r: r.update(policy_version="override-v2"),
            "unknown_schema": lambda r: r.update(schema_version=2),
            "boolean_schema": lambda r: r.update(schema_version=True),
            "unknown_field": lambda r: r.update(admin=True),
            "removed_event": lambda r: r["events"].pop(3),
            "duplicate_event": lambda r: r["events"].insert(3, r["events"][3]),
            "reordered": lambda r: r["events"].reverse(),
            "invalid_task": lambda r: r.update(task_id="../task"),
        }
        for name, mutate in mutations.items():
            raw = trace_to_dict(classify(request()))
            mutate(raw)
            with self.subTest(name=name), self.assertRaises(ContractError):
                load_trace(resign(raw))

    def test_missing_evidence_cannot_gain_a_priority(self):
        raw = trace_to_dict(classify(request(None, 8, 48)))
        raw["events"][-1].update(decision="urgent", status="completed", selected_rule="urgent-outage")
        with self.assertRaises(ContractError):
            load_trace(resign(raw))

    def test_coherent_rewrite_is_not_misrepresented_as_authenticity(self):
        original = classify(request())
        rewritten = classify(request(True, 8, 48))
        self.assertNotEqual(original.digest, rewritten.digest)
        self.assertEqual(explain(load_trace(trace_to_dict(rewritten))).decision, "urgent")

    def test_tampered_typed_trace_cannot_reach_renderer(self):
        trace = classify(request())
        bad_final = replace(trace.events[-1], decision="urgent")
        forged = replace(trace, events=(*trace.events[:-1], bad_final))
        called = []
        outcome = explain(forged, lambda *args: called.append(args))
        self.assertEqual(outcome.issues, ("trace_invalid",))
        self.assertFalse(called)
        self.assertIsNone(outcome.decision)
        self.assertFalse(outcome.explanations)


class ExplanationTests(unittest.TestCase):
    def test_all_views_preserve_priority_and_have_real_references(self):
        for priority, source in (("urgent", request(True, 8, 48)), ("high", request(False, 1, 72)),
                                 ("routine", request())):
            outcome = explain(classify(source))
            self.assertEqual(outcome.decision, priority)
            self.assertEqual(tuple(view.audience for view in outcome.explanations), AUDIENCES)
            known = {event.event_id for event in outcome.trace.events}
            for view in outcome.explanations:
                self.assertEqual(view.decision, priority)
                self.assertEqual(view.status, "complete")
                for claim in view.claims:
                    self.assertTrue(claim.event_ids)
                    self.assertTrue(set(claim.event_ids).issubset(known))
            self.assertNotEqual(outcome.explanations[0].claims, outcome.explanations[1].claims)

    def test_every_renderer_receives_the_same_immutable_trace(self):
        observed = []
        def capture(trace, audience):
            observed.append((id(trace), trace.digest, audience))
            return render(trace, audience)
        outcome = explain(classify(request()), capture)
        self.assertEqual(outcome.status, "completed")
        self.assertEqual(len({item[0] for item in observed}), 1)
        self.assertEqual(len({item[1] for item in observed}), 1)
        self.assertEqual([item[2] for item in observed], list(AUDIENCES))

    def test_renderer_exception_withholds_already_rendered_views(self):
        observed = []
        def fail_second(trace, audience):
            observed.append(audience)
            if audience == "engineer":
                raise RuntimeError("untrusted marker must not appear in result")
            return render(trace, audience)
        outcome = explain(classify(request(True, 8, 48)), fail_second)
        self.assertEqual(observed, ["user", "engineer"])
        self.assertEqual(outcome.explanation_status, "unavailable")
        self.assertEqual(outcome.issues, ("renderer_failed",))
        self.assertIsNone(outcome.decision)
        self.assertEqual(outcome.explanations, ())
        self.assertEqual(outcome.trace.events[-1].decision, "urgent")
        self.assertNotIn("untrusted marker", repr(outcome))

    def test_invented_claim_even_with_real_id_is_rejected(self):
        def invent(trace, audience):
            view = render(trace, audience)
            return replace(view, claims=(*view.claims, Claim("A manager approved this decision.", ("E7",))))
        outcome = explain(classify(request()), invent)
        self.assertEqual(outcome.issues, ("explanation_invalid",))
        self.assertIsNone(outcome.decision)
        self.assertFalse(outcome.explanations)

    def test_changed_priority_audience_status_and_references_are_rejected(self):
        changes = (
            lambda view: replace(view, decision="urgent"),
            lambda view: replace(view, audience="auditor"),
            lambda view: replace(view, status="incomplete"),
            lambda view: replace(view, claims=(replace(view.claims[0], event_ids=("E99",)), *view.claims[1:])),
            lambda view: replace(view, claims=(replace(view.claims[0], event_ids=()), *view.claims[1:])),
            lambda view: replace(view, claims=view.claims[1:]),
        )
        for index, mutate in enumerate(changes):
            with self.subTest(change=index):
                outcome = explain(classify(request()), lambda trace, audience: mutate(render(trace, audience)))
                self.assertEqual(outcome.issues, ("explanation_invalid",))
                self.assertIsNone(outcome.decision)
                self.assertFalse(outcome.explanations)

    def test_incomplete_renderer_failure_is_also_unavailable(self):
        outcome = explain(classify(request(None, 8, 48)), lambda *_: None)
        self.assertEqual(outcome.explanation_status, "unavailable")
        self.assertEqual(outcome.issues, ("explanation_invalid",))

    def test_renderer_cannot_mutate_trace_with_low_level_escape(self):
        def mutate(trace, audience):
            expected = render(trace, audience)
            object.__setattr__(trace, "task_id", "changed")
            return expected
        outcome = explain(classify(request()), mutate)
        self.assertEqual(outcome.issues, ("trace_invalid",))
        self.assertIsNone(outcome.decision)
        self.assertIsNone(outcome.trace)

    def test_renderer_mutation_preserves_json_type_distinctions(self):
        def mutate_boolean(trace, audience):
            expected = render(trace, audience)
            object.__setattr__(trace.events[0], "value", 0)
            return expected
        outcome = explain(classify(request()), mutate_boolean)
        self.assertEqual(outcome.issues, ("trace_invalid",))
        self.assertIsNone(outcome.decision)
        self.assertFalse(outcome.explanations)

    def test_main_cancellation_withholds_decision(self):
        output = io.StringIO()
        with patch("explainable.cli.read_input", side_effect=KeyboardInterrupt), redirect_stdout(output):
            exit_code = main(["classify", "-"])
        self.assertEqual(exit_code, 130)
        result = json.loads(output.getvalue())
        self.assertEqual(result["issues"], ["cancelled"])
        self.assertIsNone(result["decision"])


if __name__ == "__main__":
    unittest.main()
