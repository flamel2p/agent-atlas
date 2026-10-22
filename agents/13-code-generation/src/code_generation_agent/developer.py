"""Deterministic fixture developer with one feedback-directed repair rule.

The developer receives immutable specification text and observed feedback only.
It cannot write artifacts or choose tests. Its repair rule recognizes the five
strict-threshold failures; elapsed attempts alone cannot unlock repaired source.
This is a fixture simulation, not evidence of model reasoning.
"""

from importlib.resources import files
from typing import Protocol

from .domain import Feedback, SCENARIOS, SPECIFICATION


class Developer(Protocol):
    def propose(self, specification: str, feedback: tuple[Feedback, ...]) -> str: ...


class FixtureDeveloper:
    def __init__(self, scenario: str):
        if type(scenario) is not str or scenario not in SCENARIOS:
            raise ValueError("invalid_scenario")
        self.scenario = scenario

    def propose(self, specification: str, feedback: tuple[Feedback, ...]) -> str:
        if specification != SPECIFICATION:
            raise ValueError("unknown_specification")
        fixture = {
            "repair": "threshold_bug.txt", "exhaustion": "threshold_bug.txt",
            "policy-rejection": "policy_rejection.txt", "syntax-error": "syntax_error.txt",
        }[self.scenario]
        threshold_ids = {"w0-s100", "w1-s100", "w2-s100", "w3-s100", "w20-s100"}
        for observation in feedback:
            failures = tuple(result for result in observation.tests if not result.passed)
            if (
                self.scenario == "repair" and observation.kind == "tested"
                and len(observation.tests) == 20 and len(failures) == 5
                and {result.test_id for result in failures} == threshold_ids
                and all(result.error is None and result.actual == result.expected - 5 for result in failures)
            ):
                fixture = "repaired.txt"
        return files("code_generation_agent").joinpath("fixtures", fixture).read_text(encoding="utf-8")
