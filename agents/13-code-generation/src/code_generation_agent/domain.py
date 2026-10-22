"""Immutable host contract and evidence for one run.

The oracle is a tuple of literal expected values, never computed by candidate
code. Feedback records observations rather than instructions or authority.
RunResult is a terminal snapshot; only its persisted completed report can select
an accepted source. No state is shared between runs.
"""

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
import json

SPECIFICATION = (
    "shipping_fee(weight_kg, subtotal_rm): exact integers, excluding bool; "
    "weight 0..20, subtotal 0..1000. Return integer RM: base 8, plus 3 per "
    "kg above 2, minus 5 only for subtotal strictly greater than 100. "
    "Return range 0..100. Synthetic learning tariff."
)
SCENARIOS = ("repair", "exhaustion", "policy-rejection", "syntax-error")


@dataclass(frozen=True)
class TestCase:
    test_id: str
    weight_kg: int
    subtotal_rm: int
    expected: int


ORACLE = (
    TestCase("w0-s0", 0, 0, 8), TestCase("w0-s100", 0, 100, 8),
    TestCase("w0-s101", 0, 101, 3), TestCase("w0-s1000", 0, 1000, 3),
    TestCase("w1-s0", 1, 0, 8), TestCase("w1-s100", 1, 100, 8),
    TestCase("w1-s101", 1, 101, 3), TestCase("w1-s1000", 1, 1000, 3),
    TestCase("w2-s0", 2, 0, 8), TestCase("w2-s100", 2, 100, 8),
    TestCase("w2-s101", 2, 101, 3), TestCase("w2-s1000", 2, 1000, 3),
    TestCase("w3-s0", 3, 0, 11), TestCase("w3-s100", 3, 100, 11),
    TestCase("w3-s101", 3, 101, 6), TestCase("w3-s1000", 3, 1000, 6),
    TestCase("w20-s0", 20, 0, 62), TestCase("w20-s100", 20, 100, 62),
    TestCase("w20-s101", 20, 101, 57), TestCase("w20-s1000", 20, 1000, 57),
)


class Status(StrEnum):
    COMPLETED = "completed"
    EXHAUSTED = "exhausted"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class TestResult:
    test_id: str
    expected: int
    actual: int | None
    passed: bool
    error: str | None = None


@dataclass(frozen=True)
class Feedback:
    """Bounded evaluator evidence; errors are stable codes without source text."""

    kind: str
    error: str | None = None
    tests: tuple[TestResult, ...] = ()

    @property
    def passed(self) -> bool:
        return self.kind == "tested" and len(self.tests) == 20 and all(
            result.passed for result in self.tests
        )


@dataclass(frozen=True)
class Attempt:
    number: int
    source_digest: str | None
    source_artifact: str | None
    prior_feedback: tuple[Feedback, ...]
    feedback: Feedback


@dataclass(frozen=True)
class RunResult:
    """Published evidence or an honest unpublished failure snapshot.

    attempt_count counts proposal requests, including one interrupted or failed
    request. attempts contains only fully written attempt records.
    """

    status: Status
    attempt_count: int
    attempts: tuple[Attempt, ...]
    specification_digest: str
    oracle_digest: str
    run_directory: str | None
    report_path: str | None
    accepted_source: str | None
    error: str | None = None
    mode: str = "fixture"


def digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def json_text(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


SPECIFICATION_DIGEST = digest(SPECIFICATION)
ORACLE_DIGEST = digest(json_text([asdict(case) for case in ORACLE]))
