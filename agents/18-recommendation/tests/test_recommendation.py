"""Behavior checks use small hand-calculable inputs, independent of fixtures."""

import copy
import itertools
import json
import unittest
from importlib import resources

from recommendation import InputError, recommend


def exercise(identifier, topics=None, duration=20, difficulty="beginner", required=None):
    return {
        "id": identifier, "title": identifier.replace("-", " ").title(),
        "topics": topics if topics is not None else ["python"],
        "duration_minutes": duration, "difficulty": difficulty,
        "required_skills": required if required is not None else [],
    }


def catalogue(exercises=None):
    return {
        "version": "test-v1", "topics": ["python", "testing", "sql", "graphics"],
        "skills": ["python-basics", "testing-basics"],
        "exercises": exercises if exercises is not None else [
            exercise("both", ["python", "testing"], 30),
            exercise("short", ["python"], 10),
            exercise("testing", ["testing"], 15),
            exercise("unrelated", ["sql"], 5),
        ],
    }


def request(**overrides):
    result = {
        "topic_weights": {"python": 3, "testing": 2},
        "max_duration_minutes": 30, "max_difficulty": "intermediate",
        "completed_skills": [], "excluded_exercise_ids": [], "limit": 20,
    }
    result.update(overrides)
    return result


class RecommendationBehaviorTests(unittest.TestCase):
    def test_hand_calculated_scores_and_exact_contributions(self):
        report = recommend(request(), catalogue())
        self.assertEqual(report["status"], "personalized")
        self.assertEqual([(item["id"], item["score"]) for item in report["recommendations"]],
                         [("both", 5), ("short", 3), ("testing", 2)])
        self.assertEqual(report["recommendations"][0]["matched_topics"],
                         [{"topic": "python", "weight": 3}, {"topic": "testing", "weight": 2}])
        self.assertEqual(report["unmatched_eligible_ids"], ["unrelated"])
        self.assertEqual(report["counts"], {"catalogue": 4, "eligible": 4, "matching": 3, "returned": 3, "rejected": 0})
        for item in report["recommendations"]:
            self.assertEqual(item["score"], sum(term["weight"] for term in item["matched_topics"]))

    def test_changing_preferences_changes_ranking_without_training(self):
        first = recommend(request(), catalogue())
        second = recommend(request(topic_weights={"testing": 8}), catalogue())
        self.assertEqual([item["id"] for item in second["recommendations"]], ["testing", "both"])
        self.assertEqual(recommend(request(), catalogue()), first)

    def test_every_gate_excludes_an_otherwise_winning_item(self):
        winner = exercise("winner", ["python", "testing"], 30, "intermediate", ["python-basics"])
        allowed = request(completed_skills=["python-basics"])
        changes = [
            {"excluded_exercise_ids": ["winner"]}, {"max_duration_minutes": 29},
            {"max_difficulty": "beginner"}, {"completed_skills": []},
        ]
        for change, reason in zip(changes, ["excluded", "duration", "difficulty", "missing_skills"]):
            with self.subTest(reason=reason):
                report = recommend(allowed | change, catalogue([winner]))
                self.assertEqual(report["status"], "empty")
                self.assertEqual(report["recommendations"], [])
                self.assertEqual(report["rejected"][0]["reasons"], [reason])

    def test_simultaneous_reasons_have_fixed_order_and_sorted_missing_skills(self):
        item = exercise("winner", ["python"], 31, "advanced", ["testing-basics", "python-basics"])
        report = recommend(request(excluded_exercise_ids=["winner"], max_difficulty="beginner"), catalogue([item]))
        self.assertEqual(report["rejected"], [{
            "id": "winner", "reasons": ["excluded", "duration", "difficulty", "missing_skills"],
            "missing_skills": ["python-basics", "testing-basics"],
        }])

    def test_duration_and_difficulty_equality_pass(self):
        item = exercise("equal", ["python"], 30, "intermediate", ["python-basics"])
        report = recommend(request(completed_skills=["python-basics"]), catalogue([item]))
        self.assertEqual(report["rejected"], [])
        self.assertEqual(report["recommendations"][0]["id"], "equal")

    def test_ties_use_duration_then_id_before_limit(self):
        items = [exercise("zulu", duration=20), exercise("beta", duration=10), exercise("alpha", duration=10)]
        report = recommend(request(limit=2), catalogue(items))
        self.assertEqual([item["id"] for item in report["recommendations"]], ["alpha", "beta"])
        self.assertEqual(report["counts"]["matching"], 3)
        self.assertEqual(report["counts"]["returned"], 2)

    def test_complete_report_invariant_under_all_small_catalogue_permutations(self):
        data = catalogue([
            exercise("zulu", ["testing", "python"]), exercise("alpha", ["python"]),
            exercise("unrelated", ["sql"]), exercise("rejected", duration=31),
        ])
        original = recommend(request(), data)
        for permutation in itertools.permutations(data["exercises"]):
            altered = copy.deepcopy(data)
            altered["exercises"] = list(permutation)
            altered["topics"].reverse()
            altered["skills"].reverse()
            for item in altered["exercises"]:
                item["topics"].reverse()
            self.assertEqual(recommend(request(topic_weights={"testing": 2, "python": 3}), altered), original)

    def test_request_list_order_has_no_effect(self):
        data = catalogue([exercise("alpha"), exercise("beta")])
        left = request(completed_skills=["testing-basics", "python-basics"], excluded_exercise_ids=["beta", "alpha"])
        right = request(completed_skills=["python-basics", "testing-basics"], excluded_exercise_ids=["alpha", "beta"])
        self.assertEqual(recommend(left, data), recommend(right, data))

    def test_cold_start_is_zero_score_nonpersonalized_baseline(self):
        report = recommend(request(topic_weights={}, limit=2), catalogue())
        self.assertEqual((report["status"], report["reason"]), ("cold_start", "non_personalized_baseline"))
        self.assertEqual([(item["id"], item["score"], item["matched_topics"]) for item in report["recommendations"]],
                         [("unrelated", 0, []), ("short", 0, [])])
        self.assertEqual(report["counts"]["matching"], 0)
        self.assertEqual(report["unmatched_eligible_ids"], ["both", "short", "testing", "unrelated"])

    def test_no_match_has_no_padding_or_baseline(self):
        report = recommend(request(topic_weights={"graphics": 100}), catalogue())
        self.assertEqual((report["status"], report["reason"]), ("no_match", "no_positive_topic_overlap"))
        self.assertEqual(report["recommendations"], [])
        self.assertEqual(report["counts"]["eligible"], 4)

    def test_empty_catalogue_and_all_filtered_are_distinguishable(self):
        for interests in ({}, {"python": 1}):
            empty = recommend(request(topic_weights=interests), catalogue([]))
            filtered = recommend(request(topic_weights=interests, max_duration_minutes=1), catalogue())
            self.assertEqual(empty["status"], "empty")
            self.assertEqual(filtered["status"], "empty")
            self.assertEqual(empty["reason"], "no_eligible_exercises")
            self.assertEqual((empty["counts"]["catalogue"], filtered["counts"]["catalogue"]), (0, 4))

    def test_inputs_are_unchanged_and_returned_data_is_not_retained(self):
        data, profile = catalogue(), request()
        before = copy.deepcopy((data, profile))
        report = recommend(profile, data)
        report["request"]["topic_weights"]["python"] = 100
        report["recommendations"][0]["matched_topics"].clear()
        self.assertEqual((data, profile), before)
        self.assertEqual(recommend(profile, data)["recommendations"][0]["score"], 5)

    def test_boundary_values_and_maximum_score(self):
        topics = [f"topic-{index}" for index in range(10)]
        data = {"version": "v1", "topics": topics, "skills": [], "exercises": [exercise("bounded", topics, 480, "advanced")]}
        report = recommend(request(topic_weights=dict.fromkeys(topics, 100), max_duration_minutes=480, max_difficulty="advanced"), data)
        self.assertEqual(report["recommendations"][0]["score"], 1000)
        data["exercises"][0]["duration_minutes"] = 1
        self.assertEqual(recommend(request(topic_weights={topics[0]: 1}, max_duration_minutes=1, max_difficulty="advanced"), data)["counts"]["returned"], 1)

    def test_all_200_items_and_limit_20_are_supported(self):
        data = catalogue([exercise(f"item-{index:03}") for index in range(200)])
        report = recommend(request(), data)
        self.assertEqual(report["counts"], {"catalogue": 200, "eligible": 200, "matching": 200, "returned": 20, "rejected": 0})
        self.assertEqual(report["recommendations"][0]["id"], "item-000")


_MISSING = object()


class RecommendationValidationTests(unittest.TestCase):
    def assert_invalid(self, profile=_MISSING, data=_MISSING):
        with self.assertRaises(InputError) as captured:
            recommend(request() if profile is _MISSING else profile, catalogue() if data is _MISSING else data)
        self.assertNotIn("PRIVATE_SENTINEL", str(captured.exception))

    def test_missing_extra_and_nonobject_inputs(self):
        for missing in request():
            altered = request()
            del altered[missing]
            self.assert_invalid(altered)
        self.assert_invalid(request() | {"PRIVATE_SENTINEL": 1})
        for invalid in (None, [], "PRIVATE_SENTINEL", 1, True):
            self.assert_invalid(invalid)
            self.assert_invalid(data=invalid)
        for missing in catalogue():
            altered = catalogue()
            del altered[missing]
            self.assert_invalid(data=altered)
        self.assert_invalid(data=catalogue() | {"extra": 0})

    def test_integer_bounds_types_and_boolean_rejection(self):
        for field, invalids in {
            "max_duration_minutes": [0, 481, True, 30.0, "30", None],
            "limit": [0, 21, False, 2.0, "2", None],
        }.items():
            for value in invalids:
                with self.subTest(field=field, value=value):
                    self.assert_invalid(request(**{field: value}))
        for value in (0, 101, True, 1.0, "1", None, -1):
            self.assert_invalid(request(topic_weights={"python": value}))
        for value in (0, 481, False, 1.0, "2", None):
            data = catalogue()
            data["exercises"][0]["duration_minutes"] = value
            self.assert_invalid(data=data)

    def test_invalid_enums_unknown_references_and_identifiers(self):
        self.assert_invalid(request(max_difficulty="PRIVATE_SENTINEL"))
        for field, value in [
            ("topic_weights", {"unknown": 1}), ("completed_skills", ["unknown"]),
            ("excluded_exercise_ids", ["unknown"]), ("topic_weights", []),
        ]:
            self.assert_invalid(request(**{field: value}))
        for identifier in ("", "Upper", "white space", "a" * 65, "é", "a\n", "a/b", 3):
            self.assert_invalid(request(topic_weights={identifier: 1}))
        for field, value in [("topics", ["unknown"]), ("required_skills", ["unknown"]), ("difficulty", "expert")]:
            data = catalogue()
            data["exercises"][0][field] = value
            self.assert_invalid(data=data)

    def test_duplicate_members_and_ids(self):
        for field, values in [("completed_skills", ["python-basics"] * 2), ("excluded_exercise_ids", ["both"] * 2)]:
            self.assert_invalid(request(**{field: values}))
        for field in ("topics", "skills"):
            data = catalogue()
            data[field].append(data[field][0])
            self.assert_invalid(data=data)
        for field, values in [("topics", ["python"] * 2), ("required_skills", ["python-basics"] * 2)]:
            data = catalogue()
            data["exercises"][0][field] = values
            self.assert_invalid(data=data)
        data = catalogue()
        data["exercises"].append(copy.deepcopy(data["exercises"][0]))
        self.assert_invalid(data=data)

    def test_list_schema_and_collection_limits(self):
        for field in ("completed_skills", "excluded_exercise_ids"):
            for invalid in ({}, "python-basics", [True], [None]):
                self.assert_invalid(request(**{field: invalid}))
        for field in ("topics", "skills", "exercises"):
            data = catalogue()
            data[field] = {}
            self.assert_invalid(data=data)
        for field in ("topics", "skills"):
            data = catalogue()
            data[field] = [f"value-{index}" for index in range(101)]
            self.assert_invalid(data=data)
        self.assert_invalid(data=catalogue([exercise(f"item-{index}") for index in range(201)]))
        data = catalogue()
        data["topics"] = [f"topic-{index}" for index in range(11)]
        data["exercises"][0]["topics"] = data["topics"]
        self.assert_invalid(data=data)
        data = catalogue()
        data["skills"] = [f"skill-{index}" for index in range(21)]
        data["exercises"][0]["required_skills"] = data["skills"]
        self.assert_invalid(data=data)
        data = catalogue()
        data["exercises"][0]["topics"] = []
        self.assert_invalid(data=data)

    def test_exercise_fields_and_text(self):
        for field in exercise("valid"):
            data = catalogue()
            del data["exercises"][0][field]
            self.assert_invalid(data=data)
        data = catalogue()
        data["exercises"][0]["extra"] = 1
        self.assert_invalid(data=data)
        for value in ("", "   ", "a" * 121, "PRIVATE_SENTINEL\n", "bad\u0085", True):
            data = catalogue()
            data["exercises"][0]["title"] = value
            self.assert_invalid(data=data)
        for value in ("", " ", "v" * 65, 1, "x\n"):
            self.assert_invalid(data=catalogue() | {"version": value})

    def test_direct_python_nonjson_cyclic_deep_and_oversized_values(self):
        class CustomInteger(int):
            pass

        invalids = [object(), {"x": {1, 2}}, {1: "value"}, {"x": b"data"}, {"x": (1, 2)},
                    {"x": float("nan")}, {"x": float("inf")}, {"x": CustomInteger(1)}, {"x": "\ud800"}]
        cyclic = {}
        cyclic["self"] = cyclic
        invalids.append(cyclic)
        deeply_nested = []
        for _ in range(1000):
            deeply_nested = [deeply_nested]
        invalids.extend([deeply_nested, {"x": "x" * (256 * 1024)}, {"x": 10 ** 5000}])
        for invalid in invalids:
            with self.subTest(kind=type(invalid).__name__):
                self.assert_invalid(invalid)

    def test_title_brackets_are_data_and_not_json_depth(self):
        data = catalogue()
        data["exercises"][0]["title"] = "[" * 100
        report = recommend(request(), data)
        self.assertEqual(report["recommendations"][0]["title"], "[" * 100)


class PackagedDataTests(unittest.TestCase):
    def test_all_original_packaged_scenarios(self):
        root = resources.files("recommendation").joinpath("data")
        data = json.loads(root.joinpath("catalogue.json").read_text())
        expected = {
            "normal": ("personalized", ["unit-tests", "safe-json", "read-files"]),
            "cold-start": ("cold_start", ["cli-help", "read-files", "write-guide"]),
            "no-match": ("no_match", []), "constrained": ("personalized", ["parse-records"]),
            "no-eligible": ("empty", []),
        }
        for scenario, (status, identifiers) in expected.items():
            profile = json.loads(root.joinpath("scenarios", f"{scenario}.json").read_text())
            with self.subTest(scenario=scenario):
                report = recommend(profile, data)
                self.assertEqual(report["status"], status)
                self.assertEqual([item["id"] for item in report["recommendations"]], identifiers)
                self.assertEqual(report["counts"]["catalogue"], 16)
                self.assertEqual(report["counts"]["eligible"] + report["counts"]["rejected"], 16)


if __name__ == "__main__":
    unittest.main()
