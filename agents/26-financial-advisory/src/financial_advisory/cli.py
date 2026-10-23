"""Bounded JSON CLI, packaged fixtures, and explicit output failure handling.

Argparse only parses and formats here. The host writer owns help and report writes
and flushes, including unbuffered failures that argparse would otherwise suppress.
No input text becomes a file path, code, provider call, or policy override.
"""

import argparse
from importlib.resources import files
import json
import os
import sys

from .domain import run
from .validation import InvalidInput, MAX_BYTES, parse

FIXTURES = ("normal", "stale", "persistent", "missing")


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # Do not echo untrusted argument contents or let argparse write to stderr.
        raise InvalidInput("unsupported command-line arguments")


def _silence(stream) -> None:
    """Prevent a failed buffered descriptor from failing again at interpreter exit."""
    try:
        descriptor = stream.fileno()
        with open(os.devnull, "wb") as sink:
            os.dup2(sink.fileno(), descriptor)
    except (OSError, ValueError, AttributeError):
        pass


def _write(stream, text: str) -> bool:
    try:
        stream.write(text)
        stream.flush()
        return True
    except OSError:
        _silence(stream)
        return False


def _emit(payload: dict, code: int) -> int:
    if _write(sys.stdout, json.dumps(payload, allow_nan=False, sort_keys=True, indent=2) + "\n"):
        return code
    _write(sys.stderr, "output unavailable\n")
    return 74


def main(argv: list[str] | None = None) -> int:
    parser = Parser(description="Fictional portfolio simulation. No advice or order authority.",
                    add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--fixture", choices=FIXTURES)
    source.add_argument("--stdin", action="store_true", help="read at most 65536 UTF-8 JSON bytes")
    try:
        options = parser.parse_args(argv)
        if options.help:
            if _write(sys.stdout, parser.format_help()):
                return 0
            _write(sys.stderr, "output unavailable\n")
            return 74
        if options.stdin:
            raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        else:
            # Fixture names come from a closed host enumeration, not caller paths.
            resource = files("financial_advisory").joinpath("fixtures", f"{options.fixture or 'normal'}.json")
            with resource.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
        return _emit(run(parse(raw)).to_dict(), 0)
    except InvalidInput as error:
        return _emit({"status": "invalid_input", "error": str(error)}, 2)
    except KeyboardInterrupt:
        return _emit({"status": "cancelled"}, 130)
    except OSError:
        _write(sys.stderr, "input/output unavailable\n")
        return 74
