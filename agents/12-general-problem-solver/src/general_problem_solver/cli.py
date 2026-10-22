"""POSIX read-only CLI. Bound file input, run the pure solver, emit one report.

No user paths become output paths. The only application I/O is the selected
input or packaged example, stdout, stderr, and null-device cleanup after a
failed stdout write or flush. A descriptor check prevents a path replacement from
bypassing regular-file validation.
"""

import argparse
from dataclasses import asdict
from importlib.resources import files
import json
import os
import stat
import sys

from .domain import InputError, MAX_DOCUMENT_BYTES
from .solver import solve_document

EXAMPLES = (
    "revision", "already-valid", "impossible", "dependency", "iteration-limit",
    "evaluation-limit", "local-minimum",
)


def _read_regular_file(path: str) -> bytes:
    if not stat.S_ISREG(os.stat(path).st_mode):
        raise InputError("input must be a regular file")
    # O_NONBLOCK prevents a swapped FIFO from waiting during open. fstat checks
    # the opened descriptor instead of trusting the earlier path inspection.
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise InputError("input must be a regular file")
        if metadata.st_size > MAX_DOCUMENT_BYTES:
            raise InputError("input exceeds the 65536-byte limit")
        return stream.read(MAX_DOCUMENT_BYTES + 1)


def _write_stdout(text: str) -> None:
    """Write and flush text, or flush argparse's buffered help with empty text."""
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except OSError:
        # CPython retries buffered stdout at shutdown. Discard it through the
        # null device so that retry cannot replace the I/O exit code with 120.
        descriptor = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(descriptor, sys.stdout.fileno())
        finally:
            os.close(descriptor)
        raise


def main(argv: list[str] | None = None) -> int:
    """Emit deterministic JSON with exit 0 solved, 1 unsolved, 2 error, 130 interrupt."""
    try:
        parser = argparse.ArgumentParser(
            description="Solve a bounded synthetic scheduling puzzle", allow_abbrev=False,
        )
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument("--example", choices=EXAMPLES, action="append")
        source.add_argument("--input", metavar="PATH", action="append")
        try:
            args = parser.parse_args(argv)
        except SystemExit:
            # argparse exits after help; flush it under the same I/O handling.
            _write_stdout("")
            raise
        selected = args.example if args.example is not None else args.input
        if len(selected) != 1:
            parser.error("provide exactly one input or example")
        if args.example is not None:
            document = files("general_problem_solver").joinpath(
                "examples", selected[0] + ".json",
            ).read_bytes()
        else:
            document = _read_regular_file(selected[0])
        report = solve_document(document)
        output = json.dumps(asdict(report), sort_keys=True, indent=2, allow_nan=False)
        _write_stdout(output + "\n")
        return 0 if report.status == "solved" else 1
    except InputError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    except OSError:
        print("I/O error: could not read input or write output", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
