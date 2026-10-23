"""Drive real subprocesses through file authority, errors, and output failure."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recommendation import cli
from recommendation.documents import ResourceError


class CliTests(unittest.TestCase):
    def run_cli(self, *arguments, cwd=None, **kwargs):
        return subprocess.run(
            [sys.executable, "-m", "recommendation", *arguments], cwd=cwd,
            capture_output=True, timeout=10, **kwargs,
        )

    def assert_invalid_result(self, result):
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        error = json.loads(result.stderr)
        self.assertEqual(error["error"]["code"], "invalid_input")
        self.assertNotIn(b"PRIVATE_SENTINEL", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_default_and_all_scenarios_outside_case_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            normal = self.run_cli(cwd=directory)
            self.assertEqual(normal.returncode, 0)
            self.assertEqual(normal.stderr, b"")
            self.assertEqual(json.loads(normal.stdout)["status"], "personalized")
            for scenario, status in [("normal", "personalized"), ("cold-start", "cold_start"),
                                     ("no-match", "no_match"), ("constrained", "personalized"), ("no-eligible", "empty")]:
                with self.subTest(scenario=scenario):
                    result = self.run_cli("--scenario", scenario, cwd=directory)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stderr, b"")
                    self.assertEqual(json.loads(result.stdout)["status"], status)

    def test_installed_console_command(self):
        command = Path(sys.executable).parent / "recommendation"
        result = subprocess.run([str(command), "--scenario", "cold-start"], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["status"], "cold_start")

    def test_help_succeeds_without_loading_inputs(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        self.assertIn(b"--request", result.stdout)

    def test_selected_file_and_mac_tmp_directory_alias(self):
        profile = {
            "topic_weights": {"python": 1}, "max_duration_minutes": 480,
            "max_difficulty": "advanced", "completed_skills": [],
            "excluded_exercise_ids": [], "limit": 1,
        }
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            path = Path(directory) / "request.json"
            path.write_text(json.dumps(profile), encoding="utf-8")
            result = self.run_cli("--request", str(path))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["recommendations"][0]["id"], "read-files")
            self.assertEqual(sorted(item.name for item in Path(directory).iterdir()), ["request.json"])

    def test_argument_errors_are_sanitized_input_errors(self):
        cases = [
            ["--scenario", "PRIVATE_SENTINEL"], ["--request"], ["--PRIVATE_SENTINEL"],
            ["--request", "/PRIVATE_SENTINEL", "--scenario", "normal"],
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                self.assert_invalid_result(self.run_cli(*arguments))

    def test_malformed_duplicate_nonfinite_oversized_and_deep_json(self):
        examples = [
            b"{PRIVATE_SENTINEL", b'{"topic_weights":{"python":1,"python":2}}',
            b'{"PRIVATE_SENTINEL":NaN}', b'{"PRIVATE_SENTINEL":Infinity}', b'{"PRIVATE_SENTINEL":1e999}',
            b"x" * (256 * 1024 + 1), b"[" * 1000 + b"]" * 1000,
            b"\xff", b'"\\ud800"', b"null", b"[]", b"true", b"",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "PRIVATE_SENTINEL.json"
            for index, raw in enumerate(examples):
                with self.subTest(example=index):
                    path.write_bytes(raw)
                    self.assert_invalid_result(self.run_cli("--request", str(path)))

    def test_exact_file_size_limit_accepts_json_and_next_byte_rejects(self):
        profile = {
            "topic_weights": {}, "max_duration_minutes": 30, "max_difficulty": "beginner",
            "completed_skills": [], "excluded_exercise_ids": [], "limit": 1,
        }
        encoded = json.dumps(profile).encode("utf-8")
        padded = encoded + b" " * (256 * 1024 - len(encoded))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_bytes(padded)
            self.assertEqual(self.run_cli("--request", str(path)).returncode, 0)
            path.write_bytes(padded + b" ")
            self.assert_invalid_result(self.run_cli("--request", str(path)))

    def test_missing_directory_symlink_and_special_file_fail_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regular = root / "regular.json"
            regular.write_text("{}")
            alias = root / "PRIVATE_SENTINEL-link"
            alias.symlink_to(regular)
            pipe = root / "PRIVATE_SENTINEL-fifo"
            os.mkfifo(pipe)
            for path in (root / "PRIVATE_SENTINEL-missing", root, alias, pipe, Path("/dev/null")):
                with self.subTest(path=path):
                    self.assert_invalid_result(self.run_cli("--request", str(path)))

    def test_buffered_and_unbuffered_closed_stdout_are_nonzero_without_traceback(self):
        for unbuffered, arguments in [(False, []), (True, []), (False, ["--help"])]:
            with self.subTest(unbuffered=unbuffered, arguments=arguments):
                read_end, write_end = os.pipe()
                os.close(read_end)
                environment = dict(os.environ)
                if unbuffered:
                    environment["PYTHONUNBUFFERED"] = "1"
                else:
                    environment.pop("PYTHONUNBUFFERED", None)
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "recommendation", *arguments], stdout=write_end,
                        stderr=subprocess.PIPE, timeout=10, env=environment,
                    )
                finally:
                    os.close(write_end)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b"Traceback", result.stderr)
                self.assertNotIn(b"Exception ignored", result.stderr)
                self.assertEqual(json.loads(result.stderr)["error"]["code"], "output_unavailable")

    def test_closed_stderr_preserves_invalid_exit_and_empty_stdout(self):
        read_end, write_end = os.pipe()
        os.close(read_end)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "recommendation", "--PRIVATE_SENTINEL"],
                stdout=subprocess.PIPE, stderr=write_end, timeout=10,
            )
        finally:
            os.close(write_end)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")

    def test_stdout_descriptor_closed_before_python_starts_is_sanitized(self):
        for arguments in ([], ["--help"]):
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments, preexec_fn=lambda: os.close(1))
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"Traceback", result.stderr)
                error = json.loads(result.stderr)
                self.assertEqual(error["error"]["code"], "output_unavailable")

    def test_stderr_descriptor_closed_before_python_starts_preserves_exit(self):
        result = self.run_cli("--PRIVATE_SENTINEL", preexec_fn=lambda: os.close(2))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"")

    def test_resource_io_failure_is_nonzero_and_sanitized(self):
        with patch.object(cli, "read_resource", side_effect=ResourceError("PRIVATE_SENTINEL")):
            with patch.object(cli.sys, "stdout") as stdout, patch.object(cli.sys, "stderr") as stderr:
                self.assertEqual(cli.main([]), 1)
                stdout.write.assert_not_called()
                written = stderr.write.call_args.args[0]
                self.assertEqual(json.loads(written)["error"]["code"], "resource_unavailable")
                self.assertNotIn("PRIVATE_SENTINEL", written)


if __name__ == "__main__":
    unittest.main()
