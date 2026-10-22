"""Behavioral evidence for feedback, deterministic selection, and work budgets."""

from dataclasses import FrozenInstanceError, asdict, fields, is_dataclass
from hashlib import sha256
from itertools import product
import json
import unittest
from unittest.mock import patch

from general_problem_solver import solve_document
from general_problem_solver.domain import evaluate
from test_domain import example


def independently_feasible(value, starts):
    """Test oracle uses interval sets and raw JSON, without production evaluation."""
    tasks = sorted(value["tasks"], key=lambda task: task["id"])
    intervals = {task["id"]: set(range(start, start + task["duration"])) for task, start in zip(tasks, starts, strict=True)}
    by_id = {task["id"]: (start, start + task["duration"]) for task, start in zip(tasks, starts, strict=True)}
    for task in tasks:
        start, finish = by_id[task["id"]]
        if not task["earliest_start"] <= start or not finish <= task["latest_finish"]:
            return False
        if any(by_id[key][1] > start for key in task["after"]):
            return False
    for resource in value["resources"]:
        for tick in range(value["horizon"]):
            demand = sum(task["requires"].get(resource["id"], 0) for task in tasks if tick in intervals[task["id"]])
            if demand > resource["capacity"]:
                return False
    return True


class SolverTests(unittest.TestCase):
    def test_revision_uses_actual_feedback_and_independent_acceptance(self):
        document = example()
        with patch("general_problem_solver.solver.evaluate", wraps=evaluate) as checked:
            report = solve_document(document)
        self.assertEqual((report.status, report.stop_reason), ("solved", "feasible"))
        self.assertEqual((report.iterations, report.evaluations), (2, 3))
        first, revision = report.history
        self.assertEqual(first.strategy_id, "independent_starts")
        self.assertEqual(first.evaluation.candidate.starts, (0, 0))
        self.assertEqual(first.evaluation.score, 2)
        self.assertEqual(revision.strategy_id, "bottleneck_repair")
        self.assertEqual(revision.triggering_violations, first.evaluation.violations)
        self.assertEqual(revision.evaluation.candidate.starts, (2, 0))
        self.assertEqual(revision.evaluations_consumed, 2)
        self.assertEqual(checked.call_count, report.evaluations)
        self.assertTrue(independently_feasible(json.loads(document), report.best.candidate.starts))
        self.assertTrue(all(attempt.analogy_kind == "illustrative_heuristic" for attempt in report.history))

    def test_initial_success_uses_one_evaluation_and_identical_independent_reports(self):
        document = example("already-valid")
        original = bytes(document)
        first, second = solve_document(document), solve_document(document)
        self.assertEqual((first.iterations, first.evaluations), (1, 1))
        self.assertEqual(json.dumps(asdict(first), sort_keys=True), json.dumps(asdict(second), sort_keys=True))
        self.assertIsNot(first.history, second.history)
        self.assertIsNot(first.history[0], second.history[0])
        self.assertEqual(document, original)
        self.assertEqual(first.input_sha256, sha256(document).hexdigest())
        with self.assertRaises(FrozenInstanceError):
            first.status = "unsolved"
        def immutable(value):
            self.assertNotIsInstance(value, (list, dict, set))
            if is_dataclass(value):
                self.assertTrue(value.__dataclass_params__.frozen)
                for field in fields(value):
                    immutable(getattr(value, field.name))
            elif isinstance(value, tuple):
                for item in value:
                    immutable(item)
        immutable(first)

    def test_dependency_repair_and_decomposition(self):
        document = example("dependency")
        report = solve_document(document)
        self.assertEqual(report.status, "solved")
        self.assertTrue(independently_feasible(json.loads(document), report.best.candidate.starts))
        self.assertEqual(report.decomposition.dependencies, (("a", "b"),))
        self.assertEqual(report.decomposition.resource_groups[0].task_ids, ())
        self.assertEqual(report.history[1].triggering_violations[0].kind, "dependency")

    def test_feasible_local_minimum_has_no_revision_and_counts_rejected_neighbors(self):
        document = example("local-minimum")
        with patch("general_problem_solver.solver.evaluate", wraps=evaluate) as checked:
            report = solve_document(document)
        self.assertEqual((report.status, report.stop_reason), ("unsolved", "local_minimum"))
        self.assertEqual((report.iterations, report.evaluations), (1, 7))
        self.assertEqual(report.best.candidate.starts, (2, 1, 1))
        self.assertEqual(checked.call_count, 7)
        self.assertTrue(all(call.args[1].starts[0] == 2 for call in checked.call_args_list))
        witnesses = [starts for starts in product(range(4), repeat=3) if independently_feasible(json.loads(document), starts)]
        self.assertEqual(witnesses, [(3, 2, 1)])

    def test_impossible_input_has_failed_candidate_and_no_impossibility_claim(self):
        report = solve_document(example("impossible"))
        self.assertEqual((report.status, report.stop_reason), ("unsolved", "local_minimum"))
        self.assertEqual((report.iterations, report.evaluations), (1, 1))
        self.assertEqual(report.best.score, 2)
        self.assertTrue(report.best.violations)

    def test_iteration_limit_precedes_evaluation_limit_before_a_scan(self):
        with patch("general_problem_solver.solver.evaluate", wraps=evaluate) as checked:
            report = solve_document(example("iteration-limit"))
        self.assertEqual(report.stop_reason, "iteration_limit")
        self.assertEqual((report.iterations, report.evaluations, checked.call_count), (1, 1, 1))

    def test_mid_scan_budget_preserves_improvement(self):
        with patch("general_problem_solver.solver.evaluate", wraps=evaluate) as checked:
            report = solve_document(example("evaluation-limit"))
        self.assertEqual(report.stop_reason, "evaluation_limit")
        self.assertEqual((report.iterations, report.evaluations, checked.call_count), (2, 2, 2))
        self.assertEqual(report.best.candidate.starts, (1, 0))
        self.assertEqual(report.best.score, 1)
        self.assertEqual(report.history[-1].evaluations_consumed, 1)

    def test_budget_before_scan_and_mid_scan_without_improvement(self):
        for budget, expected_evaluations in ((1, 1), (2, 2)):
            with self.subTest(budget=budget):
                value = json.loads(example("local-minimum"))
                value["budget"]["evaluations"] = budget
                with patch("general_problem_solver.solver.evaluate", wraps=evaluate) as checked:
                    report = solve_document(json.dumps(value).encode())
                self.assertEqual(report.stop_reason, "evaluation_limit")
                self.assertEqual(report.iterations, 1)
                self.assertEqual((report.evaluations, checked.call_count), (expected_evaluations, expected_evaluations))

    def test_complete_scan_at_exact_budget_can_establish_local_minimum(self):
        value = json.loads(example("local-minimum"))
        value["budget"]["evaluations"] = 7
        report = solve_document(json.dumps(value).encode())
        self.assertEqual(report.stop_reason, "local_minimum")
        self.assertEqual(report.evaluations, 7)

    def test_feasible_on_last_evaluation_wins(self):
        value = json.loads(example())
        value["budget"] = {"iterations": 2, "evaluations": 3}
        report = solve_document(json.dumps(value).encode())
        self.assertEqual((report.status, report.stop_reason), ("solved", "feasible"))
        self.assertEqual((report.iterations, report.evaluations), (2, 3))

    def test_equal_improvements_use_full_lexicographic_starts(self):
        value = json.loads(example())
        third = dict(value["tasks"][0], id="c")
        value["tasks"].append(third)
        value["budget"]["iterations"] = 2
        report = solve_document(json.dumps(value).encode())
        self.assertEqual(report.stop_reason, "iteration_limit")
        self.assertEqual(report.best.candidate.starts, (0, 0, 2))
        self.assertEqual([item.evaluation.score for item in report.history], [4, 2])
        self.assertEqual((report.iterations, report.evaluations), (2, 7))
        value["budget"] = {"iterations": 5, "evaluations": 7}
        report = solve_document(json.dumps(value).encode())
        self.assertEqual(report.stop_reason, "evaluation_limit")
        self.assertEqual(report.best.candidate.starts, (0, 0, 2))

    def test_several_revisions_use_strictly_lower_actual_scores(self):
        value = json.loads(example())
        value["horizon"] = 3
        value["tasks"].append(dict(value["tasks"][0], id="c"))
        for task in value["tasks"]:
            task.update(duration=1, latest_finish=3)
        report = solve_document(json.dumps(value).encode())
        self.assertEqual([item.evaluation.score for item in report.history], [2, 1, 0])
        self.assertEqual((report.iterations, report.evaluations), (3, 9))
        self.assertTrue(independently_feasible(value, report.best.candidate.starts))
        for previous, revision in zip(report.history, report.history[1:]):
            self.assertEqual(revision.triggering_violations, previous.evaluation.violations)

    def test_baseline_clamps_to_horizon_when_window_cannot_fit(self):
        value = json.loads(example("impossible"))
        value["tasks"][0].update(earliest_start=1, requires={})
        report = solve_document(json.dumps(value).encode())
        self.assertEqual(report.best.candidate.starts, (0,))
        self.assertEqual(report.best.violations[0].kind, "window_start")


if __name__ == "__main__":
    unittest.main()
