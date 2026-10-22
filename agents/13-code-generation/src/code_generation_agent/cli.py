"""Console entry point: validate arguments, run once, print honest JSON and exit."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .artifacts import InvalidInput
from .domain import SCENARIOS, Status
from .runner import run

EXIT_CODES = {Status.COMPLETED: 0, Status.EXHAUSTED: 3, Status.FAILED: 4, Status.CANCELLED: 130}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refine a shipping function using bounded fixture feedback.")
    parser.add_argument("--scenario", choices=SCENARIOS, default="repair")
    parser.add_argument("--max-attempts", type=int, choices=range(1, 4), default=3)
    parser.add_argument("--workspace", type=Path, default=None, help="Physical case workspace; defaults to current directory.")
    args = parser.parse_args(argv)
    try:
        result = run(args.scenario, args.max_attempts, workspace=args.workspace)
    except InvalidInput as error:
        print(json.dumps({"mode": "fixture", "status": "invalid_input", "error": str(error)}))
        return 2
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return EXIT_CODES[result.status]


if __name__ == "__main__":
    raise SystemExit(main())
