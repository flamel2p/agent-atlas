import argparse
import asyncio
import os
from collections.abc import Sequence

from .backends import LiveBackend, ReplayBackend
from .controller import run_decision, stopped_outcome
from .fixtures import EXAMPLES, SyntheticStatusTool, load_example


class UsageError(Exception):
    pass


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError("invalid_input")


def main(argv: Sequence[str] | None = None) -> int:
    mode = "replay"
    try:
        parser = JsonArgumentParser(description="Prepare one bounded decision from a synthetic support ticket.")
        parser.add_argument("--example", choices=EXAMPLES, default="routine-outage")
        parser.add_argument("--mode", choices=("replay", "live"), default="replay")
        args = parser.parse_args(argv)
        mode = args.mode
        api_key = os.environ.get("OPENAI_API_KEY", "").strip() if mode == "live" else ""
        if mode == "live" and not api_key:
            outcome = stopped_outcome("invalid_configuration", mode)
        else:
            cognition = LiveBackend(api_key) if mode == "live" else None
            if cognition is not None:
                cognition.validate_configuration()
            example = load_example(args.example)
            if cognition is None:
                cognition = ReplayBackend(example.proposal_override)
            outcome = asyncio.run(run_decision(example.ticket, SyntheticStatusTool(example.observation_json), cognition, mode=mode))
    except KeyboardInterrupt:
        outcome = stopped_outcome("cancelled", mode, cancelled=True)
    except UsageError:
        outcome = stopped_outcome("invalid_input", mode)
    except Exception:
        outcome = stopped_outcome("invalid_configuration", mode)
    print(outcome.report.model_dump_json(indent=2))
    return outcome.exit_code
