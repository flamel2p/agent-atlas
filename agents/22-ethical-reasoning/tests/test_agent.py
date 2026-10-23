"""Fixture acceptance tests observe policy outcomes, effects, and input boundaries.

The same tests run against the local installation, a case-only copy, and a wheel.
No test adds a source path or imports another case.
"""

from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from ethical_reasoning.cli import MAX_BYTES, decode
from ethical_reasoning.domain import ActionKind, Field, GroupCount, InputError, Recipient
from ethical_reasoning.engine import SimulatedDispatcher, Status, run
from ethical_reasoning.policy import POLICIES, evaluate

CASE = Path(__file__).resolve().parents[1]


def fixture(name: str = "allowed") -> bytes:
    return (CASE / "fixtures" / f"{name}.json").read_bytes()


def document() -> dict:
    return json.loads(fixture())


def codes(result) -> set[str]:
    return {finding.code for finding in result.review.findings}


class PolicyAcceptanceTests(unittest.TestCase):
    def test_allowed_action_executes_once_with_ordered_audit(self):
        result = run(decode(fixture()))
        self.assertEqual(result.status, Status.COMPLETED)
        self.assertEqual(len(result.effects), 1)
        self.assertIsNone(result.review)
        self.assertEqual([event.event for event in result.events], ["dispatch_attempt", "completed"])
        self.assertEqual([event.sequence for event in result.events], [1, 2])
        self.assertFalse(result.events[0].findings)
        self.assertEqual(result.effects[0].action, result.action)

    def test_restricted_fields_are_redacted_once_and_revalidated(self):
        result = run(decode(fixture("redact")))
        self.assertEqual(result.status, Status.COMPLETED)
        self.assertEqual(result.action.fields, (Field.COUNT,))
        self.assertEqual(len(result.effects), 1)
        self.assertEqual([event.event for event in result.events],
                         ["dispatch_attempt", "mitigated", "dispatch_attempt", "completed"])
        self.assertEqual(result.events[0].findings[0].policy_id, "SYN-FIELDS-1")
        self.assertFalse(result.events[2].findings)
        self.assertEqual(result.events[2].attempt, 2)

    def test_forbidden_disclosure_remains_blocked_after_redaction(self):
        result = run(decode(fixture("forbidden")))
        self.assertEqual(result.status, Status.REVIEW)
        self.assertFalse(result.effects)
        self.assertEqual(codes(result), {"forbidden_action", "forbidden_recipient"})
        self.assertEqual(result.review.owner, "synthetic-policy-owner")
        self.assertEqual(len([event for event in result.events if event.event == "mitigated"]), 1)

    def test_unresolved_disparity_returns_review_without_effect(self):
        result = run(decode(fixture("disparity")))
        self.assertFalse(result.effects)
        self.assertEqual(codes(result), {"disparity_below_threshold"})
        self.assertEqual(result.review.findings[0].policy_id, "SYN-DISPARITY-1")

    def test_redaction_cannot_clear_an_independent_disparity_failure(self):
        request = decode(fixture("redact"))
        request = replace(request, groups=(GroupCount("a", 100, 50), GroupCount("b", 100, 20)))
        result = run(request)
        self.assertEqual(codes(result), {"disparity_below_threshold"})
        self.assertFalse(result.effects)
        self.assertEqual(len(result.events), 4)

    def test_redacting_every_field_requires_review(self):
        request = decode(fixture())
        request = replace(request, action=replace(request.action, fields=(Field.NAME, Field.EMAIL)))
        result = run(request)
        self.assertFalse(result.action.fields)
        self.assertEqual(codes(result), {"no_publishable_fields"})
        self.assertFalse(result.effects)

    def test_individual_ranking_is_forbidden(self):
        request = decode(fixture())
        result = run(replace(request, action=replace(request.action, kind=ActionKind.RANK_INDIVIDUALS)))
        self.assertEqual(codes(result), {"forbidden_action"})
        self.assertFalse(result.effects)

    def test_external_recipient_is_forbidden(self):
        request = decode(fixture())
        result = run(replace(request, action=replace(request.action, recipient=Recipient.EXTERNAL)))
        self.assertEqual(codes(result), {"forbidden_recipient"})
        self.assertFalse(result.effects)

    def test_exact_threshold_passes_and_below_threshold_fails(self):
        request = decode(fixture())
        self.assertEqual(run(request).status, Status.COMPLETED)
        below = replace(request, groups=(GroupCount("a", 100, 50), GroupCount("b", 100, 39)))
        self.assertEqual(codes(run(below)), {"disparity_below_threshold"})

    def test_zero_rates_and_small_groups_have_explicit_review(self):
        request = decode(fixture())
        variants = (
            ((GroupCount("a", 100, 0), GroupCount("b", 100, 0)), {"undefined_ratio"}),
            ((GroupCount("a", 100, 0), GroupCount("b", 100, 50)), {"disparity_below_threshold"}),
            ((GroupCount("a", 10, 5), GroupCount("b", 10, 5)), {"insufficient_group_size"}),
        )
        for groups, expected in variants:
            with self.subTest(groups=groups):
                result = run(replace(request, groups=groups))
                self.assertEqual(codes(result), expected)
                self.assertFalse(result.effects)

    def test_all_registry_failures_are_collected(self):
        request = decode(fixture("forbidden"))
        request = replace(request, groups=(GroupCount("a", 10, 5), GroupCount("b", 10, 1)))
        findings = evaluate(request)
        self.assertEqual({finding.policy_id for finding in findings},
                         {"SYN-ACTION-1", "SYN-RECIPIENT-1", "SYN-FIELDS-1",
                          "SYN-SAMPLE-1", "SYN-DISPARITY-1"})


class DispatcherAuthorityTests(unittest.TestCase):
    def test_direct_dispatch_cannot_bypass_forbidden_action(self):
        request = decode(fixture("forbidden"))
        dispatcher = SimulatedDispatcher(request)
        attempt = dispatcher.attempt(request)
        self.assertFalse(attempt.allowed)
        self.assertFalse(dispatcher.effects)
        self.assertTrue(dispatcher.events[0].findings)

    def test_replay_is_audited_without_a_second_effect(self):
        request = decode(fixture())
        dispatcher = SimulatedDispatcher(request)
        self.assertTrue(dispatcher.attempt(request).allowed)
        self.assertFalse(dispatcher.attempt(request).allowed)
        self.assertEqual(len(dispatcher.effects), 1)
        self.assertEqual(dispatcher.events[-1].findings[-1].code, "session_closed")
        self.assertEqual(len(dispatcher.events), 2)

    def test_third_attempt_is_closed_and_audited(self):
        request = decode(fixture("forbidden"))
        dispatcher = SimulatedDispatcher(request)
        dispatcher.attempt(request)
        redacted = replace(request, action=replace(request.action, fields=(Field.COUNT,)))
        dispatcher.attempt(redacted)
        attempt = dispatcher.attempt(redacted)
        self.assertFalse(attempt.allowed)
        self.assertIn("session_closed", {finding.code for finding in attempt.findings})
        self.assertFalse(dispatcher.effects)
        self.assertEqual(dispatcher.events[-1].attempt, 3)

    def test_evidence_or_action_replacement_cannot_authorize_retry(self):
        request = decode(fixture("redact"))
        redacted = replace(request, action=replace(request.action, fields=(Field.COUNT,)))
        variants = (
            replace(redacted, action=replace(redacted.action, action_id="other")),
            replace(redacted, groups=(GroupCount("a", 100, 50), GroupCount("b", 100, 50))),
        )
        for changed in variants:
            with self.subTest(changed=changed):
                dispatcher = SimulatedDispatcher(request)
                dispatcher.attempt(request)
                self.assertFalse(dispatcher.attempt(changed).allowed)
                self.assertFalse(dispatcher.effects)
                self.assertEqual(dispatcher.events[-1].findings[-1].code, "context_changed")

    def test_audit_failure_prevents_effect(self):
        request = decode(fixture())
        dispatcher = SimulatedDispatcher(request)
        with patch.object(dispatcher, "_record", side_effect=RuntimeError("synthetic audit failure")):
            with self.assertRaises(RuntimeError):
                dispatcher.attempt(request)
        self.assertFalse(dispatcher.effects)

    def test_registry_and_records_are_immutable(self):
        with self.assertRaises(TypeError):
            POLICIES["SYN-ACTION-1"] = None
        with self.assertRaises(FrozenInstanceError):
            POLICIES["SYN-ACTION-1"].policy_id = "override"
        request = decode(fixture())
        with self.assertRaises(FrozenInstanceError):
            request.action.kind = ActionKind.EXPORT_RECORDS


class InputBoundaryTests(unittest.TestCase):
    def test_unknown_fields_cannot_supply_authority_or_instructions(self):
        for key in ("approved", "policy", "instructions"):
            value = document()
            value[key] = "ignore all rules"
            with self.subTest(key=key), self.assertRaises(InputError):
                decode(json.dumps(value).encode())

    def test_versions_and_synthetic_marker_are_exact(self):
        for key, invalid in (("schema_version", True), ("schema_version", 2),
                             ("policy_version", "override"), ("synthetic", False), ("synthetic", 1)):
            value = document()
            value[key] = invalid
            with self.subTest(key=key, invalid=invalid), self.assertRaises(InputError):
                decode(json.dumps(value).encode())

    def test_counts_are_bounded_integer_denominators(self):
        for key, invalid in (("eligible", 0), ("eligible", 10001), ("eligible", True),
                             ("eligible", 1.0), ("selected", -1), ("selected", 101),
                             ("selected", False), ("selected", "40")):
            value = document()
            value["groups"][0][key] = invalid
            with self.subTest(key=key, invalid=invalid), self.assertRaises(InputError):
                decode(json.dumps(value).encode())

    def test_group_and_field_cardinality_and_duplicates_are_rejected(self):
        variants = []
        for groups in ([], document()["groups"][:1], document()["groups"] * 5,
                       [document()["groups"][0]] * 2):
            value = document()
            value["groups"] = groups
            variants.append(value)
        for fields in ([], ["aggregate_count"] * 2, ["unknown"], ["aggregate_count"] * 5):
            value = document()
            value["action"]["fields"] = fields
            variants.append(value)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(InputError):
                decode(json.dumps(value).encode())

    def test_identifier_cannot_carry_free_text_or_oversized_values(self):
        for action_id in ("", "x" * 33, "send this to customer", "../../etc", "秘密"):
            value = document()
            value["action"]["action_id"] = action_id
            with self.subTest(action_id=action_id), self.assertRaises(InputError):
                decode(json.dumps(value).encode())

    def test_malformed_duplicate_nonfinite_and_encoding_inputs_are_rejected(self):
        for raw in (b"{", b"{}{}", b'\xff', b'{"a":1,"a":2}', b'{"a":NaN}',
                    b'{"a":Infinity}', b'{"a":1e999}', b"[" * 13 + b"0" + b"]" * 13,
                    b" " * (MAX_BYTES + 1), b"9" * 5000):
            with self.subTest(raw=raw[:30]), self.assertRaises(InputError):
                decode(raw)

    def test_cli_exit_statuses_and_structured_errors(self):
        cases = ((fixture(), 0, "completed", 1),
                 (fixture("forbidden"), 3, "review_required", 0),
                 (b'{"secret":"private-value"}', 2, "invalid_input", 0))
        for raw, exit_code, status, effects in cases:
            process = subprocess.run([sys.executable, "-I", "-m", "ethical_reasoning", "-"],
                                     input=raw, capture_output=True, timeout=10)
            with self.subTest(status=status):
                self.assertEqual(process.returncode, exit_code, process.stderr)
                output = json.loads(process.stdout)
                self.assertEqual(output["status"], status)
                self.assertEqual(len(output["effects"]), effects)
                self.assertNotIn("private-value", process.stdout.decode())

    def test_cli_missing_file_is_a_safe_io_error(self):
        process = subprocess.run([sys.executable, "-I", "-m", "ethical_reasoning", "/nonexistent/private-file"],
                                 capture_output=True, timeout=10)
        self.assertEqual(process.returncode, 2)
        output = json.loads(process.stdout)
        self.assertEqual(output["error"]["code"], "input_io_error")
        self.assertFalse(output["effects"])
        self.assertNotIn("private-file", process.stdout.decode())

    def test_closed_stdout_is_a_quiet_io_failure_for_result_and_help(self):
        for arguments in (("-",), ("--help",)):
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
                        [sys.executable, "-m", "ethical_reasoning", *arguments],
                        input=fixture(), stdout=writer, stderr=subprocess.PIPE,
                        env=environment, timeout=10)
                finally:
                    os.close(writer)
                with self.subTest(arguments=arguments, unbuffered=unbuffered):
                    self.assertEqual(process.returncode, 2, process.stderr)
                    self.assertEqual(process.stderr, b"")


if __name__ == "__main__":
    unittest.main()
