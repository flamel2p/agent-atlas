"""CLI boundary: select bundled input/mode, preflight live access, emit stdout JSON."""

import argparse
import json
import os

from .backends import OpenAIPlanner
from .contracts import Failure
from .controller import run
from .fixtures import EXAMPLES, load_example


def main(argv=None) -> int:
    """Map terminal reports to exits: completed=0, cancelled=130, otherwise=2."""

    parser = argparse.ArgumentParser(description="Plan and simulate a bounded documentation release.")
    parser.add_argument("--example", choices=EXAMPLES, default="normal")
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    args = parser.parse_args(argv)
    planner = None
    preflight_failure = None
    if args.mode == "live":
        # Pass preflight failures into the normal report path before any task can
        # start; a missing live dependency must never silently select replay.
        try:
            planner = OpenAIPlanner(os.environ.get("OPENAI_API_KEY", ""))
        except Failure as failure:
            preflight_failure = failure
        except KeyboardInterrupt:
            preflight_failure = Failure("interrupted")
    report = run(load_example(args.example), planner=planner, mode=args.mode,
                 preflight_failure=preflight_failure)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["status"] == "completed" else 130 if report["status"] == "cancelled" else 2
