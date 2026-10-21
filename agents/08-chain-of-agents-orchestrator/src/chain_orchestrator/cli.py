"""Fixture-name CLI. Print one report or one bounded diagnostic, with explicit exits."""

import argparse
import asyncio
from dataclasses import asdict
import json
import sys

from .contracts import RunStatus
from .evidence import InputError, SCENARIOS
from .manager import analyze_release


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's default diagnostic reflects arbitrary user arguments.
        raise InputError("invalid_arguments; use --help")


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description="Reconcile synthetic release evidence. Fixture mode only.")
    parser.add_argument("scenario", choices=SCENARIOS, nargs="?", default="consistent")
    parser.add_argument("--target-release", help="Select a release already present in the fixture")
    try:
        args = parser.parse_args(argv)
        report = asyncio.run(analyze_release(args.scenario, args.target_release))
    except InputError as exc:
        print(f"input_error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    print(json.dumps(asdict(report), indent=2))
    return {RunStatus.COMPLETE: 0, RunStatus.REVIEW_REQUIRED: 2,
            RunStatus.FAILED: 1, RunStatus.TIMED_OUT: 1}[report.status]
