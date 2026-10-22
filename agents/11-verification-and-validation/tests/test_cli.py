"""Exercise real subprocess CLI output/exits and POSIX file boundaries.

Subprocesses occur only in this development test harness. Source-error subprocess
checks substitute a private test path without adding runtime CLI authority.
"""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from verification_agent import InputError, SourceError, verify_document
from verification_agent import cli, verifier
from verification_agent.files import read_regular
from test_verifier import ROOT, RAW_SNAPSHOT, document


class CLITests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run([sys.executable, "-m", "verification_agent.cli", *map(str, arguments)],
                              capture_output=True, text=True, timeout=5)

    def test_actual_cli_complete_success_and_no_input_writes(self):
        fixture = ROOT / "fixtures/claims.json"
        before = fixture.read_bytes()
        completed = self.run_cli(fixture)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, "")
        report = json.loads(completed.stdout)
        self.assertFalse(report["review_required"])
        self.assertEqual(len(report["results"]), 4)
        self.assertEqual(fixture.read_bytes(), before)
        self.assertEqual(completed.stdout, self.run_cli(fixture).stdout)

    def test_unfavorable_report_still_exits_zero(self):
        completed = self.run_cli(ROOT / "fixtures/scenarios/mixed.json")
        self.assertEqual(completed.returncode, 0)
        report = json.loads(completed.stdout)
        self.assertTrue(report["review_required"])
        self.assertEqual([item["verdict"] for item in report["results"]], ["confirmed", "mostly_true", "contradicted", "unverified"])

    def test_syntax_errors_are_sanitized_and_emit_no_report(self):
        for arguments in [(), ("--truth",), ("--truth", "/secret/path"), ("one", "two"), ("-",)]:
            with self.subTest(arguments=arguments):
                completed = self.run_cli(*arguments)
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertEqual(completed.stderr, "input_error:invalid_arguments\n")

    def test_help(self):
        completed = self.run_cli("--help")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("verification-agent FILE", completed.stdout)
        self.assertEqual(completed.stderr, "")

    def test_invalid_input_errors_are_atomic_and_do_not_echo_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private-secret-input.json"
            for payload in [b"private-secret-payload", document().replace(b'"-5"', b'"oops"'),
                            b"[" * 3000 + b"]" * 3000, b" " * 65_537]:
                path.write_bytes(payload)
                completed = self.run_cli(path)
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertTrue(completed.stderr.startswith("input_error:"))
                self.assertNotIn(directory, completed.stderr)
                self.assertNotIn("private-secret", completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)

    def test_missing_input(self):
        completed = self.run_cli(ROOT / "missing-secret.json")
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(completed.stderr, "input_error:unreadable_file\n")

    def test_input_directory_symlink_fifo_and_device_fail_promptly(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            regular = folder / "regular.json"
            regular.write_bytes(document())
            symlink, fifo = folder / "symlink", folder / "fifo"
            symlink.symlink_to(regular)
            os.mkfifo(fifo)
            for path in (folder, symlink, fifo, Path("/dev/null")):
                with self.subTest(path=path.name):
                    completed = self.run_cli(path)
                    self.assertEqual(completed.returncode, 2)
                    self.assertEqual(completed.stdout, "")
                    self.assertNotIn("Traceback", completed.stderr)

    def test_source_errors_exit_three_in_real_process(self):
        code = "from pathlib import Path; import sys; from verification_agent import verifier, cli; verifier._SNAPSHOT_PATH=Path(sys.argv[1]); raise SystemExit(cli.main([sys.argv[2]]))"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private-source.json"
            request = Path(directory) / "request.json"
            request.write_bytes(document())
            for payload in [b"secret corrupt source", b" " * 262_145, None]:
                if payload is None:
                    path.unlink()
                else:
                    path.write_bytes(payload)
                completed = subprocess.run([sys.executable, "-c", code, str(path), str(request)], capture_output=True, text=True, timeout=5)
                self.assertEqual(completed.returncode, 3)
                self.assertEqual(completed.stdout, "")
                self.assertTrue(completed.stderr.startswith("source_error:"))
                self.assertNotIn(directory, completed.stderr)
                self.assertNotIn("secret", completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)

    def test_interruption_before_output_returns_130(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), patch.object(cli, "read_regular", side_effect=KeyboardInterrupt):
            status = cli.main(["request.json"])
        self.assertEqual(status, 130)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "interrupted\n")

    def test_broken_pipe_returns_one_without_traceback(self):
        class BrokenOutput:
            def write(self, _value):
                raise BrokenPipeError()
        err = io.StringIO()
        with patch.object(cli.sys, "stdout", BrokenOutput()), redirect_stderr(err):
            status = cli.main([str(ROOT / "fixtures/claims.json")])
        self.assertEqual(status, 1)
        self.assertEqual(err.getvalue(), "")

    def test_real_closed_output_pipe_exits_one(self):
        reader, writer = os.pipe()
        os.close(reader)
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "verification_agent.cli", str(ROOT / "fixtures/claims.json")],
                stdout=writer, stderr=subprocess.PIPE, text=True, timeout=5,
            )
        finally:
            os.close(writer)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stderr, "")


class FileBoundaryTests(unittest.TestCase):
    def test_source_directory_symlink_and_fifo_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            regular = folder / "regular.json"
            regular.write_bytes(RAW_SNAPSHOT)
            symlink, fifo = folder / "symlink", folder / "fifo"
            symlink.symlink_to(regular)
            os.mkfifo(fifo)
            for path in (folder, symlink, fifo):
                with self.subTest(path=path.name), patch.object(verifier, "_SNAPSHOT_PATH", path), self.assertRaises(SourceError):
                    verify_document(document())

    def test_unreadable_error_mapping(self):
        for error in (InputError, SourceError):
            with self.subTest(error=error), patch("verification_agent.files.os.open", side_effect=PermissionError), self.assertRaises(error) as caught:
                read_regular("secret-file", 100, error)
            self.assertEqual(caught.exception.code, "unreadable_file")

    def test_nul_filename_is_sanitized(self):
        with self.assertRaises(InputError) as caught:
            read_regular("bad\0name", 100, InputError)
        self.assertEqual(caught.exception.code, "unreadable_file")

    def test_bound_holds_when_size_metadata_is_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "growing.json"
            path.write_bytes(b"x" * 101)
            metadata = path.stat()
            stale = os.stat_result((metadata.st_mode, metadata.st_ino, metadata.st_dev, metadata.st_nlink,
                                    metadata.st_uid, metadata.st_gid, 0, metadata.st_atime, metadata.st_mtime, metadata.st_ctime))
            with patch("verification_agent.files.os.fstat", return_value=stale), self.assertRaises(InputError) as caught:
                read_regular(path, 100, InputError)
            self.assertEqual(caught.exception.code, "too_large")

    def test_read_failure_closes_descriptor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "file.json"
            path.write_bytes(document())
            real_close = os.close
            with patch("verification_agent.files.os.close", wraps=real_close) as close, patch("verification_agent.files.os.read", side_effect=OSError), self.assertRaises(InputError):
                read_regular(path, 65_536, InputError)
            close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
