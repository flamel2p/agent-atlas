"""POSIX CLI boundary for bounded file acquisition and complete JSON reports.

Regular-file checks occur both before and after opening. O_NONBLOCK prevents a
file-type replacement race from blocking on a FIFO, and O_NOFOLLOW rejects a
final symlink. The descriptor is always closed during read failure/cancellation.
No user-supplied path, JSON fragment, or traceback is included in error output.
"""

import argparse
from importlib import resources
import json
import os
from pathlib import Path
import stat
import sys

from .replay import run_replay
from .schema import MAX_INPUT_BYTES, ScenarioError, parse_scenario

SCENARIOS = ("normal", "stale", "conflict", "late", "boundary")


def _discard_failed_stream(stream, expected_descriptor: int) -> None:
    # A failed buffered flush would otherwise run again during interpreter
    # shutdown, print an exception, and replace the promised exit code with 120.
    try:
        descriptor = stream.fileno()
        if descriptor == expected_descriptor:
            sink = os.open(os.devnull, os.O_WRONLY | os.O_CLOEXEC)
            try:
                os.dup2(sink, descriptor)
            finally:
                os.close(sink)
    except (OSError, ValueError, AttributeError):
        pass


def _write_stdout(message: str) -> None:
    try:
        sys.stdout.write(message)
        sys.stdout.flush()
    except OSError:
        _discard_failed_stream(sys.stdout, 1)
        raise


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ScenarioError("invalid arguments")

    def _print_message(self, message: str, file=None) -> None:
        if message:
            _write_stdout(message)


def read_input(path: str | Path) -> bytes:
    """Read at most the byte limit plus one, without opening special files."""
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_INPUT_BYTES:
        raise ScenarioError("invalid input file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or opened.st_size > MAX_INPUT_BYTES:
            raise ScenarioError("invalid input file")
        chunks = []
        remaining = MAX_INPUT_BYTES + 1
        while remaining:
            chunk = os.read(fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > MAX_INPUT_BYTES:
            raise ScenarioError("invalid input file")
        return raw
    finally:
        os.close(fd)


def _report_error(message: str) -> None:
    try:
        sys.stderr.write(message + "\n")
        sys.stderr.flush()
    except OSError:
        _discard_failed_stream(sys.stderr, 2)
        pass


def main(argv: list[str] | None = None) -> int:
    """Return 0 for a complete report, 2 for failure, or 130 for interruption."""
    try:
        parser = _Parser(description="Replay synthetic sensor evidence into simulated commands.")
        selection = parser.add_mutually_exclusive_group()
        selection.add_argument("--scenario", choices=SCENARIOS)
        selection.add_argument("--input", metavar="PATH")
        args = parser.parse_args(argv)
        if args.input is not None:
            raw = read_input(args.input)
        else:
            packaged = resources.files("physical_world_sensing").joinpath("scenarios", (args.scenario or "normal") + ".json")
            # Installed wheels unpack resources to regular filesystem paths.
            # Other import transports cannot establish this file-type boundary.
            if not isinstance(packaged, Path):
                raise ScenarioError("unsupported package resources")
            raw = read_input(packaged)
        report = run_replay(parse_scenario(raw))
        rendered = json.dumps(report, ensure_ascii=True, separators=(",", ":")) + "\n"
        # An explicit flush makes deferred stdout delivery errors a failed run.
        _write_stdout(rendered)
        return 0
    except KeyboardInterrupt:
        _report_error("error: interrupted")
        return 130
    except (ScenarioError, OSError, ValueError):
        _report_error("error: unable to complete simulation")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
