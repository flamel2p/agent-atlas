"""Expose one stateless question as JSON, with stable machine-readable exit codes."""

import argparse
import json
import sys

from .contracts import AgentError
from .engine import empty_result, run


class Parser(argparse.ArgumentParser):
    """Route argument errors through sanitized JSON instead of echoing raw arguments."""

    def error(self, message):
        raise AgentError("invalid_input")


def main(argv=None) -> int:
    """Translate CLI options into host scope; the engine owns validation and execution.

    Answer/abstention exit 0, runtime failure 1, invalid input 2, interruption 130.
    """
    try:
        parser = Parser(description="Retrieve exact passages from synthetic AtlasDesk support documents.")
        commands = parser.add_subparsers(dest="command", required=True)
        ask = commands.add_parser("ask")
        ask.add_argument("question")
        ask.add_argument("--backend", choices=("replay", "openai"), default="replay")
        ask.add_argument("--audience", choices=("public", "staff"), default="public")
        ask.add_argument("--version", default="2.0")
        ask.add_argument("--as-of")
        args = parser.parse_args(argv)
        result, code = run(args.question, backend=args.backend, audience=args.audience,
                           version=args.version, as_of=args.as_of)
    except AgentError:
        result, code = empty_result(), 2
    except KeyboardInterrupt:
        result, code = empty_result(), 130
        result.update(status="cancelled", reason="interrupted")
    print(json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
