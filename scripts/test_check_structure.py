"""Regression checks for repository governance, not demo runtime behavior."""

from pathlib import Path
import shutil
import tempfile
import unittest

from check_structure import audit, metadata


TEMPLATE = Path(__file__).resolve().parents[1] / "agent-library-bootstrap/repository-template"


class StructureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="agent-atlas-structure-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        shutil.copytree(TEMPLATE, self.root)
        self.case = self.root / "agents/tool-using"

    def assert_error(self, expected):
        errors = audit(self.root)
        self.assertTrue(any(expected in error for error in errors), errors)

    def recorded_ready_fixture(self):
        for name in ("README.md", "SPEC.md"):
            path = self.case / name
            text = path.read_text().replace("Status: planned", "Status: demo-ready")
            text = text.replace("Runtime: undecided", "Runtime: Python 3.9+")
            path.write_text(text.replace("Not implemented or run", "Synthetic checker fixture"))
        for directory in ("src", "tests"):
            (self.case / directory).mkdir()
            (self.case / directory / "fixture.py").write_text("# Checker fixture only.\n")
        with (self.case / "README.md").open("a") as readme:
            readme.write(
                "\nVerified on: 2026-10-16\n"
                "Verification command: python3 -m unittest\n"
                "Verification mode: fixture\n"
                "Verification result: passed\n"
                "Verified scope: Synthetic metadata; no execution claim\n"
                "\n## Fixture limitations\n"
            )

    def test_planned_scaffold(self):
        self.assertEqual(audit(self.root), [])

    def test_retained_reference_bundles(self):
        for name in ("agent-library-analysis", "agent-library-bootstrap"):
            (self.root / name).mkdir()
        self.assertEqual(audit(self.root), [])

    def test_root_runtime_directory_rejected(self):
        (self.root / "runtime").mkdir()
        self.assert_error("Unexpected root item: runtime")

    def test_root_dependency_manifest_rejected(self):
        (self.root / "package.json").write_text("{}")
        self.assert_error("Unexpected root item: package.json")

    def test_missing_specification_rejected(self):
        (self.case / "SPEC.md").unlink()
        self.assert_error("missing SPEC.md")

    def test_unowned_case_resources_rejected(self):
        (self.root / "agents/shared.py").write_text("")
        (self.root / "agents/.shared").mkdir()
        self.assert_error("Unowned agents/ item: shared.py")
        self.assert_error("Unowned agents/ item: .shared")

    def test_escaping_symlink_rejected(self):
        (self.case / "escape").symlink_to(self.root / "README.md")
        self.assert_error("resource resolves outside its case")

    def test_unsupported_readiness_rejected(self):
        path = self.case / "README.md"
        path.write_text(path.read_text().replace("Status: planned", "Status: demo-ready"))
        self.assert_error("README and SPEC Status disagree")
        self.assert_error("requires a recorded passed Verification result")

    def test_recorded_readiness_fields(self):
        self.recorded_ready_fixture()
        self.assertEqual(audit(self.root), [])

    def test_blank_metadata_does_not_consume_next_line(self):
        self.assertEqual(metadata("Runtime: \t\n\n## Purpose\n", "Runtime"), "")
        self.assertIsNone(metadata("## Purpose\n", "Runtime"))
        self.assertEqual(metadata("Runtime: Python 3.9+\n", "Runtime"), "Python 3.9+")

    def test_blank_runtime_rejected(self):
        for name in ("README.md", "SPEC.md"):
            path = self.case / name
            path.write_text(path.read_text().replace("Runtime: undecided", "Runtime:"))
        self.assert_error("README.md must state its Runtime")
        self.assert_error("SPEC.md must state its Runtime")

    def test_blank_verification_fields_rejected(self):
        self.recorded_ready_fixture()
        path = self.case / "README.md"
        text = path.read_text().replace("Verification command: python3 -m unittest", "Verification command:")
        text = text.replace("Verified scope: Synthetic metadata; no execution claim", "Verified scope:")
        path.write_text(text)
        self.assert_error("requires a recorded Verification command")
        self.assert_error("requires a recorded Verified scope")


if __name__ == "__main__":
    unittest.main()
