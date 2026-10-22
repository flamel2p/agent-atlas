"""One JSON result per invocation. No interactive loop, network, or credentials.

CLI labels are namespaces, not authenticated identities. All database paths are
fixed below the invocation directory's private-data folder. Lost stdout after a
successful commit cannot undo that turn. Request deduplication is outside scope.
"""

import argparse
import json
import os
import sys

from .domain import TurnRequest, terminal
from .service import Conversation

EXIT_CODES = {"invalid_input": 2, "limit": 3, "storage_error": 4, "cancelled": 130}


class InvalidArguments(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def print_help(self, file=None):
        # argparse suppresses write errors internally. Help must share our output failure contract.
        stream = file if file is not None else sys.stdout
        stream.write(self.format_help())

    def error(self, message):
        # argparse's ordinary error includes raw arguments. Keep the boundary output fixed.
        raise InvalidArguments()


def _execute(argv: list[str] | None = None) -> int:
    parser = Parser(description="Synthetic deterministic course guide")
    commands = parser.add_subparsers(dest="command", required=True)
    turn = commands.add_parser("turn")
    forget = commands.add_parser("forget")
    for command in (turn, forget):
        command.add_argument("--workspace", default="demo")
        command.add_argument("--user", required=True)
    turn.add_argument("--session", required=True)
    turn.add_argument("--message", required=True)
    try:
        args = parser.parse_args(argv)
        service = Conversation(args.workspace)
        result = service.turn(TurnRequest(args.user, args.session, args.message)) if args.command == "turn" else service.forget(args.user)
    except InvalidArguments:
        result = terminal("invalid_input", "Course guide: Supply turn or forget with its required options.", "persistence:not_accessed")
    except KeyboardInterrupt:
        result = terminal("cancelled", "Course guide: Processing was cancelled.", "persistence:rolled_back")
    print(json.dumps(result.as_dict(), ensure_ascii=True))
    return EXIT_CODES.get(result.status, 0)


def main(argv: list[str] | None = None) -> int:
    """Own stdout delivery for both argparse help and ordinary JSON results."""
    try:
        try:
            exit_code = _execute(argv)
        except SystemExit as end:
            if end.code != 0:
                raise
            exit_code = 0
        sys.stdout.flush()
        return exit_code
    except (BrokenPipeError, OSError):
        # Buffered bytes must not trigger a second failed flush during interpreter teardown.
        try:
            with open(os.devnull, "w") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        except (OSError, ValueError):
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
