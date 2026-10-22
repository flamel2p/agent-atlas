"""Verify the installed restricted interpreter against an independent oracle.

The 21-entry base-fee table is literal, independent of the implementation's
oracle or fixture. Every valid input is interpreted and compared with an exact
integer expectation. Adversarial cases must raise the public Rejected error;
an unrelated Python exception does not establish a controlled rejection.
Candidate text is never executed as CPython code. This verifies the bundled
repaired fixture and selected boundaries, not arbitrary generated programs.
"""

from importlib.resources import files
import json


BASE_FEES = (8, 8, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35, 38, 41, 44, 47, 50, 53, 56, 59, 62)

# Each case isolates a source or input boundary. Dead branches exercise full
# syntax validation before interpretation can choose a reachable path.
REJECTION_CASES = (
    ("unreachable_call", "def shipping_fee(weight_kg, subtotal_rm):\n    if weight_kg < 0:\n        bad = print(1)\n    return 8\n", 0, 0, 100),
    ("unreachable_import", "def shipping_fee(weight_kg, subtotal_rm):\n    if weight_kg < 0:\n        import os\n    return 8\n", 0, 0, 100),
    ("comparison_addition", "def shipping_fee(weight_kg, subtotal_rm):\n    return 8 + (weight_kg > 2)\n", 3, 0, 100),
    ("comparison_multiplication", "def shipping_fee(weight_kg, subtotal_rm):\n    return 8 * (weight_kg > 2)\n", 3, 0, 100),
    ("boolean_constant", "def shipping_fee(weight_kg, subtotal_rm):\n    return True\n", 0, 0, 100),
    ("boolean_return", "def shipping_fee(weight_kg, subtotal_rm):\n    return weight_kg > 2\n", 3, 0, 100),
    ("decorator", "@decorator\ndef shipping_fee(weight_kg, subtotal_rm):\n    return 8\n", 0, 0, 100),
    ("parameter_annotation", "def shipping_fee(weight_kg: int, subtotal_rm):\n    return 8\n", 0, 0, 100),
    ("return_annotation", "def shipping_fee(weight_kg, subtotal_rm) -> int:\n    return 8\n", 0, 0, 100),
    ("unreachable_loop", "def shipping_fee(weight_kg, subtotal_rm):\n    if weight_kg < 0:\n        while weight_kg < 0:\n            weight_kg = weight_kg + 1\n    return 8\n", 0, 0, 100),
    ("intermediate_overflow", "def shipping_fee(weight_kg, subtotal_rm):\n    fee = 1000000 * 2\n    return fee - 1000000 - 999992\n", 0, 0, 100),
    ("unbound_local", "def shipping_fee(weight_kg, subtotal_rm):\n    if weight_kg > 2:\n        fee = 8\n    return fee\n", 0, 0, 100),
    ("boolean_weight", "def shipping_fee(weight_kg, subtotal_rm):\n    return 8\n", True, 0, 100),
    ("boolean_subtotal", "def shipping_fee(weight_kg, subtotal_rm):\n    return 8\n", 0, False, 100),
    ("step_exhaustion", "def shipping_fee(weight_kg, subtotal_rm):\n    fee = weight_kg + 8\n    return fee\n", 0, 0, 1),
)

EXPECTED_REJECTIONS = {
    "intermediate_overflow": ("evaluation", "integer_overflow"),
    "unbound_local": ("evaluation", "unbound_name"),
    "boolean_weight": ("input", "weight_range"),
    "boolean_subtotal": ("input", "subtotal_range"),
    "step_exhaustion": ("evaluation", "step_limit"),
}


def main() -> int:
    """Print bounded JSON evidence and return nonzero for any failed check."""
    summary = {
        "mode": "fixture-independent",
        "exhaustive": {"total": 0, "passed": 0, "failed": 0},
        "rejections": {"total": 0, "passed": 0, "failed": 0},
        "failures": [],
    }

    def fail(group: str, case: str, reason: str) -> None:
        summary[group]["failed"] += 1
        # Retain counts for every failure while bounding diagnostic output.
        if len(summary["failures"]) < 10:
            summary["failures"].append({"case": case, "reason": reason})

    try:
        from code_generation_agent.interpreter import Rejected, interpret

        source = files("code_generation_agent").joinpath("fixtures/repaired.txt").read_text(encoding="utf-8")
    except Exception as error:
        summary["startup_error"] = type(error).__name__
        summary["status"] = "failed"
        print(json.dumps(summary, sort_keys=True))
        return 1

    for weight, base_fee in enumerate(BASE_FEES):
        for subtotal in range(1001):
            summary["exhaustive"]["total"] += 1
            expected = base_fee - (5 if subtotal > 100 else 0)
            case = f"weight={weight},subtotal={subtotal}"
            try:
                actual = interpret(source, weight, subtotal)
            except Exception as error:
                fail("exhaustive", case, f"unexpected_{type(error).__name__}")
            else:
                if type(actual) is not int or actual != expected:
                    fail("exhaustive", case, "wrong_value_or_non_integer")
                else:
                    summary["exhaustive"]["passed"] += 1

    for name, candidate, weight, subtotal, limit in REJECTION_CASES:
        summary["rejections"]["total"] += 1
        try:
            interpret(candidate, weight, subtotal, step_limit=limit)
        except Rejected as error:
            details = (getattr(error, "kind", None), getattr(error, "code", None))
            expected = EXPECTED_REJECTIONS.get(name)
            if expected is not None and details != expected:
                fail("rejections", name, "wrong_rejection_reason")
            elif all(isinstance(value, str) and value for value in details):
                summary["rejections"]["passed"] += 1
            else:
                fail("rejections", name, "missing_rejection_kind_or_code")
        except Exception as error:
            fail("rejections", name, f"unexpected_{type(error).__name__}")
        else:
            fail("rejections", name, "accepted_forbidden_case")

    failed = summary["exhaustive"]["failed"] + summary["rejections"]["failed"]
    summary["status"] = "failed" if failed else "passed"
    print(json.dumps(summary, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
