"""Drive both the installed entry point and module CLI on their real surface."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from self_improving import ScenarioError
from self_improving.__main__ import main


class CLITests(unittest.TestCase):
    def test_every_cli_scenario_has_the_expected_terminal_outcome(self):
        expected = {"improvement": "review_required", "regression": "rejected_regression",
                    "insufficient": "no_proposal_insufficient", "poisoned": "no_proposal_insufficient",
                    "development-rejection": "rejected_development", "no-gain": "rejected_no_gain"}
        executable = str(Path(sys.executable).with_name("self-improving-agent"))
        for scenario, status in expected.items():
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                result = subprocess.run([executable, "--scenario", scenario], cwd=directory,
                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                report = json.loads(result.stdout)
                self.assertEqual(report["status"], status)
                self.assertEqual(report["serving_version_id"], report["baseline"]["version_id"])
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_module_cli_and_argument_errors(self):
        result = subprocess.run([sys.executable, "-m", "self_improving", "--scenario", "improvement"],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "review_required")
        for args in ([], ["--scenario", "unknown"], ["--scenario", "../../outside"],
                     ["--scenario", "improvement", "--activate"]):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, "-m", "self_improving", *args],
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("error:", result.stderr)

    def test_fixture_errors_emit_no_completed_report(self):
        stdout, stderr = StringIO(), StringIO()
        with patch("self_improving.__main__.load_scenario", side_effect=ScenarioError("bad host fixture")):
            with redirect_stdout(stdout), redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
                main(["--scenario", "improvement"])
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("bad host fixture", stderr.getvalue())

    def test_broken_stdout_is_an_error(self):
        with patch("builtins.print", side_effect=BrokenPipeError):
            self.assertEqual(main(["--scenario", "improvement"]), 1)

    def test_closed_stdout_pipe_is_a_nonzero_io_exit(self):
        for scenario in ("improvement", "insufficient"):
            with self.subTest(scenario=scenario):
                process = subprocess.Popen([sys.executable, "-m", "self_improving", "--scenario", scenario],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                process.stdout.close()
                self.assertNotEqual(process.wait(timeout=15), 0)
                process.stderr.close()


if __name__ == "__main__":
    unittest.main()
