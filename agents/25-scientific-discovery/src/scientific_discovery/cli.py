"""CLI owns regular-file input, controlled errors, cancellation, and output flushing.

Domain code has no file or output authority. Explicit flushing catches buffered
broken pipes before interpreter shutdown; fd redirection prevents a second flush.
"""
import argparse
from importlib.resources import as_file, files
import json
import os
from pathlib import Path
import sys

from .domain import discover
from .input import InvalidInput, parse, read_input


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default diagnostic includes caller text and can exceed input bounds.
        raise InvalidInput("invalid_arguments")

    # argparse suppresses OSError while printing help, hiding closed output pipes.
    def _print_message(self, message, file=None):
        if message:
            (file or sys.stderr).write(message)


def _quiet_stdout() -> None:
    try:
        descriptor = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(descriptor, sys.stdout.fileno())
        finally:
            os.close(descriptor)
    except (OSError, ValueError):
        pass


def _error(kind: str) -> None:
    try:
        sys.stderr.write(json.dumps({"error": kind}) + "\n")
        sys.stderr.flush()
    except (BrokenPipeError, OSError):
        pass


def main(argv: list[str] | None = None) -> int:
    """Emit one report, or a controlled boundary failure without input disclosure."""
    try:
        parser = _Parser(description="Synthetic corpus gaps and virtual experiments only.")
        parser.add_argument("--input", type=Path, help="Strict JSON regular file; defaults to the packaged planted fixture.")
        try:
            args = parser.parse_args(argv)
        except SystemExit as exit_status:
            # Help and usage also write through buffered streams before exiting.
            sys.stdout.flush()
            return int(exit_status.code or 0)
        if args.input is None:
            with as_file(files("scientific_discovery").joinpath("fixtures/planted.json")) as path:
                data = read_input(path)
        else:
            data = read_input(args.input)
        report = discover(parse(data))
        sys.stdout.write(json.dumps(report.to_dict(), allow_nan=False, sort_keys=True, indent=2) + "\n")
        sys.stdout.flush()
        return 0
    except BrokenPipeError:
        _quiet_stdout()
        return 1
    except (InvalidInput, OSError, ValueError):
        _error("invalid_input")
        return 2
    except KeyboardInterrupt:
        _error("cancelled")
        return 130
