"""Allowlisted fixture CLI. All learning and gate policy live in experiment.py."""

import argparse
import sys

from . import ScenarioError, ScenarioName, load_scenario, run_experiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one bounded FAQ adaptation experiment")
    parser.add_argument("--scenario", required=True, choices=[name.value for name in ScenarioName])
    args = parser.parse_args(argv)
    try:
        report = run_experiment(load_scenario(ScenarioName(args.scenario)))
    except ScenarioError as error:
        parser.error(str(error))
    try:
        print(report.to_json(), flush=True)
    except BrokenPipeError:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
