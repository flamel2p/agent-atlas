"""Real CLI checks plus fault injection for interruption and descriptor races."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from general_problem_solver import cli
from test_domain import example


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "general_problem_solver", *args], capture_output=True, text=True, timeout=5)

    def test_every_packaged_example_and_exit_code(self):
        for name in cli.EXAMPLES:
            with self.subTest(name=name):
                result = self.run_cli("--example", name)
                report = json.loads(result.stdout)
                expected = 0 if name in ("revision", "already-valid", "dependency") else 1
                self.assertEqual(result.returncode, expected)
                self.assertEqual(result.stderr, "")
                self.assertEqual(report["status"], "solved" if expected == 0 else "unsolved")

    def test_output_bytes_are_repeatable(self):
        first = self.run_cli("--example", "revision")
        second = self.run_cli("--example", "revision")
        self.assertEqual(first.stdout, second.stdout)

    def test_closed_output_pipe_exits_cleanly_with_io_error(self):
        arguments = [("--example", name) for name in cli.EXAMPLES] + [("--help",)]
        for args in arguments:
            with self.subTest(args=args):
                reader, writer = os.pipe()
                # Close before launch so child scheduling cannot hide the failure.
                os.close(reader)
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "general_problem_solver", *args],
                        stdout=writer, stderr=subprocess.PIPE, text=True, timeout=5,
                    )
                finally:
                    os.close(writer)
                self.assertEqual(result.returncode, 2)
                self.assertIn("I/O error", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertNotIn("Exception ignored", result.stderr)
                self.assertNotIn("BrokenPipeError", result.stderr)

    def test_read_only_output_descriptor_exits_cleanly_without_changing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "problem.json"
            document = example()
            path.write_bytes(document)
            arguments = [("--example", "already-valid"), ("--example", "impossible"), ("--help",)]
            for args in arguments:
                with self.subTest(args=args), path.open("rb") as output:
                    result = subprocess.run(
                        [sys.executable, "-m", "general_problem_solver", *args],
                        stdout=output, stderr=subprocess.PIPE, text=True, timeout=5,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stderr, "I/O error: could not read input or write output\n")
                    self.assertEqual(path.read_bytes(), document)

    def test_help_and_usage_codes(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--example", result.stdout)
        for args in ((), ("--example", "unknown"), ("--example", "revision", "--input", "x"), ("--example", "revision", "--example", "dependency"), ("--ex", "revision")):
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertNotIn("Traceback", result.stderr)

    def test_custom_file_is_unchanged_and_no_output_file_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "problem.json"
            document = example()
            path.write_bytes(document)
            result = self.run_cli("--input", str(path))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "solved")
            self.assertEqual(path.read_bytes(), document)
            self.assertEqual(tuple(Path(directory).iterdir()), (path,))

    def test_file_errors_have_no_json_input_leak_or_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for document in (b'{"private-value": "SECRET"}', b" " * 65_537, b"\xff"):
                with self.subTest(size=len(document)):
                    path.write_bytes(document)
                    result = self.run_cli("--input", str(path))
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, "")
                    self.assertNotIn("SECRET", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
            for target in (str(Path(directory) / "missing"), directory, "/dev/null"):
                with self.subTest(target=target):
                    result = self.run_cli("--input", target)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, "")

    def test_fifo_is_rejected_without_waiting_for_a_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pipe"
            os.mkfifo(path)
            result = self.run_cli("--input", str(path))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")

    def test_descriptor_type_recheck_rejects_path_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pipe"
            os.mkfifo(path)
            stdout, stderr = StringIO(), StringIO()
            with patch("general_problem_solver.cli.os.stat", return_value=SimpleNamespace(st_mode=stat.S_IFREG)):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = cli.main(["--input", str(path)])
            self.assertEqual(code, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("regular file", stderr.getvalue())

    def test_interruption_has_no_partial_report(self):
        stdout, stderr = StringIO(), StringIO()
        with patch("general_problem_solver.cli.solve_document", side_effect=KeyboardInterrupt):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli.main(["--example", "revision"])
        self.assertEqual(code, 130)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "Interrupted\n")


if __name__ == "__main__":
    unittest.main()
