"""Refinement, retained evidence, authority boundaries and terminal failures."""

from dataclasses import asdict, FrozenInstanceError
import json
from pathlib import Path
from unittest.mock import Mock, patch

from code_generation_agent.artifacts import ArtifactError, ArtifactStore, InvalidInput, validate_workspace
from code_generation_agent.developer import FixtureDeveloper
from code_generation_agent.domain import Feedback, ORACLE_DIGEST, SPECIFICATION, Status, digest
from code_generation_agent.interpreter import check_candidate
from code_generation_agent.runner import run
from support import WorkspaceTest, fixture


class RunnerTests(WorkspaceTest):
    def persisted(self, result):
        return json.loads(Path(result.report_path).read_text(encoding="utf-8"))

    def test_repair_uses_failures_and_publishes_only_attempt_source(self):
        result = run(workspace=self.workspace)
        self.assertEqual((result.status, result.attempt_count), (Status.COMPLETED, 2))
        self.assertEqual(result.oracle_digest, ORACLE_DIGEST)
        self.assertEqual(result.accepted_source, "attempt-2/candidate.txt")
        report = self.persisted(result)
        self.assertEqual(report, json.loads(json.dumps(asdict(result))))
        self.assertEqual(result.attempts[1].prior_feedback, (result.attempts[0].feedback,))
        directory = Path(result.run_directory)
        self.assertEqual(sorted(path.name for path in directory.iterdir()), ["attempt-1", "attempt-2", "report.json"])
        for attempt in result.attempts:
            source = (directory / attempt.source_artifact).read_text(encoding="utf-8")
            self.assertEqual(digest(source), attempt.source_digest)
            self.assertTrue((directory / f"attempt-{attempt.number}" / "feedback.json").exists())
        self.assertTrue(result.attempts[-1].feedback.passed)
        with self.assertRaises(FrozenInstanceError):
            result.attempts[-1].feedback.tests[0].expected = 99

    def test_developer_does_not_repair_without_qualifying_feedback(self):
        developer = FixtureDeveloper("repair")
        bad = fixture("threshold_bug.txt")
        for _ in range(4):
            self.assertEqual(developer.propose(SPECIFICATION, ()), bad)
        for feedback in ((Feedback("syntax", "invalid_syntax"),), (check_candidate(fixture()),)):
            self.assertEqual(developer.propose(SPECIFICATION, feedback), bad)
        self.assertEqual(developer.propose(SPECIFICATION, (check_candidate(bad),)), fixture())
        with self.assertRaises(ValueError):
            developer.propose("changed tests", ())

    def test_exhaustion_caps_and_policy_syntax_failures(self):
        for scenario in ("exhaustion", "policy-rejection", "syntax-error"):
            for cap in (1, 2, 3):
                with self.subTest(scenario=scenario, cap=cap):
                    result = run(scenario, cap, workspace=self.workspace)
                    self.assertEqual((result.status, result.attempt_count), (Status.EXHAUSTED, cap))
                    self.assertEqual(len(result.attempts), cap)
                    self.assertIsNone(self.persisted(result)["accepted_source"])
                    self.assertTrue(all((Path(result.run_directory) / attempt.source_artifact).exists() for attempt in result.attempts))
        result = run("repair", 1, workspace=self.workspace)
        self.assertEqual(result.status, Status.EXHAUSTED)

    def test_each_run_owns_its_history_and_artifacts(self):
        first = run(workspace=self.workspace)
        second = run(workspace=self.workspace)
        self.assertNotEqual(first.run_directory, second.run_directory)
        self.assertEqual(first.attempts, second.attempts)
        self.assertEqual(second.attempts[0].prior_feedback, ())

    def test_invalid_calls_precede_proposals_and_artifacts(self):
        developer = Mock()
        for cap in (True, False, 0, 4, 1.5, "2"):
            with self.subTest(cap=cap), self.assertRaises(InvalidInput):
                run(max_attempts=cap, workspace=self.workspace, developer=developer)
        for scenario in (None, 1, "unknown"):
            with self.subTest(scenario=scenario), self.assertRaises(InvalidInput):
                run(scenario, workspace=self.workspace, developer=developer)
        developer.propose.assert_not_called()
        self.assertFalse((self.workspace / "artifacts").exists())

    def test_invalid_proposals_are_bounded_metadata_not_accepted_sources(self):
        for candidate, code in ((None, "source_type"), ("x" * 2049, "source_size"), ("é" * 1025, "source_size"), ("\ud800", "source_encoding")):
            with self.subTest(code=code):
                result = run(workspace=self.workspace, developer=Mock(propose=Mock(return_value=candidate)))
                self.assertEqual((result.status, result.attempt_count), (Status.FAILED, 1))
                self.assertIsNone(result.accepted_source)
                self.assertEqual(result.attempts[0].feedback.error, code)
                self.assertIsNone(result.attempts[0].source_digest)
                self.assertIsNone(result.attempts[0].source_artifact)
                self.assertEqual(list((Path(result.run_directory) / "attempt-1").iterdir()), [Path(result.run_directory) / "attempt-1" / "feedback.json"])

    def test_developer_failure_and_cancellation_keep_completed_attempts(self):
        for error, status in ((RuntimeError("secret not logged"), Status.FAILED), (KeyboardInterrupt(), Status.CANCELLED)):
            with self.subTest(status=status):
                developer = Mock(propose=Mock(side_effect=[fixture("threshold_bug.txt"), error]))
                result = run(workspace=self.workspace, developer=developer)
                self.assertEqual((result.status, result.attempt_count), (status, 2))
                self.assertEqual(len(result.attempts), 2)
                self.assertIsNone(result.accepted_source)
                self.assertTrue((Path(result.run_directory) / "attempt-1" / "candidate.txt").exists())
                self.assertNotIn("secret", Path(result.report_path).read_text())

    def test_artifact_failure_keeps_previous_records_and_never_selects_source(self):
        record = ArtifactStore.record
        def fail_second(store, attempt, source):
            if attempt.number == 2:
                raise ArtifactError("disk full private detail")
            record(store, attempt, source)
        with patch.object(ArtifactStore, "record", fail_second):
            result = run(workspace=self.workspace)
        self.assertEqual(result.status, Status.FAILED)
        self.assertEqual(len(result.attempts), 1)
        self.assertIsNone(self.persisted(result)["accepted_source"])
        self.assertTrue((Path(result.run_directory) / "attempt-1" / "feedback.json").exists())

    def test_report_failure_leaves_no_success_authority(self):
        with patch("code_generation_agent.artifacts.os.link", side_effect=OSError("private detail")):
            result = run(workspace=self.workspace)
        self.assertEqual(result.status, Status.FAILED)
        self.assertIsNone(result.report_path)
        self.assertIsNone(result.accepted_source)
        directory = Path(result.run_directory)
        self.assertFalse((directory / "report.json").exists())
        self.assertTrue((directory / "attempt-2" / "candidate.txt").exists())

    def test_write_failure_and_cancellation_during_attempt_are_terminal(self):
        write = ArtifactStore._write
        for error, status in ((OSError("disk full"), Status.FAILED), (KeyboardInterrupt(), Status.CANCELLED)):
            def fail_candidate(path, data):
                if path.name == "candidate.txt":
                    raise error
                write(path, data)
            with self.subTest(status=status), patch.object(ArtifactStore, "_write", staticmethod(fail_candidate)):
                result = run(workspace=self.workspace)
            self.assertEqual(result.status, status)
            self.assertEqual(result.attempt_count, 1)
            self.assertEqual(result.attempts, ())
            self.assertIsNone(self.persisted(result)["accepted_source"])

    def test_report_temporary_write_failure_is_not_publication(self):
        write = ArtifactStore._write
        def fail_temporary(path, data):
            if path.name == ".report.tmp":
                raise OSError("private disk error")
            write(path, data)
        with patch.object(ArtifactStore, "_write", staticmethod(fail_temporary)):
            result = run(workspace=self.workspace)
        self.assertEqual(result.status, Status.FAILED)
        self.assertIsNone(result.report_path)
        self.assertIsNone(result.accepted_source)
        self.assertFalse((Path(result.run_directory) / "report.json").exists())

    def test_unreportable_cancellation_remains_cancelled_and_unpublished(self):
        with patch("code_generation_agent.artifacts.os.link", side_effect=KeyboardInterrupt()):
            result = run(workspace=self.workspace)
        self.assertEqual(result.status, Status.CANCELLED)
        self.assertIsNone(result.report_path)
        self.assertIsNone(result.accepted_source)
        self.assertFalse((Path(result.run_directory) / "report.json").exists())

    def test_interruption_before_publication_reports_cancelled(self):
        import os
        link = os.link
        calls = 0
        def interrupt_once(source, destination):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise KeyboardInterrupt()
            link(source, destination)
        with patch("code_generation_agent.artifacts.os.link", interrupt_once):
            result = run(workspace=self.workspace)
        self.assertEqual(result.status, Status.CANCELLED)
        self.assertIsNone(self.persisted(result)["accepted_source"])

    def test_interruption_after_atomic_link_preserves_completed_report(self):
        import os
        link = os.link
        def interrupt_after_link(source, destination):
            link(source, destination)
            raise KeyboardInterrupt()
        with patch("code_generation_agent.artifacts.os.link", interrupt_after_link):
            result = run(workspace=self.workspace)
        self.assertEqual(result.status, Status.COMPLETED)
        self.assertEqual(self.persisted(result)["status"], "completed")
        self.assertEqual(self.persisted(result)["accepted_source"], result.accepted_source)

    def test_interruption_after_cancellation_publication_keeps_report_path(self):
        import os
        link = os.link
        calls = 0
        def interrupt_before_then_after(source, destination):
            nonlocal calls
            calls += 1
            if calls > 1:
                link(source, destination)
            raise KeyboardInterrupt()
        with patch("code_generation_agent.artifacts.os.link", interrupt_before_then_after):
            result = run(workspace=self.workspace)
        self.assertEqual(result.status, Status.CANCELLED)
        self.assertEqual(self.persisted(result)["status"], "cancelled")
        self.assertIsNone(result.accepted_source)

    def test_artifact_creation_error_returns_unpublished_failure(self):
        with patch.object(ArtifactStore, "__init__", side_effect=ArtifactError("no space")):
            result = run(workspace=self.workspace)
        self.assertEqual((result.status, result.attempt_count), (Status.FAILED, 0))
        self.assertIsNone(result.report_path)
        self.assertIsNone(result.run_directory)

    def test_existing_runs_and_escape_paths_are_refused(self):
        first = run(workspace=self.workspace, run_id="fixed")
        original = Path(first.report_path).read_bytes()
        with self.assertRaises(InvalidInput):
            run(workspace=self.workspace, run_id="fixed")
        self.assertEqual(Path(first.report_path).read_bytes(), original)
        for name in ("../escape", "/escape", "a/b", "", ".", "..", True, "a" * 65):
            with self.subTest(name=name), self.assertRaises(InvalidInput):
                run(workspace=self.workspace, run_id=name)

    def test_workspace_markers_and_symlinks_cannot_redirect_writes(self):
        (self.workspace / "SPEC.md").write_text("Slug: sibling\n")
        with self.assertRaises(InvalidInput):
            run(workspace=self.workspace)
        (self.workspace / "SPEC.md").write_text("Slug: 13-code-generation\n")
        (self.workspace / "pyproject.toml").write_text('[project]\nname = "sibling"\n')
        with self.assertRaises(InvalidInput):
            validate_workspace(self.workspace)
        (self.workspace / "pyproject.toml").write_text('[project]\nname = "agent-atlas-13-code-generation"\n')
        alias = self.workspace / "alias"
        alias.symlink_to(self.workspace, target_is_directory=True)
        for workspace in (alias, alias / "alias"):
            with self.subTest(workspace=workspace), self.assertRaises(InvalidInput):
                validate_workspace(workspace)
        (self.workspace / "artifacts").symlink_to(self.workspace, target_is_directory=True)
        with self.assertRaises(InvalidInput):
            run(workspace=self.workspace)
        self.assertFalse((self.workspace / "report.json").exists())

    def test_symlink_parent_traversal_is_rejected_before_proposals_or_writes(self):
        normalized = self.workspace / "selected"
        resolved = self.workspace / "elsewhere" / "selected"
        child = self.workspace / "elsewhere" / "child"
        child.mkdir(parents=True)
        for workspace in (normalized, resolved):
            workspace.mkdir()
            for marker in ("SPEC.md", "pyproject.toml"):
                (workspace / marker).write_bytes((self.workspace / marker).read_bytes())
        shortcut = self.workspace / "shortcut"
        shortcut.symlink_to(child, target_is_directory=True)
        supplied = shortcut / ".." / "selected"
        self.assertEqual(supplied.resolve(), resolved)
        developer = Mock(propose=Mock(return_value=fixture()))
        with self.assertRaisesRegex(InvalidInput, "^workspace_escape$"):
            run(workspace=supplied, developer=developer)
        developer.propose.assert_not_called()
        for workspace in (normalized, resolved):
            self.assertFalse((workspace / "artifacts").exists())

    def test_plain_parent_traversal_is_rejected_before_proposals_or_writes(self):
        child = self.workspace / "child"
        child.mkdir()
        developer = Mock(propose=Mock(return_value=fixture()))
        with self.assertRaisesRegex(InvalidInput, "^workspace_escape$"):
            run(workspace=child / "..", developer=developer)
        developer.propose.assert_not_called()
        self.assertFalse((self.workspace / "artifacts").exists())

    def test_symlink_markers_and_existing_report_cannot_be_overwritten(self):
        marker = self.workspace / "SPEC.md"
        target = self.workspace / "actual-spec"
        marker.rename(target)
        marker.symlink_to(target)
        with self.assertRaises(InvalidInput):
            validate_workspace(self.workspace)
        marker.unlink()
        target.rename(marker)
        publish = ArtifactStore.publish
        def conflicting_report(store, result):
            (store.directory / "report.json").write_text("untouched")
            publish(store, result)
        with patch.object(ArtifactStore, "publish", conflicting_report):
            result = run(workspace=self.workspace)
        self.assertEqual(result.status, Status.FAILED)
        self.assertIsNone(result.report_path)
        self.assertEqual((Path(result.run_directory) / "report.json").read_text(), "untouched")
