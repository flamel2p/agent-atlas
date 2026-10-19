import argparse
import json

from .agent import ask, exit_code, forget
from .contracts import Failure, Request, STYLES, terminal


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Failure("invalid_input")


def parser() -> Parser:
    result = Parser(description="Synthetic study assistant with explicit scoped memory; replay is offline.")
    subcommands = result.add_subparsers(dest="command", required=True, parser_class=Parser)
    question = subcommands.add_parser("ask", help="Answer using the FAQ and scoped memory")
    question.add_argument("--user", required=True)
    question.add_argument("--session", required=True)
    question.add_argument("--query", required=True)
    question.add_argument("--remember-style", choices=STYLES)
    question.add_argument("--mode", choices=("replay", "live"), default="replay")
    question.add_argument("--store", default="demo")
    deletion = subcommands.add_parser("forget", help="Logically delete only this user's memory")
    deletion.add_argument("--user", required=True)
    deletion.add_argument("--store", default="demo")
    return result


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        if args.command == "forget":
            result = forget(args.user, args.store)
        else:
            result = ask(Request(args.user, args.session, args.query, args.remember_style, args.mode, args.store))
    except Failure as error:
        result = terminal("failed", "unknown", code=error.code)
    except KeyboardInterrupt:
        result = terminal("cancelled", "unknown", code="interrupted")
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return exit_code(result)
