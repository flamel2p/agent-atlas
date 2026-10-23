"""Drive installed entry points as real processes, including closed stdout."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from typed_decision.json_boundary import dumps, loads
from test_decision import demo


def run_cli(*arguments, unbuffered=False, env=None):
    command = [sys.executable] + (["-u"] if unbuffered else []) + ["-m", "typed_decision", *arguments]
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, env=env)


class CLITests(unittest.TestCase):
    def test_actual_cli_accepts_valid_utf8_bytes_and_rejects_excessive_state(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root).resolve()
            request_path, fixture_path = folder / "request.json", folder / "fixture.json"
            for repetitions, status, code in [(8000, "decision", 0), (8193, "invalid_input", 2)]:
                fixture = demo()
                fixture["request"]["request_id"] = "请求😀"
                fixture["request"]["state"] = "😀" * repetitions
                labels = ["信息😀", "排程", "其他"]
                fixture["request"]["labels"] = labels
                fixture["response"]["selection"] = labels[0]
                # Independent input encoding must not reproduce a serializer defect.
                fixture["response"]["probabilities"] = dict(zip(labels, [0.9, 0.06, 0.04]))
                request_bytes = json.dumps(fixture["request"], ensure_ascii=False).encode("utf-8")
                fixture_bytes = json.dumps(fixture, ensure_ascii=False).encode("utf-8")
                self.assertLess(len(request_bytes), 65_536)
                self.assertLess(len(fixture_bytes), 65_536)
                request_path.write_bytes(request_bytes)
                fixture_path.write_bytes(fixture_bytes)
                result = run_cli("--request", str(request_path), "--fixture", str(fixture_path))
                self.assertEqual((result.returncode, loads(result.stdout)["status"]), (code, status), result.stderr)
                self.assertEqual(loads(result.stdout)["attempts"], 1 if code == 0 else 0)
                self.assertEqual(result.stderr, b"")
                if code == 0:
                    self.assertEqual(loads(result.stdout)["request_id"], "请求😀")
                    self.assertEqual(loads(result.stdout)["selected_label"], "信息😀")
                    ascii_result = run_cli("--request", str(request_path), "--fixture", str(fixture_path),
                                           env={**os.environ, "PYTHONIOENCODING": "ascii"})
                    self.assertEqual(ascii_result.returncode, 0, ascii_result.stderr)
                    self.assertEqual(loads(ascii_result.stdout), loads(result.stdout))
                    self.assertEqual(ascii_result.stderr, b"")

    def test_module_and_console_entrypoints(self):
        module = run_cli()
        self.assertEqual(module.returncode, 0, module.stderr)
        self.assertEqual(loads(module.stdout)["status"], "decision")
        entry = subprocess.run([str(Path(sys.executable).parent / "typed-decision")],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(entry.returncode, 0, entry.stderr)
        self.assertEqual(loads(entry.stdout), loads(module.stdout))

    def test_sanitized_invalid_arguments_and_policy(self):
        for arguments in [("--unknown-secret-value",), ("--threshold", "private-secret"),
                          ("--timeout", "nan"), ("--threshold",), ("--timeout", "11"),
                          ("--threshold", "-1"), ("--threshold", "1" * 5000)]:
            for unbuffered in (False, True):
                result = run_cli(*arguments, unbuffered=unbuffered)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(loads(result.stdout)["status"], "invalid_input")
                self.assertEqual(result.stderr, b"")
                self.assertLess(len(result.stdout), 1024)
                self.assertNotIn(b"private", result.stdout)
                self.assertNotIn(b"secret", result.stdout)

    def test_strict_request_and_fixture_files(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root).resolve()
            request = folder / "request.json"
            request.write_bytes(b'{"state":1,"state":2}')
            invalid_request = run_cli("--request", str(request))
            self.assertEqual((invalid_request.returncode, loads(invalid_request.stdout)["status"]),
                             (2, "invalid_input"))
            fixture = folder / "fixture.json"
            fixture.write_bytes(b'{"response":NaN}')
            invalid_fixture = run_cli("--fixture", str(fixture))
            self.assertEqual((invalid_fixture.returncode, loads(invalid_fixture.stdout)["status"]),
                             (2, "invalid_output"))
            surrogate = demo()
            surrogate["response"]["selection"] = "\ud800"
            surrogate["response"]["probabilities"] = {
                k: float(v) for k, v in surrogate["response"]["probabilities"].items()}
            fixture.write_text(json.dumps(surrogate, ensure_ascii=True))
            surrogate_result = run_cli("--fixture", str(fixture))
            self.assertEqual((surrogate_result.returncode, loads(surrogate_result.stdout)["status"]),
                             (2, "invalid_output"))
            self.assertEqual(surrogate_result.stderr, b"")

    def test_abstention_timeout_and_failure_exit_codes(self):
        abstain = run_cli("--threshold", "0.9")
        self.assertEqual((abstain.returncode, loads(abstain.stdout)["status"]), (0, "abstention"))
        with tempfile.TemporaryDirectory() as root:
            path = Path(root).resolve() / "fixture.json"
            for behavior, expected_status, code in [("hang", "timeout", 4), ("fail", "backend_failure", 3)]:
                fixture = demo()
                fixture["behavior"] = behavior
                path.write_text(dumps(fixture))
                result = run_cli("--fixture", str(path), "--timeout", "0.1")
                self.assertEqual((result.returncode, loads(result.stdout)["status"]), (code, expected_status))
                self.assertEqual(result.stderr, b"")

    def test_sigint_returns_cancellation_json(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root).resolve() / "fixture.json"
            fixture = demo()
            fixture["behavior"] = "hang"
            path.write_text(dumps(fixture))
            process = subprocess.Popen([sys.executable, "-m", "typed_decision", "--fixture", str(path)],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                time.sleep(0.2)
                process.send_signal(signal.SIGINT)
                output, errors = process.communicate(timeout=2)
                self.assertEqual((process.returncode, loads(output)["status"]), (130, "cancellation"))
                self.assertEqual(errors, b"")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_closed_stdout_is_quiet_for_help_and_results_in_both_modes(self):
        for unbuffered in (False, True):
            for arguments in [[], ["--help"], ["--unknown-private-value"]]:
                read_fd, write_fd = os.pipe()
                os.close(read_fd)
                command = [sys.executable] + (["-u"] if unbuffered else []) + ["-m", "typed_decision", *arguments]
                try:
                    process = subprocess.Popen(command, stdout=write_fd, stderr=subprocess.PIPE)
                finally:
                    os.close(write_fd)
                _, errors = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 0, errors)
                self.assertEqual(errors, b"")

    def test_readonly_stdout_returns_output_failure_without_traceback_or_shutdown_error(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root).resolve() / "readonly-output"
            path.write_bytes(b"")
            for unbuffered in (False, True):
                for arguments in ([], ["--help"]):
                    descriptor = os.open(path, os.O_RDONLY)
                    command = [sys.executable] + (["-u"] if unbuffered else []) + ["-m", "typed_decision", *arguments]
                    try:
                        process = subprocess.Popen(command, stdout=descriptor, stderr=subprocess.PIPE)
                    finally:
                        os.close(descriptor)
                    _, errors = process.communicate(timeout=5)
                    self.assertEqual(process.returncode, 3, errors)
                    self.assertEqual(errors, b"")
                    self.assertEqual(path.read_bytes(), b"")

    def test_help_is_available_and_flushes(self):
        for unbuffered in (False, True):
            result = run_cli("--help", unbuffered=unbuffered)
            self.assertEqual(result.returncode, 0)
            self.assertIn(b"--threshold", result.stdout)
            self.assertEqual(result.stderr, b"")
