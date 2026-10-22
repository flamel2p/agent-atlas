"""Actual CLI process evidence, including nonzero terminal and input outcomes."""

import json
import subprocess
import sys

from support import WorkspaceTest


class CliTests(WorkspaceTest):
    def command(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "code_generation_agent.cli", "--workspace", str(self.workspace), *arguments],
            capture_output=True, text=True, timeout=10, check=False,
        )

    def test_scenario_exit_codes_and_reports_agree(self):
        for scenario, status, code in (("repair", "completed", 0), ("exhaustion", "exhausted", 3),
                                       ("policy-rejection", "exhausted", 3), ("syntax-error", "exhausted", 3)):
            with self.subTest(scenario=scenario):
                process = self.command("--scenario", scenario)
                self.assertEqual(process.returncode, code, process.stderr)
                result = json.loads(process.stdout)
                self.assertEqual(result["status"], status)
                self.assertEqual(result["mode"], "fixture")
                self.assertEqual(result["accepted_source"] is not None, code == 0)

    def test_invalid_cli_input_is_distinct_and_writes_nothing(self):
        for arguments in (("--max-attempts", "4"), ("--scenario", "unknown")):
            with self.subTest(arguments=arguments):
                process = self.command(*arguments)
                self.assertEqual(process.returncode, 2)
        self.assertFalse((self.workspace / "artifacts").exists())
        (self.workspace / "SPEC.md").write_text("Slug: other\n")
        process = self.command()
        self.assertEqual(process.returncode, 2)
        self.assertEqual(json.loads(process.stdout)["status"], "invalid_input")
