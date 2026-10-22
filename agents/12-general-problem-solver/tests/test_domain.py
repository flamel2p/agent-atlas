"""Contract checks for the external JSON boundary and independent evaluator."""

from copy import deepcopy
from importlib.resources import files
import json
import unittest

from general_problem_solver import InputError, solve_document
from general_problem_solver.domain import Candidate, Violation, evaluate, parse_document


def example(name="revision"):
    return files("general_problem_solver").joinpath("examples", name + ".json").read_bytes()


class ParsingTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(example())

    def test_rejects_missing_and_unknown_fields_at_every_object(self):
        for location in ((), ("budget",), ("resources", 0), ("tasks", 0)):
            for mode in ("missing", "unknown"):
                with self.subTest(location=location, mode=mode):
                    value = deepcopy(self.value)
                    obj = value
                    for key in location:
                        obj = obj[key]
                    if mode == "missing":
                        del obj[next(iter(obj))]
                    else:
                        obj["private-content\ud800"] = 1
                    with self.assertRaises(InputError) as raised:
                        solve_document(json.dumps(value).encode())
                    self.assertNotIn("private-content", str(raised.exception))
                    self.assertNotIn("\ud800", str(raised.exception))

    def test_duplicate_keys_in_root_budget_task_and_requirements(self):
        document = example()
        for old, new in (
            (b'"horizon": 4', b'"horizon": 4, "horizon": 4'),
            (b'"iterations": 5', b'"iterations": 5, "iterations": 5'),
            (b'"duration": 2', b'"duration": 2, "duration": 2'),
            (b'"bench": 1', b'"bench": 1, "bench": 1'),
        ):
            with self.subTest(field=old), self.assertRaises(InputError):
                solve_document(document.replace(old, new, 1))

    def test_invalid_number_spellings(self):
        for spelling in (b"true", b"false", b"4.0", b"4e0", b"NaN", b"Infinity", b"-Infinity", b"1e999", b"null", b'"4"'):
            with self.subTest(spelling=spelling), self.assertRaises(InputError):
                solve_document(example().replace(b'"horizon": 4', b'"horizon": ' + spelling))

    def test_numeric_bounds_and_boolean_rejection(self):
        locations = (
            (("horizon",), (0, 25, True)),
            (("resources", 0, "capacity"), (0, 9, True)),
            (("tasks", 0, "duration"), (0, 5, True)),
            (("tasks", 0, "earliest_start"), (-1, 4, True)),
            (("tasks", 0, "latest_finish"), (0, 5, True)),
            (("tasks", 0, "requires", "bench"), (0, 9, True)),
            (("budget", "iterations"), (0, 17, True)),
            (("budget", "evaluations"), (0, 1025, True)),
        )
        for path, invalids in locations:
            for invalid in invalids:
                with self.subTest(path=path, invalid=invalid):
                    value = deepcopy(self.value)
                    obj = value
                    for key in path[:-1]:
                        obj = obj[key]
                    obj[path[-1]] = invalid
                    with self.assertRaises(InputError):
                        parse_document(json.dumps(value).encode())

    def test_collection_bounds_and_types(self):
        for field, values in (
            ("tasks", [[], {}, None, self.value["tasks"] * 5]),
            ("resources", [[], {}, None, self.value["resources"] * 5]),
            ("budget", [[], None]),
        ):
            for invalid in values:
                with self.subTest(field=field, invalid=invalid):
                    value = deepcopy(self.value)
                    value[field] = invalid
                    with self.assertRaises(InputError):
                        parse_document(json.dumps(value).encode())
        for field, invalid in (("requires", []), ("requires", None), ("after", {}), ("after", ["b"] * 8)):
            with self.subTest(field=field, invalid=invalid):
                value = deepcopy(self.value)
                value["tasks"][0][field] = invalid
                with self.assertRaises(InputError):
                    parse_document(json.dumps(value).encode())

    def test_ids_references_duplicates_and_cycles(self):
        mutations = (
            lambda v: v["tasks"][0].update(id="A"),
            lambda v: v["tasks"][0].update(id="a" * 33),
            lambda v: v["tasks"][0].update(id="a\n"),
            lambda v: v["tasks"][0].update(id=""),
            lambda v: v["tasks"][0].update(id=True),
            lambda v: v["tasks"][0].update(id="b"),
            lambda v: v["resources"].append(v["resources"][0].copy()),
            lambda v: v["tasks"][0].update(requires={"unknown": 1}),
            lambda v: v["tasks"][0].update(after=["unknown"]),
            lambda v: v["tasks"][0].update(after=["a"]),
            lambda v: v["tasks"][0].update(after=["b", "b"]),
            lambda v: (v["tasks"][0].update(after=["b"]), v["tasks"][1].update(after=["a"])),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                value = deepcopy(self.value)
                mutate(value)
                with self.assertRaises(InputError):
                    parse_document(json.dumps(value).encode())

    def test_malformed_deep_oversized_and_wrong_transport(self):
        for document in (
            b"", b"[]", b"null", b"{}{}", b"{", b"\xff", b"\xef\xbb\xbf{}",
            b"[" * 2000 + b"0" + b"]" * 2000, b" " * 65_537,
            b'{"horizon":' + b"9" * 10_000 + b"}", "{}", bytearray(b"{}"), None,
        ):
            with self.subTest(kind=type(document), size=len(document) if document is not None else 0), self.assertRaises(InputError):
                solve_document(document)

    def test_exact_byte_ceiling_and_upper_domain_bounds(self):
        document = example()
        self.assertEqual(solve_document(document + b" " * (65_536 - len(document))).status, "solved")
        value = {
            "horizon": 24,
            "resources": [{"id": f"r{i}", "capacity": 8} for i in range(4)],
            "tasks": [{"id": f"t{i}", "duration": 24, "earliest_start": 0, "latest_finish": 24, "requires": {f"r{j}": 8 for j in range(4)}, "after": []} for i in range(8)],
            "budget": {"iterations": 16, "evaluations": 1024},
        }
        problem = parse_document(json.dumps(value).encode())
        self.assertEqual((len(problem.tasks), len(problem.resources)), (8, 4))
        self.assertEqual(problem.budget.evaluations, 1024)

    def test_well_formed_impossible_inputs_are_valid_and_unsolved(self):
        values = []
        demand = deepcopy(self.value)
        demand["tasks"][0]["requires"]["bench"] = 8
        values.append(demand)
        window = deepcopy(self.value)
        window["tasks"][0]["duration"] = 4
        window["tasks"][0]["earliest_start"] = 3
        values.append(window)
        dependency = json.loads(example("already-valid"))
        dependency["tasks"][1]["earliest_start"] = 0
        dependency["tasks"][1]["latest_finish"] = 2
        values.append(dependency)
        for value in values:
            with self.subTest(value=value):
                report = solve_document(json.dumps(value).encode())
                self.assertEqual(report.status, "unsolved")
                self.assertTrue(report.best.violations)


class EvaluatorTests(unittest.TestCase):
    def test_window_dependency_and_capacity_excesses_are_exact(self):
        value = {
            "horizon": 6,
            "resources": [{"id": "x", "capacity": 2}, {"id": "y", "capacity": 1}],
            "tasks": [
                {"id": "a", "duration": 2, "earliest_start": 1, "latest_finish": 4, "requires": {"x": 2, "y": 1}, "after": []},
                {"id": "b", "duration": 2, "earliest_start": 0, "latest_finish": 2, "requires": {"x": 1, "y": 2}, "after": ["a"]},
            ],
            "budget": {"iterations": 5, "evaluations": 100},
        }
        evaluation = evaluate(parse_document(json.dumps(value).encode()), Candidate((0, 1)))
        self.assertEqual(evaluation.violations, (
            Violation("window_start", ("a",), 1),
            Violation("window_finish", ("b",), 1),
            Violation("dependency", ("a", "b"), 1),
            Violation("capacity", ("a", "b"), 1, "x", 1),
            Violation("capacity", ("a", "b"), 2, "y", 1),
            Violation("capacity", ("b",), 1, "y", 2),
        ))
        self.assertEqual(evaluation.score, 7)
        self.assertFalse(evaluation.feasible)

    def test_touching_intervals_and_dependency_equality_are_feasible(self):
        problem = parse_document(example("already-valid"))
        evaluation = evaluate(problem, Candidate((0, 2)))
        self.assertEqual(evaluation.violations, ())
        self.assertEqual(evaluation.score, 0)
        self.assertTrue(evaluation.feasible)

    def test_normalization_preserves_separate_id_namespaces(self):
        value = json.loads(example())
        value["tasks"].reverse()
        value["resources"][0]["id"] = "a"
        for task in value["tasks"]:
            task["requires"] = {"a": 1}
        problem = parse_document(json.dumps(value).encode())
        self.assertEqual(tuple(task.id for task in problem.tasks), ("a", "b"))
        self.assertEqual(problem.resources[0].id, "a")


if __name__ == "__main__":
    unittest.main()
