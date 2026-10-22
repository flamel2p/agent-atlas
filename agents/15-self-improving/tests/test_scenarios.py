"""Strict boundary checks distinguish malformed host data from excluded feedback."""

import copy
from io import BytesIO
import json
import unittest

from self_improving import ScenarioError, ScenarioName, load_scenario
from self_improving.scenarios import (
    MAX_FILE_BYTES, _decode_bundle, _decode_json, _read_bounded,
)
from test_experiment import bundle, decode


class ScenarioTests(unittest.TestCase):
    def test_strict_field_and_value_rules(self):
        mutations = [
            (0, ("schema_version",), True),
            (0, ("schema_version",), 2),
            (0, ("baseline", "config", "recency_topic"), "refunds"),
            (0, ("corpus", 0, "revision"), True),
            (0, ("corpus", 0, "revision"), 1.0),
            (0, ("corpus", 0, "revision"), 0),
            (0, ("corpus", 0, "revision"), 1_000_001),
            (0, ("corpus", 0, "tokens"), []),
            (0, ("corpus", 0, "tokens"), ["refund", "refund"]),
            (0, ("corpus", 0, "tokens"), ["Refund"]),
            (0, ("corpus", 0, "tokens"), [True]),
            (0, ("corpus", 0, "tokens"), "refund"),
            (0, ("corpus", 0, "tokens"), ["x" * 33]),
            (0, ("corpus", 0, "tokens"), ["x" + str(i) for i in range(65)]),
            (0, ("corpus", 0, "answer"), ""),
            (0, ("corpus", 0, "answer"), "x" * 2001),
            (0, ("corpus", 0, "answer"), "bad\x00answer"),
            (0, ("corpus", 0, "answer"), "bad\ud800answer"),
            (0, ("corpus", 0, "document_id"), "x" * 65),
            (0, ("corpus", 0, "topic"), "../refunds"),
            (0, ("traces", 0, "query", "tokens"), [None]),
            (0, ("traces", 0, "baseline_version_id"), "baseline"),
            (0, ("development_controls", 0, "group"), "stable"),
            (2, ("cases", 0, "group"), "other"),
        ]
        for file_index, path, value in mutations:
            with self.subTest(path=path, value=repr(value)[:60]):
                parts = bundle()
                target = parts[file_index]
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.assertRaises(ScenarioError):
                    decode(parts)

    def test_unknown_missing_and_self_approval_fields_are_errors(self):
        for index, path, key in ((0, (), "instructions"), (0, ("feedback", 0), "approved"),
                                 (1, ("records", 0), "trusted"), (2, ("cases", 0), "weight")):
            with self.subTest(path=path):
                parts = bundle()
                target = parts[index]
                for step in path:
                    target = target[step]
                target[key] = True
                with self.assertRaises(ScenarioError):
                    decode(parts)
        parts = bundle()
        del parts[0]["feedback"][0]["curator_record_id"]
        with self.assertRaises(ScenarioError):
            decode(parts)

    def test_duplicate_record_ids_are_errors(self):
        for index, key in ((0, "corpus"), (0, "traces"), (0, "feedback"), (1, "records"), (2, "cases")):
            with self.subTest(collection=key):
                parts = bundle()
                parts[index][key].append(copy.deepcopy(parts[index][key][0]))
                with self.assertRaises(ScenarioError):
                    decode(parts)

    def test_record_and_file_caps_apply_to_each_input(self):
        for index, key in ((0, "corpus"), (0, "traces"), (0, "feedback"),
                           (0, "development_controls"), (1, "records"), (2, "cases")):
            with self.subTest(collection=key):
                parts = bundle()
                parts[index][key] = [copy.deepcopy(parts[index][key][0]) for _ in range(101)]
                with self.assertRaisesRegex(ScenarioError, "at most 100"):
                    decode(parts)
        valid_bytes = [json.dumps(part).encode() for part in bundle()]
        for index in range(3):
            with self.subTest(file=index):
                contents = list(valid_bytes)
                contents[index] = b" " * (MAX_FILE_BYTES + 1)
                with self.assertRaisesRegex(ScenarioError, "exceeds"):
                    _decode_bundle("oversized", *contents)
        self.assertEqual(len(_read_bounded(BytesIO(b" " * MAX_FILE_BYTES))), MAX_FILE_BYTES)
        with self.assertRaises(ScenarioError):
            _read_bounded(BytesIO(b" " * (MAX_FILE_BYTES + 1)))

    def test_json_byte_level_failures(self):
        for data in (b'{"schema_version":1,"schema_version":1}', b'{"x":NaN}',
                     b'{"x":Infinity}', b'\xff', b'{invalid', b'[' * 17 + b']' * 17):
            with self.subTest(data=data[:60]):
                with self.assertRaises(ScenarioError):
                    _decode_json(data)
        self.assertEqual(_decode_json(b'{"answer":"[quoted brackets] \\\"ok\\\""}'),
                         {"answer": '[quoted brackets] "ok"'})

    def test_unknown_or_ineligible_host_references_fail_before_learning(self):
        changes = [
            (1, ("records", 0, "trace_id"), "unknown-trace"),
            (1, ("records", 0, "target_document_id"), "unknown-document"),
            (1, ("records", 0, "target_document_id"), "z-access-new"),
            (1, ("records", 0, "target_document_id"), "z-unused"),
            (0, ("traces", 0, "observed_document_id"), "unknown-document"),
            (2, ("cases", 0, "expected_document_id"), "unknown-document"),
            (2, ("cases", 0, "expected_document_id"), "z-access-new"),
            (2, ("cases", 0, "expected_document_id"), "z-unused"),
        ]
        for index, path, value in changes:
            with self.subTest(path=path, value=value):
                parts = bundle()
                target = parts[index]
                for step in path[:-1]:
                    target = target[step]
                target[path[-1]] = value
                with self.assertRaises(ScenarioError):
                    decode(parts)
        parts = bundle()
        parts[1]["records"].append(dict(parts[1]["records"][0], record_id="second-host-record"))
        with self.assertRaisesRegex(ScenarioError, "one record per trace"):
            decode(parts)

    def test_holdout_and_development_partition_rules(self):
        for split in ("trace-id", "trace-signature", "dev-signature", "heldout-signature", "missing-stable", "empty-holdout"):
            with self.subTest(split=split):
                parts = bundle()
                if split == "trace-id":
                    parts[2]["cases"][0]["query"]["query_id"] = parts[0]["traces"][0]["query"]["query_id"]
                elif split == "trace-signature":
                    parts[2]["cases"][0]["query"]["tokens"] = list(reversed(parts[0]["traces"][0]["query"]["tokens"]))
                elif split == "dev-signature":
                    parts[2]["cases"][0]["query"] = dict(parts[0]["development_controls"][0]["query"], query_id="copied-dev")
                elif split == "heldout-signature":
                    parts[2]["cases"].append(dict(parts[2]["cases"][0], query=dict(parts[2]["cases"][0]["query"], query_id="copied-heldout")))
                elif split == "missing-stable":
                    parts[2]["cases"] = [case for case in parts[2]["cases"] if case["group"] == "recent"]
                else:
                    parts[2]["cases"] = []
                with self.assertRaises(ScenarioError):
                    decode(parts)
        parts = bundle()
        parts[0]["development_controls"][0]["query"] = dict(parts[0]["traces"][0]["query"], query_id="copied-trace")
        with self.assertRaisesRegex(ScenarioError, "Development controls"):
            decode(parts)

    def test_valid_boundary_values_and_closed_loader(self):
        parts = bundle()
        parts[0]["corpus"][0]["answer"] = "x" * 2000
        parts[0]["corpus"][0]["revision"] = 1_000_000
        scenario = decode(parts)
        self.assertEqual(max(doc.revision for doc in scenario.selection.corpus), 1_000_000)
        with self.assertRaises(ScenarioError):
            load_scenario("improvement")
        with self.assertRaises(ScenarioError):
            load_scenario("../../outside")


if __name__ == "__main__":
    unittest.main()
