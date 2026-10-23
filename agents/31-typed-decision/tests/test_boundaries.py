"""Strict JSON/file boundaries and real child lifetime verification."""

import os
import signal
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from typed_decision import Policy, predict
from typed_decision.json_boundary import Invalid, loads, read_file, snapshot
from test_decision import demo


class JSONBoundaryTests(unittest.TestCase):
    def test_library_utf8_snapshot_matches_exact_serialized_byte_limit(self):
        value = "😀" * 16_383 + "xx"
        self.assertEqual(snapshot(value), value)
        with self.assertRaises(Invalid):
            snapshot(value + "x")

    def test_duplicate_keys_nonstandard_numbers_and_depth(self):
        for value in [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'"\xff"',
                      b'[' * 9 + b'0' + b']' * 9, b'1e1001', b'1e-1001',
                      b'1' * 65, b'{"x":', b'{} {}', b'\xef\xbb\xbf{}']:
            with self.subTest(value=value), self.assertRaises(Invalid):
                loads(value)
        self.assertEqual(loads(b'[' * 8 + b'0' + b']' * 8), [[[[[[[[0]]]]]]]])
        with self.assertRaises(Invalid):
            loads(b' ' * 65_537)
        self.assertEqual(loads(b' ' * 65_534 + b'{}'), {})

    def test_delimiters_inside_strings_do_not_change_depth(self):
        self.assertEqual(loads(b'{"x":"[[[\\\"{{{"}'), {"x": '[[["{{{'})

    def test_no_symlinks_directories_fifos_or_oversized_files(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root).resolve()
            valid = folder / "valid.json"
            valid.write_bytes(b"{}")
            self.assertEqual(read_file(valid), b"{}")
            leaf = folder / "leaf.json"
            leaf.symlink_to(valid)
            parent = folder / "parent"
            parent.symlink_to(folder, target_is_directory=True)
            fifo = folder / "fifo"
            os.mkfifo(fifo)
            big = folder / "big.json"
            big.write_bytes(b" " * 65_537)
            for path in (leaf, parent / "valid.json", parent / ".." / "valid.json",
                         folder, fifo, big, folder / "missing"):
                with self.subTest(path=path), self.assertRaises(Invalid):
                    read_file(path)

    def test_direct_library_values_are_bounded_and_json_typed(self):
        for value in [{1: "x"}, {"a": (1, 2)}, {"a": float("nan")}, {"a": "x" * 65_537},
                      {"a": "\ud800"}, {"\ud800": "a"}]:
            with self.assertRaises(Invalid):
                snapshot(value)


class RuntimeTests(unittest.TestCase):
    def test_sigint_during_launch_cannot_orphan_worker(self):
        fixture = demo()
        fixture["behavior"] = "hang"
        children = []
        original = subprocess.Popen

        def start(*args, **kwargs):
            process = original(*args, **kwargs)
            children.append(process)
            os.kill(os.getpid(), signal.SIGINT)
            return process

        with patch("typed_decision.runtime.subprocess.Popen", side_effect=start):
            result = predict(fixture["request"], fixture=fixture)
        self.assertEqual((result.status, result.attempts), ("cancellation", 1))
        self.assertIsNotNone(children[0].poll())

    def test_backend_failure_is_one_attempt(self):
        fixture = demo()
        fixture["behavior"] = "fail"
        result = predict(fixture["request"], fixture=fixture)
        self.assertEqual((result.status, result.attempts, result.selected_label),
                         ("backend_failure", 1, None))

    def test_timeout_kills_and_reaps_actual_worker(self):
        fixture = demo()
        fixture["behavior"] = "hang"
        children = []
        original = subprocess.Popen

        def start(*args, **kwargs):
            process = original(*args, **kwargs)
            children.append(process)
            return process

        before = time.monotonic()
        with patch("typed_decision.runtime.subprocess.Popen", side_effect=start):
            result = predict(fixture["request"], fixture=fixture, policy=Policy(timeout_seconds=0.1))
        self.assertEqual((result.status, result.attempts), ("timeout", 1))
        self.assertLess(time.monotonic() - before, 1.0)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())
        self.assertTrue(all(stream.closed for stream in (children[0].stdin, children[0].stdout)))
        self.assertIsNone(result.selected_label)
        self.assertIsNone(result.probabilities)

    def test_cancellation_before_attempt_and_during_child(self):
        fixture = demo()
        fixture["behavior"] = "hang"
        cancel = threading.Event()
        cancel.set()
        before = predict(fixture["request"], fixture=fixture, cancel=cancel)
        self.assertEqual((before.status, before.attempts), ("cancellation", 0))
        cancel.clear()
        children = []
        original = subprocess.Popen

        def start(*args, **kwargs):
            process = original(*args, **kwargs)
            children.append(process)
            return process

        timer = threading.Timer(0.1, cancel.set)
        timer.start()
        started = time.monotonic()
        try:
            with patch("typed_decision.runtime.subprocess.Popen", side_effect=start):
                result = predict(fixture["request"], fixture=fixture, cancel=cancel)
        finally:
            timer.join()
        self.assertEqual((result.status, result.attempts, result.selected_label), ("cancellation", 1, None))
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())

    def test_cannot_start_worker_returns_honest_failure(self):
        fixture = demo()
        with patch("typed_decision.runtime.subprocess.Popen", side_effect=OSError("sensitive path")):
            result = predict(fixture["request"], fixture=fixture)
        self.assertEqual((result.status, result.attempts), ("backend_failure", 0))
        self.assertNotIn("sensitive", result.to_json())

    def test_invalid_cancellation_type_is_not_invoked(self):
        fixture = demo()
        result = predict(fixture["request"], fixture=fixture, cancel=True)
        self.assertEqual((result.status, result.attempts), ("invalid_input", 0))
