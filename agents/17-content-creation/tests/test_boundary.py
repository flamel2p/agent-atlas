"""Exercise strict external input, internal fixture validation, and safe file reads."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from content_creation import Brief, InputError
from content_creation.boundary import (
    BRIEF_MAX_BYTES, FIXTURE_MAX_BYTES, _resource_bytes, brief_from_bytes,
    load_brief_file, load_scenario, snapshot_from_bytes,
)
from content_creation.domain import FixtureError


class BriefBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.value = asdict(load_scenario("relaxed"))
        self.raw = json.dumps(self.value).encode()

    def test_invalid_json_encoding_keys_numbers_and_controls(self):
        candidates = [
            b"", b"{", b"[]", b"null", b"\xff", b'{} trailing',
            b'{"audience":"team_leads","audience":"developers"}',
            b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":1e9999}',
            b'{"x":1.5}', b'{"x":"\\ud800"}', b'{"x":"\\udfff"}',
            b'{"x":"\\u0000"}', b'{"x":"\\u007f"}', b'{"x":"\\u0085"}',
            b'[' * 1500 + b'0' + b']' * 1500,
            b'{"x":' + b'9' * 5000 + b'}',
            b' ' * (BRIEF_MAX_BYTES + 1),
        ]
        for raw in candidates:
            with self.subTest(size=len(raw)), self.assertRaises(InputError):
                brief_from_bytes(raw)

    def test_invalid_schema_values_are_rejected(self):
        candidates = []
        for field in self.value:
            missing = dict(self.value)
            del missing[field]
            candidates.append(missing)
        candidates.append(dict(self.value, unknown="unsupported"))
        for field, values in {
            "audience": [None, True, [], {}, "unsupported", " team_leads"],
            "required_fact_ids": ["availability", [], ["availability", "availability"],
                                  [None], [["availability"]], [" availability"], ["x" * 41], list("abcdefg")],
            "forbidden_phrases": ["seamless", [None], [""], ["   "], ["x" * 81],
                                   ["word", " WORD\t"], ["strasse", "STRAẞE"],
                                   [str(i) for i in range(17)]],
            "email_max_words": [True, False, None, 0, 501, "120", [], 1.0],
            "docs_max_words": [True, -1, 501, {}, "100"],
        }.items():
            candidates.extend(dict(self.value, **{field: value}) for value in values)
        for candidate in candidates:
            with self.subTest(candidate=candidate), self.assertRaises(InputError):
                brief_from_bytes(json.dumps(candidate).encode())

    def test_valid_bounds_and_ordinary_whitespace_are_accepted(self):
        value = dict(self.value, email_max_words=1, docs_max_words=500,
                     forbidden_phrases=["  discover\tseamless\ncoordination.\r ", "x" * 80])
        self.assertEqual(brief_from_bytes(json.dumps(value).encode()).email_max_words, 1)
        padded = self.raw + b' ' * (BRIEF_MAX_BYTES - len(self.raw))
        self.assertEqual(brief_from_bytes(padded), load_scenario("relaxed"))
        with self.assertRaises(InputError):
            brief_from_bytes(padded + b' ')

    def test_python_brief_is_deeply_immutable_and_strict(self):
        values = dict(self.value)
        values["required_fact_ids"] = list(values["required_fact_ids"])
        with self.assertRaises(InputError):
            Brief(**values)
        values["required_fact_ids"] = tuple(values["required_fact_ids"])
        values["forbidden_phrases"] = []
        with self.assertRaises(InputError):
            Brief(**values)

    def test_regular_file_unchanged_and_final_symlinks_special_files_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regular = root / "brief.json"
            regular.write_bytes(self.raw)
            self.assertEqual(load_brief_file(regular), load_scenario("relaxed"))
            self.assertEqual(regular.read_bytes(), self.raw)
            symlink = root / "alias.json"
            symlink.symlink_to(regular)
            fifo = root / "pipe"
            os.mkfifo(fifo)
            oversized = root / "large.json"
            oversized.write_bytes(b' ' * (BRIEF_MAX_BYTES + 1))
            for selected in (symlink, fifo, oversized, root, root / "absent"):
                with self.subTest(path=selected.name), self.assertRaises(InputError):
                    load_brief_file(selected)

    def test_directory_aliases_are_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            (nested / "brief.json").write_bytes(self.raw)
            alias = root / "alias"
            alias.symlink_to(nested, target_is_directory=True)
            self.assertEqual(load_brief_file(alias / "brief.json"), load_scenario("relaxed"))

    def test_regular_file_replaced_by_fifo_is_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "brief.json"
            target.write_bytes(self.raw)
            original_open = os.open

            def raced_open(path, flags, *args, **kwargs):
                if path == target.name:
                    target.unlink()
                    os.mkfifo(target)
                return original_open(path, flags, *args, **kwargs)

            with patch("content_creation.boundary.os.open", side_effect=raced_open):
                with self.assertRaises(InputError):
                    load_brief_file(target)

    def test_scenario_names_are_allowlisted(self):
        with self.assertRaises(InputError):
            load_scenario("../../secrets")


class FixtureBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.raw = _resource_bytes("content.json")
        self.value = json.loads(self.raw)

    def test_digest_tracks_exact_bytes_even_when_content_is_equivalent(self):
        first = snapshot_from_bytes(self.raw)
        second = snapshot_from_bytes(self.raw + b"\n")
        self.assertEqual(first.facts, second.facts)
        self.assertNotEqual(first.sha256, second.sha256)

    def test_packaged_resource_reads_are_bounded_before_validation(self):
        for names, limit in ((("content.json",), FIXTURE_MAX_BYTES),
                             (("briefs", "launch.json"), BRIEF_MAX_BYTES)):
            with self.subTest(names=names), patch("content_creation.boundary.files") as resources:
                reader = resources.return_value.joinpath.return_value.open.return_value.__enter__.return_value
                reader.read.return_value = b"x"
                self.assertEqual(_resource_bytes(*names), b"x")
                reader.read.assert_called_once_with(limit + 1)

    def test_internal_identity_reference_and_copy_errors_fail(self):
        mutations = [
            lambda data: data.update(extra=True),
            lambda data: data.update(product=""),
            lambda data: data["sources"].append(data["sources"][0]),
            lambda data: data["sources"][0].update(id="bad/id"),
            lambda data: data["facts"][1].update(id=data["facts"][0]["id"]),
            lambda data: data["facts"][0].update(source_id="missing"),
            lambda data: data["facts"][0].update(text="Not the canonical product."),
            lambda data: data["facts"][0].update(text="LumenBoard lacks a final period"),
            lambda data: data["facts"][0].update(text="LumenBoard " + "x" * 240 + "."),
            lambda data: data["copy"]["email"].update(opening=[]),
            lambda data: data["copy"]["email"].update(opening=["same", "same"]),
            lambda data: data["copy"]["email"].update(opening=["newline\ninside"]),
            lambda data: data["copy"]["email"].update(title=[None]),
            lambda data: data["priorities"]["team_leads"][0].update(rank=True),
            lambda data: data["priorities"]["team_leads"][0].update(rank=101),
            lambda data: data["priorities"]["developers"][0].update(fact_id="missing"),
            lambda data: data["priorities"]["team_leads"][0].update(fact_id="boards"),
        ]
        for index, mutate in enumerate(mutations):
            data = json.loads(self.raw)
            mutate(data)
            with self.subTest(index=index), self.assertRaises(FixtureError):
                snapshot_from_bytes(json.dumps(data).encode())
        for raw in (b"{}", b"null", b"\xff", b' ' * (FIXTURE_MAX_BYTES + 1)):
            with self.assertRaises(FixtureError):
                snapshot_from_bytes(raw)


if __name__ == "__main__":
    unittest.main()
