"""Strict file/JSON adapter and controlled stdout for the pure memo workflow.

All writes happen here. A flush guard handles closed pipes before interpreter
shutdown; argparse does not get authority to print through its own help path.
"""
from __future__ import annotations

import argparse
from importlib.resources import files
import json
import os
import sys

from .boundary import InvalidInput, decode_json, read_local
from .core import parse_corpus, parse_request, run

HELP = """usage: legal-intelligence [--input PATH] [--help]

Verify a memorandum in an original fictional legal system.
Omit --input to run the packaged matter. Output is JSON on stdout.
Exit 0: simulated reviewer handoff; 1: blocked review; 2: invalid input.
No human approval, real legal advice, provider, or external delivery exists.
"""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InvalidInput("arguments")


def write_output(text: str) -> bool:
    """Flush now so a closed result/help pipe fails quietly and nonzero."""
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
        return True
    except (OSError, ValueError):
        # Redirect the descriptor so buffered shutdown cannot emit a traceback
        # or turn this controlled failure into CPython's shutdown exit 120.
        try:
            sink = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(sink, sys.stdout.fileno())
            finally:
                os.close(sink)
        except (OSError, ValueError):
            pass
        return False


def fixture(name: str) -> bytes:
    return read_local(str(files("legal_intelligence").joinpath("fixtures", name)))


def main(argv: list[str] | None = None) -> int:
    """One request, one bounded report. Invalid proposals cannot grant release."""
    try:
        parser = Parser(add_help=False, allow_abbrev=False)
        parser.add_argument("--input")
        parser.add_argument("--help", action="store_true")
        args = parser.parse_args(argv)
        if args.help:
            return 0 if write_output(HELP) else 1
        raw = read_local(args.input) if args.input is not None else fixture("matter.json")
        matter, draft = parse_request(decode_json(raw))
        corpus = parse_corpus(decode_json(fixture("corpus.json"), corpus=True))
        result = run(matter, corpus, draft)
        payload = result.to_dict()
        exit_code = 0 if result.simulated_release else 1
    except (InvalidInput, OSError) as error:
        payload = {"outcome": "invalid_input", "error": str(error) if isinstance(error, InvalidInput)
                   else "unreadable_regular_file", "simulated_release": False}
        exit_code = 2
    except KeyboardInterrupt:
        payload = {"outcome": "cancelled", "simulated_release": False}
        exit_code = 130
    return exit_code if write_output(json.dumps(payload, indent=2, allow_nan=False) + "\n") else 1
