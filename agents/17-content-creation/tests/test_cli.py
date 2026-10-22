"""CLI contract checks cover stdout reports, sanitized errors, and write failures."""

import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from content_creation.cli import main
from content_creation.domain import FixtureError


class FailingWriter(io.StringIO):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode

    def write(self, text):
        if self.mode == "write":
            raise OSError("PRIVATE_WRITE_DETAIL")
        if self.mode == "short":
            return len(text) - 1
        return super().write(text)

    def flush(self):
        if self.mode == "flush":
            raise BrokenPipeError("PRIVATE_FLUSH_DETAIL")
        return super().flush()


class CliTests(unittest.TestCase):
    def invoke(self, args):
        output, errors = io.StringIO(), io.StringIO()
        status = main(args, stdout=output, stderr=errors)
        return status, output.getvalue(), errors.getvalue()

    def test_all_packaged_scenarios_have_honest_exit_codes(self):
        for scenario, expected in (("launch", 0), ("relaxed", 0), ("exhausted", 1),
                                   ("length-repair", 0), ("impossible-length", 1), ("mixed", 1)):
            with self.subTest(scenario=scenario):
                status, output, errors = self.invoke(["--scenario", scenario])
                self.assertEqual(status, expected)
                self.assertEqual(errors, "")
                report = json.loads(output)
                self.assertEqual(report["status"], "validated" if expected == 0 else "unapproved")
                self.assertEqual(report["approval"], "not_granted")
                self.assertEqual([item["kind"] for item in report["artifacts"]], ["email", "documentation"])

    def test_default_output_is_deterministic(self):
        self.assertEqual(self.invoke([]), self.invoke([]))
        self.assertEqual(self.invoke([]), self.invoke(["--scenario", "launch"]))

    def test_argument_errors_do_not_echo_raw_values(self):
        secret = "PRIVATE_ARGUMENT_VALUE"
        for args in ([secret], ["--scenario", secret], ["--brief", secret],
                     ["--scenario", "launch", "--brief", secret], ["--scen", "launch"]):
            with self.subTest(args=args):
                status, output, errors = self.invoke(args)
                self.assertEqual(status, 2)
                self.assertEqual(output, "")
                self.assertNotIn(secret, errors)
                self.assertLessEqual(len(errors), 200)

    def test_malformed_input_and_fixture_fail_without_a_report(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "PRIVATE_FILENAME.json"
            target.write_text('{"PRIVATE_CONTENT": NaN}')
            status, output, errors = self.invoke(["--brief", str(target)])
            self.assertEqual(status, 2)
            self.assertEqual(output, "")
            self.assertNotIn("PRIVATE", errors)
        with patch("content_creation.cli.create_content", side_effect=FixtureError("Packaged content fixture is invalid.")):
            status, output, errors = self.invoke([])
            self.assertEqual(status, 2)
            self.assertEqual(output, "")
            self.assertIn("fixture", errors)

    def test_output_write_short_write_and_flush_failure_are_exit_two(self):
        for mode in ("write", "short", "flush"):
            output, errors = FailingWriter(mode), io.StringIO()
            with self.subTest(mode=mode):
                self.assertEqual(main([], stdout=output, stderr=errors), 2)
                self.assertIn("Unable to write", errors.getvalue())
                self.assertNotIn("PRIVATE", errors.getvalue())

    def test_interrupt_is_not_success(self):
        with patch("content_creation.cli.create_content", side_effect=KeyboardInterrupt):
            status, output, errors = self.invoke([])
            self.assertEqual(status, 130)
            self.assertEqual(output, "")
            self.assertIn("Interrupted", errors)

    def test_failed_stderr_does_not_hide_invalid_input_exit(self):
        self.assertEqual(main(["--unknown"], stdout=io.StringIO(), stderr=FailingWriter("write")), 2)

    def test_real_module_cli_from_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-m", "content_creation", "--scenario", "launch"],
                                    cwd=directory, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout)["status"], "validated")


if __name__ == "__main__":
    unittest.main()
