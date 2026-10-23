"""Exercise the real CLI and descriptor boundaries without external services."""

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

from audio_processing import cli
from audio_processing.assets import AssetError
from audio_processing.core import MAX_INPUT_BYTES, Rejected
from test_audio import make_wav


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    def run_cli(self, *arguments, **options):
        return subprocess.run(
            [sys.executable, "-m", "audio_processing", *arguments],
            cwd=self.directory, env=self.environment,
            capture_output=True, timeout=5, **options,
        )

    def test_real_complaint_emits_one_json_and_writes_no_files(self):
        before = set(self.directory.iterdir())
        result = self.run_cli("--fixture", "complaint")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(len(result.stdout.splitlines()), 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["kind"], "analysis")
        self.assertEqual(report["transcript"]["full_text"], "my parcel is late. please check its status.")
        self.assertEqual(set(self.directory.iterdir()), before)

    def test_real_unknown_input_and_silence_are_successful_unavailable_results(self):
        unknown = self.directory / "unknown.wav"
        unknown.write_bytes(make_wav([1, -1]))
        for arguments, reason in (
            (("--input", str(unknown)), "no_exact_fixture_match"),
            (("--fixture", "silence"), "silent_input"),
        ):
            with self.subTest(reason=reason):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["transcript"], {"kind": "unavailable", "reason": reason})
                self.assertIn("metrics", report)

    def test_real_wav_rejection_does_not_echo_private_path_or_bytes(self):
        path = self.directory / "PRIVATE-CUSTOMER-AUDIO.wav"
        path.write_bytes(b"PRIVATE RAW AUDIO PAYLOAD")
        result = self.run_cli("--input", str(path))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["code"], "invalid_wav")
        self.assertNotIn(b"PRIVATE", result.stdout + result.stderr)
        self.assertNotIn(str(self.directory).encode(), result.stdout + result.stderr)

    def test_real_missing_file_is_safe_rejection(self):
        result = self.run_cli("--input", str(self.directory / "PRIVATE-NOT-FOUND"))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["code"], "invalid_input")
        self.assertNotIn(b"PRIVATE", result.stdout + result.stderr)

    def test_real_usage_rejections_hide_arbitrary_tokens(self):
        for arguments in (
            (), ("--fixture", "PRIVATE-UNKNOWN"),
            ("--fixture", "complaint", "--input", "PRIVATE-PATH"),
            ("--fixture", "complaint", "--mode", "normalized"),
            ("--fixture", "complaint", "--transcript", "PRIVATE-TEXT"),
            ("--fixture", "complaint", "--manifest", "PRIVATE-PATH"),
            ("--fixt", "complaint"),
        ):
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"usage:", result.stderr)
                self.assertNotIn(b"PRIVATE", result.stderr)

    def test_real_help_succeeds_on_stdout_in_both_buffering_modes(self):
        for unbuffered in (False, True):
            with self.subTest(unbuffered=unbuffered):
                environment = dict(self.environment, PYTHONUNBUFFERED=str(int(unbuffered)))
                result = subprocess.run(
                    [sys.executable, "-m", "audio_processing", "--help"],
                    capture_output=True, timeout=5, cwd=self.directory, env=environment,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(b"usage: audio-processing", result.stdout)
                self.assertIn(b"--fixture", result.stdout)
                self.assertEqual(result.stderr, b"")

    def test_real_help_with_closed_stdout_is_exit_one_in_both_buffering_modes(self):
        for unbuffered in (False, True):
            with self.subTest(unbuffered=unbuffered):
                environment = dict(self.environment, PYTHONUNBUFFERED=str(int(unbuffered)))
                result = subprocess.run(
                    [sys.executable, "-m", "audio_processing", "--help"],
                    preexec_fn=lambda: os.close(1), capture_output=True, timeout=5,
                    cwd=self.directory, env=environment,
                )
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"usage:", result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)
                self.assertNotIn(b"Exception ignored", result.stderr)

    def test_real_help_broken_pipe_is_exit_one_in_both_buffering_modes(self):
        program = (
            "import sys; from audio_processing.cli import main; "
            "sys.stdin.buffer.read(1); raise SystemExit(main(['--help']))"
        )
        for unbuffered in (False, True):
            with self.subTest(unbuffered=unbuffered):
                environment = dict(self.environment, PYTHONUNBUFFERED=str(int(unbuffered)))
                process = subprocess.Popen(
                    [sys.executable, "-c", program], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=self.directory, env=environment,
                )
                process.stdout.close()
                process.stdout = None
                _output, diagnostic = process.communicate(b"x", timeout=5)
                self.assertEqual(process.returncode, 1, diagnostic)
                self.assertNotIn(b"Traceback", diagnostic)
                self.assertNotIn(b"Exception ignored", diagnostic)

    def test_help_with_missing_or_closed_stdout_stream_is_exit_one(self):
        closed = io.StringIO()
        closed.close()
        for stream in (None, closed):
            diagnostic = io.StringIO()
            with self.subTest(stream=stream), patch("sys.stdout", stream), redirect_stderr(diagnostic):
                status = cli.main(["--help"])
                self.assertEqual(status, 1)
                self.assertNotIn("usage:", diagnostic.getvalue())
                self.assertNotIn("Traceback", diagnostic.getvalue())

    def test_real_fifo_directory_symlink_and_oversized_input_do_not_hang(self):
        fifo = self.directory / "input.fifo"
        os.mkfifo(fifo)
        target = self.directory / "target.wav"
        target.write_bytes(make_wav([1]))
        symlink = self.directory / "link.wav"
        symlink.symlink_to(target)
        oversized = self.directory / "oversized.wav"
        with oversized.open("wb") as output:
            output.truncate(MAX_INPUT_BYTES + 1)
        for path in (fifo, self.directory, symlink, oversized):
            with self.subTest(path_kind=path.name):
                result = self.run_cli("--input", str(path))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(json.loads(result.stdout)["code"], "invalid_input")

    def test_parent_directory_symlink_is_allowed(self):
        real_directory = self.directory / "real"
        real_directory.mkdir()
        (real_directory / "input.wav").write_bytes(make_wav([1]))
        link = self.directory / "linked-directory"
        link.symlink_to(real_directory, target_is_directory=True)
        result = self.run_cli("--input", str(link / "input.wav"))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_inspects_opened_descriptor_instead_of_trusting_a_path(self):
        fifo = self.directory / "substituted.fifo"
        os.mkfifo(fifo)
        descriptor = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
        with patch("audio_processing.cli.os.open", return_value=descriptor):
            result = cli.read_input("apparently-regular.wav")
        self.assertIsInstance(result, Rejected)
        self.assertEqual(result.code, "invalid_input")
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_read_limit_still_applies_after_file_growth(self):
        path = self.directory / "growing.wav"
        path.write_bytes(b"x" * (MAX_INPUT_BYTES + 1))
        with patch("audio_processing.cli.os.fstat", return_value=type("Info", (), {"st_mode": 0o100600, "st_size": 1})()):
            result = cli.read_input(str(path))
        self.assertEqual(result.code, "invalid_input")

    def test_cancellation_closes_owned_input_descriptor(self):
        path = self.directory / "input.wav"
        path.write_bytes(make_wav([1]))
        opened = []
        real_open = os.open

        def capture(*args):
            descriptor = real_open(*args)
            opened.append(descriptor)
            return descriptor

        with patch("audio_processing.cli.os.open", side_effect=capture), patch("audio_processing.cli.os.read", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                cli.read_input(str(path))
        with self.assertRaises(OSError):
            os.fstat(opened[0])

    def test_corrupt_resources_exit_three(self):
        output = io.StringIO()
        with patch("audio_processing.load_assets", side_effect=AssetError("Packaged resources cannot be read.")), redirect_stdout(output):
            status = cli.main(["--fixture", "complaint"])
        self.assertEqual(status, 3)
        report = json.loads(output.getvalue())
        self.assertEqual(report["code"], "invalid_assets")
        self.assertNotIn("metrics", report)

    def test_missing_stdout_stream_is_exit_one(self):
        diagnostic = io.StringIO()
        with patch("sys.stdout", None), redirect_stderr(diagnostic):
            status = cli.main(["--fixture", "complaint"])
        self.assertEqual(status, 1)
        self.assertNotIn("Traceback", diagnostic.getvalue())

    def test_buffered_flush_failure_is_exit_one(self):
        class BrokenFlush(io.StringIO):
            def flush(self):
                raise BrokenPipeError("private operating-system detail")

        diagnostic = io.StringIO()
        with redirect_stdout(BrokenFlush()), redirect_stderr(diagnostic):
            status = cli.main(["--fixture", "complaint"])
        self.assertEqual(status, 1)
        self.assertNotIn("private", diagnostic.getvalue())

    def test_real_closed_stdout_descriptor_is_exit_one(self):
        result = self.run_cli("--fixture", "complaint", preexec_fn=lambda: os.close(1))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_real_broken_pipe_flush_is_exit_one(self):
        program = (
            "import sys; from audio_processing.cli import main; "
            "sys.stdin.buffer.read(1); raise SystemExit(main(['--fixture','complaint']))"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", program], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=self.directory, env=self.environment,
        )
        process.stdout.close()
        process.stdout = None
        _output, diagnostic = process.communicate(b"x", timeout=5)
        self.assertEqual(process.returncode, 1, diagnostic)
        self.assertNotIn(b"Traceback", diagnostic)
        self.assertNotIn(b"Exception ignored", diagnostic)

    def test_real_sigint_during_invocation_is_exit_130(self):
        program = "\n".join((
            "import signal",
            "from audio_processing import cli",
            "def interrupt(*args): signal.raise_signal(signal.SIGINT)",
            "cli.analyze_fixture = interrupt",
            "raise SystemExit(cli.main(['--fixture', 'complaint']))",
        ))
        result = subprocess.run([sys.executable, "-c", program], capture_output=True, timeout=5, cwd=self.directory, env=self.environment)
        self.assertEqual(result.returncode, 130, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(b"Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
