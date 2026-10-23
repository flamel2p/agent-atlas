"""Real CLI, unsafe-file, output-failure, and cancellation boundary checks."""

from contextlib import redirect_stderr, redirect_stdout
from importlib import resources
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from physical_world_sensing import ScenarioError
from physical_world_sensing.cli import main, read_input
from helpers import scenario


def invoke(*args, **kwargs):
    return subprocess.run([sys.executable, "-m", "physical_world_sensing", *args], capture_output=True, timeout=10, **kwargs)


class BrokenStream(io.StringIO):
    def write(self, message):
        raise OSError("private output detail")


class FlushFailure(io.StringIO):
    def flush(self):
        raise OSError("private flush detail")


class CliTests(unittest.TestCase):
    def test_default_console_and_module_use_same_normal_report(self):
        module = invoke()
        self.assertEqual(module.returncode, 0, module.stderr)
        console = subprocess.run([str(Path(sys.executable).with_name("physical-world-sensing")), "--scenario", "normal"], capture_output=True, timeout=10)
        self.assertEqual(console.returncode, 0, console.stderr)
        self.assertEqual(json.loads(module.stdout), json.loads(console.stdout))
        self.assertEqual(module.stderr, b"")

    def test_explicit_regular_file_and_no_input_path_in_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "private-scenario.json")
            path.write_text(json.dumps(scenario()))
            result = invoke("--input", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(str(path).encode(), result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "completed")

    def test_argument_failures_are_sanitized_and_produce_no_report(self):
        for args in (("--scenario", "private-unknown"), ("--input",), ("--other-private",), ("--scenario", "normal", "--input", "private.json")):
            with self.subTest(args=args):
                result = invoke(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(result.stderr, b"error: unable to complete simulation\n")

    def test_missing_invalid_and_oversized_files_fail_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "private.json")
            for payload in (None, b"{private broken json", b"\xff", b" " * 262145):
                if payload is not None:
                    path.write_bytes(payload)
                result = invoke("--input", str(path))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"private", result.stderr)

    def test_special_files_are_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            regular = Path(directory, "regular.json")
            regular.write_text(json.dumps(scenario()))
            link = Path(directory, "link.json")
            link.symlink_to(regular)
            fifo = Path(directory, "fifo.json")
            os.mkfifo(fifo)
            for path in (Path(directory), link, fifo, Path(os.devnull)):
                with self.subTest(path=path.name):
                    result = invoke("--input", str(path))
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, b"")

    def test_file_replaced_by_fifo_between_stat_and_open_cannot_block(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "replace.json")
            path.write_text(json.dumps(scenario()))
            real_open = os.open
            def replace_then_open(name, flags):
                self.assertTrue(flags & os.O_NONBLOCK)
                self.assertTrue(flags & os.O_NOFOLLOW)
                path.unlink()
                os.mkfifo(path)
                return real_open(name, flags)
            with patch("physical_world_sensing.cli.os.open", side_effect=replace_then_open):
                with self.assertRaises(ScenarioError):
                    read_input(path)

    def test_descriptors_close_on_read_failure_and_keyboard_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "input.json")
            path.write_text(json.dumps(scenario()))
            for failure in (OSError("private failure"), KeyboardInterrupt()):
                opened = []
                real_open = os.open
                def track_open(name, flags):
                    fd = real_open(name, flags)
                    opened.append(fd)
                    return fd
                with patch("physical_world_sensing.cli.os.open", side_effect=track_open), patch("physical_world_sensing.cli.os.read", side_effect=failure):
                    with self.assertRaises(type(failure)):
                        read_input(path)
                self.assertEqual(len(opened), 1)
                with self.assertRaises(OSError):
                    os.fstat(opened[0])

    def test_packaged_resources_use_same_regular_bounded_file_boundary(self):
        raw = resources.files("physical_world_sensing").joinpath("scenarios", "normal.json").read_bytes()
        for kind in ("valid", "missing", "directory", "symlink", "fifo", "oversize"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                folder = root / "scenarios"
                folder.mkdir()
                path = folder / "normal.json"
                if kind == "valid":
                    path.write_bytes(raw)
                elif kind == "directory":
                    path.mkdir()
                elif kind == "symlink":
                    target = root / "target.json"
                    target.write_bytes(raw)
                    path.symlink_to(target)
                elif kind == "fifo":
                    os.mkfifo(path)
                elif kind == "oversize":
                    path.write_bytes(raw + b" " * 262145)
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch("physical_world_sensing.cli.resources.files", return_value=root), redirect_stdout(stdout), redirect_stderr(stderr):
                    code = main([])
                self.assertEqual(code, 0 if kind == "valid" else 2)
                if kind != "valid":
                    self.assertEqual(stdout.getvalue(), "")

    def test_nonfilesystem_packaged_resources_fail_closed(self):
        with patch("physical_world_sensing.cli.resources.files") as files, redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main([]), 2)
            self.assertEqual(stdout.getvalue(), "")

    def test_keyboard_interruption_returns_130_without_traceback(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("physical_world_sensing.cli.read_input", side_effect=KeyboardInterrupt), redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--input", "private.json"])
        self.assertEqual(code, 130)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "error: interrupted\n")

    def test_output_write_and_flush_failures_exit_2(self):
        for stream in (BrokenStream(), FlushFailure()):
            with redirect_stdout(stream), redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(main([]), 2)
            self.assertEqual(stderr.getvalue(), "error: unable to complete simulation\n")

    def test_help_output_delivery_failure_exits_2(self):
        with redirect_stdout(BrokenStream()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--help"]), 2)

    def test_closed_stdout_pipe_preserves_failure_exit_without_shutdown_traceback(self):
        for args in ([], ["--help"]):
            read_fd, write_fd = os.pipe()
            os.close(read_fd)
            try:
                result = subprocess.run([sys.executable, "-m", "physical_world_sensing", *args], stdout=write_fd, stderr=subprocess.PIPE, timeout=10)
            finally:
                os.close(write_fd)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(b"Traceback", result.stderr)
            self.assertNotIn(b"Exception ignored", result.stderr)

    def test_closed_stderr_pipe_preserves_error_and_interruption_exit(self):
        commands = [
            ([sys.executable, "-m", "physical_world_sensing", "--scenario", "unknown"], 2),
            ([sys.executable, "-c", "from unittest.mock import patch; from physical_world_sensing.cli import main;\nwith patch('physical_world_sensing.cli.read_input',side_effect=KeyboardInterrupt): raise SystemExit(main(['--input','x']))"], 130),
        ]
        for command, expected in commands:
            read_fd, write_fd = os.pipe()
            os.close(read_fd)
            try:
                result = subprocess.run(command, stdout=subprocess.PIPE, stderr=write_fd, timeout=10)
            finally:
                os.close(write_fd)
            self.assertEqual(result.returncode, expected)
            self.assertEqual(result.stdout, b"")

    def test_help_is_successful_without_simulation_output(self):
        result = invoke("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"--scenario", result.stdout)
        self.assertEqual(result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
