"""Drive real CLI processes, then inject boundary failures that need controlled streams."""

import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from compliance_agent.cli import main


class CliTests(unittest.TestCase):
    def invoke(self, *args, source=b"", cwd=None):
        process = subprocess.run(
            [sys.executable, "-m", "compliance_agent", *args], input=source,
            capture_output=True, cwd=cwd, timeout=10,
        )
        self.assertEqual(process.stderr, b"")
        self.assertEqual(len(process.stdout.splitlines()), 1)
        return process, json.loads(process.stdout)

    def test_all_packaged_scenarios_match_status_and_exit_contract(self):
        expected = {
            "clean": ("passed", 0), "blocked": ("blocked", 1),
            "alias": ("blocked", 1), "ambiguous": ("review_required", 2),
            "mixed": ("blocked", 1), "reassigned": ("blocked", 1),
            "unsupported": ("review_required", 2), "masking": ("review_required", 2),
            "prior-block": ("blocked", 1), "syntax-error": ("review_required", 2),
        }
        process, listing = self.invoke("--list-scenarios")
        self.assertEqual(process.returncode, 0)
        self.assertEqual(set(listing["scenarios"]), set(expected))
        for name, outcome in expected.items():
            with self.subTest(name=name):
                process, report = self.invoke("--scenario", name)
                self.assertEqual((report["status"], process.returncode), outcome)

    def test_stdin_reports_repeated_exact_snapshots_deterministically(self):
        source = b'a: Sensitive = "CLI_CANARY"\nlogger.info(a)'
        first, first_record = self.invoke("--stdin", source=source)
        second, _ = self.invoke("--stdin", source=source)
        self.assertEqual(first.returncode, 1)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first_record["status"], "blocked")
        self.assertNotIn(b"CLI_CANARY", first.stdout)

    def test_cli_oversized_source_never_hashes_its_prefix(self):
        process, report = self.invoke("--stdin", source=b"#" + b"x" * 20000)
        self.assertEqual(process.returncode, 2)
        self.assertFalse(report["input_complete"])
        self.assertIsNone(report["source_sha256"])
        self.assertEqual(report["findings"][0]["reason"], "source_size_limit")

    def test_parser_warnings_do_not_escape_to_stderr(self):
        outputs = []
        for setting in ("default", "always", "error"):
            with self.subTest(warning_filter=setting):
                process = subprocess.run(
                    [sys.executable, "-m", "compliance_agent", "--stdin"],
                    input=b'logger.info("PRIVATE_LITERAL\\q")', capture_output=True,
                    env={**os.environ, "PYTHONWARNINGS": setting}, timeout=10,
                )
                self.assertEqual(process.returncode, 0)
                self.assertEqual(process.stderr, b"")
                self.assertEqual(json.loads(process.stdout)["status"], "passed")
                self.assertNotIn(b"PRIVATE_LITERAL", process.stdout)
                outputs.append(process.stdout)
        self.assertEqual(len(set(outputs)), 1)

    def test_invalid_usage_is_a_source_free_json_failure(self):
        for args in ((), ("--scenario",), ("--scenario", "PRIVATE_ARGUMENT"),
                     ("--stdin", "--scenario", "clean"), ("--list-scenarios", "--stdin"),
                     ("--scenario", "../../PRIVATE_PATH"), ("--PRIVATE_FLAG",)):
            with self.subTest(args=args):
                process, report = self.invoke(*args)
                self.assertEqual(process.returncode, 3)
                self.assertEqual(report["status"], "failed")
                self.assertEqual(report["error"]["code"], "invalid_usage")
                self.assertNotIn("policy", report)
                self.assertNotIn("PRIVATE", process.stdout.decode())

    def test_actual_source_execution_canary_has_no_file_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            canary = Path(directory) / "EXECUTION_CANARY"
            source = f'__import__("pathlib").Path({str(canary)!r}).write_text("executed")'.encode()
            process, report = self.invoke("--stdin", source=source, cwd=directory)
            self.assertEqual(process.returncode, 2)
            self.assertEqual(report["status"], "review_required")
            self.assertFalse(canary.exists())
            self.assertNotIn(str(canary), process.stdout.decode())

    def test_input_read_failure_and_interrupt_emit_no_partial_policy_record(self):
        for error, expected_code, exit_code in ((OSError("PRIVATE_READ_ERROR"), "input_read_failed", 3), (KeyboardInterrupt(), "cancelled", 130)):
            stream = unittest.mock.Mock()
            stream.read.side_effect = error
            output = io.StringIO()
            with self.subTest(error=type(error).__name__):
                self.assertEqual(main(["--stdin"], stdin=stream, stdout=output), exit_code)
                report = json.loads(output.getvalue())
                self.assertEqual(report["status"], "failed")
                self.assertEqual(report["error"]["code"], expected_code)
                self.assertNotIn("policy", report)
                self.assertNotIn("PRIVATE_READ_ERROR", output.getvalue())

    def test_policy_rejection_precedes_source_read(self):
        stdin = unittest.mock.Mock()
        output = io.StringIO()
        with patch("compliance_agent.cli._resource", return_value=b'{"scope":"PRIVATE_POLICY"}'):
            code = main(["--stdin"], stdin=stdin, stdout=output)
        self.assertEqual(code, 3)
        stdin.read.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["error"]["code"], "policy_invalid")
        self.assertNotIn("PRIVATE_POLICY", output.getvalue())

    def test_bounded_stdin_read_consumes_only_limit_plus_one(self):
        stream = io.BytesIO(b"#" + b"x" * 30000)
        output = io.StringIO()
        self.assertEqual(main(["--stdin"], stdin=stream, stdout=output), 2)
        self.assertEqual(stream.tell(), 16385)

    def test_resource_reads_are_bounded_for_policy_and_scenario(self):
        policy_stream = unittest.mock.MagicMock()
        policy_stream.__enter__.return_value.read.return_value = b" " * 4097
        resource = unittest.mock.Mock()
        resource.joinpath.return_value.open.return_value = policy_stream
        output = io.StringIO()
        with patch("compliance_agent.cli.files", return_value=resource):
            code = main(["--scenario", "clean"], stdout=output)
        self.assertEqual(code, 3)
        policy_stream.__enter__.return_value.read.assert_called_once_with(4097)

        from compliance_agent.cli import _resource
        with patch("compliance_agent.cli.files", return_value=resource):
            _resource("scenarios/clean.py.txt", 16384, "scenario_unavailable")
        self.assertEqual(policy_stream.__enter__.return_value.read.call_args.args, (16385,))

    def test_missing_policy_and_unexpected_operational_errors_are_source_free(self):
        for failure, expected in ((OSError("PRIVATE_PATH"), "policy_unavailable"), (RuntimeError("PRIVATE_INTERNAL"), "operational_failure")):
            output = io.StringIO()
            with patch("compliance_agent.cli.files", side_effect=failure):
                code = main(["--stdin"], stdin=io.BytesIO(b""), stdout=output)
            self.assertEqual(code, 3)
            self.assertEqual(json.loads(output.getvalue())["error"]["code"], expected)
            self.assertNotIn("PRIVATE", output.getvalue())

    def test_output_write_failure_returns_nonzero_without_retry(self):
        output = unittest.mock.Mock()
        output.write.side_effect = BrokenPipeError("PRIVATE_OUTPUT")
        self.assertEqual(main(["--list-scenarios"], stdout=output), 3)
        output.write.assert_called_once()

    def test_actual_broken_stdout_exits_without_shutdown_traceback(self):
        process = subprocess.Popen([sys.executable, "-m", "compliance_agent", "--list-scenarios"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.stdout.close()
        try:
            self.assertEqual(process.wait(timeout=10), 3)
            self.assertEqual(process.stderr.read(), b"")
        finally:
            process.stderr.close()
            if process.poll() is None:
                process.kill()
                process.wait()

    @unittest.skipUnless(os.name == "posix", "Uses a POSIX closed descriptor")
    def test_actual_closed_stdin_produces_input_read_failure(self):
        process = subprocess.run(
            [sys.executable, "-m", "compliance_agent", "--stdin"],
            preexec_fn=lambda: os.close(0), capture_output=True, timeout=10,
        )
        self.assertEqual(process.returncode, 3)
        self.assertEqual(process.stderr, b"")
        report = json.loads(process.stdout)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["error"]["code"], "input_read_failed")

    @unittest.skipUnless(os.name == "posix", "Uses a POSIX interrupt signal")
    def test_actual_interrupt_during_stdin_read_exits_130(self):
        process = subprocess.Popen([sys.executable, "-m", "compliance_agent", "--stdin"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            # Leave stdin open so the real command waits for the complete snapshot.
            # The delay allows the interpreter to install its normal SIGINT handler.
            time.sleep(0.2)
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        self.assertEqual(process.returncode, 130)
        self.assertEqual(stderr, b"")
        report = json.loads(stdout)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["error"]["code"], "cancelled")
        self.assertNotIn("coverage", report)


if __name__ == "__main__":
    unittest.main()
