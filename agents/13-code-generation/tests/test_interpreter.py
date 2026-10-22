"""Behavioral checks for shipping semantics, the whole-tree policy and bounds."""

from dataclasses import FrozenInstanceError
import unittest
from unittest.mock import patch

from code_generation_agent.domain import ORACLE
from code_generation_agent.interpreter import Rejected, check_candidate, interpret
from support import fixture, function


class InterpreterTests(unittest.TestCase):
    def test_literal_oracle_and_hand_calculated_boundaries(self):
        expected = {
            0: (8, 8, 3, 3), 1: (8, 8, 3, 3), 2: (8, 8, 3, 3),
            3: (11, 11, 6, 6), 20: (62, 62, 57, 57),
        }
        self.assertEqual(len(ORACLE), 20)
        self.assertEqual(len({case.test_id for case in ORACLE}), 20)
        for weight, fees in expected.items():
            for subtotal, fee in zip((0, 100, 101, 1000), fees, strict=True):
                with self.subTest(weight=weight, subtotal=subtotal):
                    oracle = next(case for case in ORACLE if (case.weight_kg, case.subtotal_rm) == (weight, subtotal))
                    self.assertEqual(oracle.expected, fee)
                    self.assertEqual(interpret(fixture(), weight, subtotal), fee)
        with self.assertRaises(FrozenInstanceError):
            ORACLE[0].expected = 999

    def test_complete_oracle_reports_threshold_failure(self):
        feedback = check_candidate(fixture("threshold_bug.txt"))
        self.assertEqual(len(feedback.tests), 20)
        self.assertEqual(
            {result.test_id for result in feedback.tests if not result.passed},
            {"w0-s100", "w1-s100", "w2-s100", "w3-s100", "w20-s100"},
        )
        self.assertTrue(check_candidate(fixture()).passed)

    def test_arithmetic_else_assignment_and_return_zero(self):
        source = function("fee = 9\nif weight_kg == 0:\n    return 0\nelse:\n    fee = fee * 2 - 10\nreturn fee")
        self.assertEqual(interpret(source, 0, 0), 0)
        self.assertEqual(interpret(source, 1, 0), 8)
        expected = {"==": (1, 0), "!=": (0, 1), "<": (0, 0), "<=": (1, 0), ">": (0, 1), ">=": (1, 1)}
        for comparison, outcomes in expected.items():
            with self.subTest(comparison=comparison):
                source = function(f"if weight_kg {comparison} 2:\n    return 1\nreturn 0")
                self.assertEqual(tuple(interpret(source, weight, 0) for weight in (2, 3)), outcomes)

    def test_forbidden_syntax_is_rejected_even_after_return(self):
        bodies = (
            "return 8\nimport os", "return 8\nopen('x')", "return 8\nwhile 1:\n    return 8",
            "return 8\nfor x in weight_kg:\n    return 8", "return weight_kg.real",
            "return weight_kg[0]", "return [8]", "return {'fee': 8}", "return (8,)",
            "assert weight_kg == 1\nreturn 8", "return abs(weight_kg)", "return 2 ** 2",
            "return 8 / 1", "return 8 // 1", "return 8 % 1", "return -1", "return +8",
            "return 8 if weight_kg else 3", "return lambda: 8", "global fee\nreturn 8",
            "raise ValueError()", "try:\n    return 8\nexcept:\n    return 3",
            "return (x := 8)", "yield 8", "fee += 8\nreturn fee", "a = b = 8\nreturn a",
            "a, b = 8\nreturn a", "fee: int = 8\nreturn fee",
            "__debug__ = 8\nreturn __debug__",
            "def inner():\n    return 8\nreturn 8", "match weight_kg:\n    case 0:\n        return 8",
        )
        for body in bodies:
            with self.subTest(body=body):
                feedback = check_candidate(function(body))
                self.assertEqual(feedback.kind, "policy")
                self.assertEqual(feedback.tests, ())

    def test_signatures_and_top_level_are_exact(self):
        sources = (
            "def wrong(weight_kg, subtotal_rm):\n    return 8",
            "def shipping_fee(weight_kg):\n    return 8",
            "def shipping_fee(subtotal_rm, weight_kg):\n    return 8",
            "def shipping_fee(weight_kg, subtotal_rm=0):\n    return 8",
            "def shipping_fee(weight_kg, /, subtotal_rm):\n    return 8",
            "def shipping_fee(weight_kg, *, subtotal_rm):\n    return 8",
            "def shipping_fee(weight_kg, subtotal_rm, *extra):\n    return 8",
            "def shipping_fee(weight_kg, subtotal_rm, **extra):\n    return 8",
            "def shipping_fee(weight_kg: int, subtotal_rm):\n    return 8",
            "def shipping_fee(weight_kg, subtotal_rm) -> int:\n    return 8",
            "def shipping_fee[T](weight_kg, subtotal_rm):\n    return 8",
            "@decorator\ndef shipping_fee(weight_kg, subtotal_rm):\n    return 8",
            "async def shipping_fee(weight_kg, subtotal_rm):\n    return 8",
            "fee = 8\n" + fixture(), fixture() + "\nfee = 8\n", "", "# comment only",
        )
        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(check_candidate(source).kind, "policy")

    def test_comparisons_only_in_conditions_and_exact_integer_literals(self):
        for body in (
            "return True", "return None", "return 8.0", "return '8'", "return b'8'", "return 8j",
            "return weight_kg > 2", "fee = weight_kg > 2\nreturn fee",
            "return 8 + (weight_kg > 2)", "if weight_kg:\n    return 8\nreturn 3",
            "if 0 < weight_kg < 20:\n    return 8\nreturn 3",
            "if (weight_kg > 2) == 1:\n    return 8\nreturn 3",
            "if weight_kg > 2 and subtotal_rm > 100:\n    return 8\nreturn 3",
        ):
            with self.subTest(body=body):
                self.assertEqual(check_candidate(function(body)).kind, "policy")

    def test_source_encoding_size_and_parser_failures_are_normalized(self):
        for source, code in ((None, "source_type"), (b"x", "source_type"), ("x" * 2049, "source_size"),
                             ("é" * 1025, "source_size"), ("\ud800", "source_encoding")):
            with self.subTest(code=code):
                self.assertEqual(check_candidate(source).error, code)
        self.assertEqual(check_candidate(fixture("syntax_error.txt")).error, "invalid_syntax")
        self.assertEqual(check_candidate(function("return 8") + "\0").error, "invalid_syntax")
        exact_boundary = function("return 8")
        exact_boundary += "#" + "x" * (2048 - len(exact_boundary.encode("utf-8")) - 1)
        self.assertEqual(interpret(exact_boundary, 0, 0), 8)
        for error in (RecursionError("private content"), MemoryError("private content")):
            with patch("code_generation_agent.interpreter.ast.parse", side_effect=error):
                self.assertEqual(check_candidate(fixture()).error, "parser_limit")

    def test_ast_size_depth_and_numeric_bounds(self):
        self.assertEqual(check_candidate(function("fee = 8\n" * 30 + "return fee")).error, "node_limit")
        deep = function("return " + "(" * 13 + "8" + " + 0)" * 13)
        self.assertEqual(check_candidate(deep).error, "depth_limit")
        self.assertEqual(check_candidate(function("return 1000001")).error, "integer_literal")
        for body, code in (
            ("return 1000 * 1001", "integer_overflow"),
            ("return 1000000 + 1", "integer_overflow"),
            ("return 0 - 1000000 - 1", "integer_overflow"),
            ("return 101", "fee_range"), ("return 0 - 1", "fee_range"),
            ("return missing", "unbound_name"), ("fee = 8", "missing_return"),
            ("return", "missing_return_value"),
        ):
            with self.subTest(body=body):
                feedback = check_candidate(function(body))
                self.assertEqual(len(feedback.tests), 20)
                self.assertEqual({result.error for result in feedback.tests}, {code})

    def test_input_validation_and_fuel_cannot_be_bypassed_via_api(self):
        for weight, subtotal in ((True, 0), (1.0, 0), (-1, 0), (21, 0), (0, False), (0, -1), (0, 1001), (0, "1")):
            with self.subTest(weight=weight, subtotal=subtotal):
                with self.assertRaises(Rejected) as caught:
                    interpret(fixture(), weight, subtotal)
                self.assertEqual(caught.exception.kind, "input")
        for limit in (True, 0, 101, 1.5):
            with self.subTest(limit=limit), self.assertRaises(Rejected):
                interpret(fixture(), 2, 100, step_limit=limit)
        with self.assertRaises(Rejected) as caught:
            interpret(fixture(), 2, 100, step_limit=1)
        self.assertEqual(caught.exception.code, "step_limit")

    def test_locals_are_fresh_for_every_case_and_invocation(self):
        source = function("if weight_kg == 0:\n    fee = 8\nreturn fee")
        self.assertEqual(interpret(source, 0, 0), 8)
        with self.assertRaises(Rejected) as caught:
            interpret(source, 1, 0)
        self.assertEqual(caught.exception.code, "unbound_name")
        feedback = check_candidate(source)
        self.assertEqual(sum(result.error == "unbound_name" for result in feedback.tests), 16)
