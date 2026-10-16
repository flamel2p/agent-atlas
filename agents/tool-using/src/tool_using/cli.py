import argparse
import json
import os

from .contracts import Failure, RunConfig
from .controller import error_report, exit_code, run


EXAMPLES = {
    "revenue-by-channel-bar": ("Compare total revenue by channel", "bar"),
    "spend-by-channel-table": ("Compare total spend by channel", "table"),
    "invalid-tool-call": ("Demonstrate rejection of an unpermitted tool", "table"),
}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Failure("invalid_input", status="rejected", phase="cli")


def parse_config(argv: list[str] | None = None) -> RunConfig:
    parser = Parser(description="Summarize synthetic campaign data through bounded tool calls.")
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    parser.add_argument("--example", choices=tuple(EXAMPLES))
    parser.add_argument("--task")
    parser.add_argument("--format", choices=("table", "bar"))
    args = parser.parse_args(argv)
    if args.mode == "replay":
        if args.task is not None or args.format is not None:
            parser.error("Live-only option in replay mode")
        example = args.example or "revenue-by-channel-bar"
        task, output_format = EXAMPLES[example]
        return RunConfig(mode="replay", task=task, output_format=output_format, example=example)
    if args.example is not None or args.task is None:
        parser.error("Live mode requires a task and no replay example")
    task = args.task.strip()
    if not 1 <= len(task) <= 500:
        parser.error("Task length")
    return RunConfig(mode="live", task=task, output_format=args.format or "table", example=None)


def main(argv: list[str] | None = None) -> int:
    config = RunConfig()
    try:
        config = parse_config(argv)
        key = os.environ.get("OPENAI_API_KEY") if config.mode == "live" else None
        report = run(config, api_key=key)
    except Failure as failure:
        report = error_report(config, failure)
    print(json.dumps(report, indent=2, allow_nan=False))
    return exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
