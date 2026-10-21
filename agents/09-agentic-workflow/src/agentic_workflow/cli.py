"""Bounded JSON CLI for one explicit host command per process invocation.

Argument parsing and file-size limits are external boundaries. The CLI delegates
all state transitions to Store; caller text is data, including reviewer labels.
Those labels demonstrate policy guards but do not authenticate a human operator.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .domain import InputError, MAX_FILE_BYTES, Profile, RequestInput
from .store import Store, WorkflowError


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InputError(message)


def parser() -> Parser:
    root = Parser(prog="agentic-workflow", description=(
        "Durable synthetic equipment workflow. Reviewer labels are attribution, "
        "not authentication."))
    commands = root.add_subparsers(dest="operation", required=True, parser_class=Parser)
    for name in ("init", "submit", "advance", "review", "cancel", "show", "audit"):
        sub = commands.add_parser(name)
        sub.add_argument("--db", type=Path, default=Path("state/workflow.sqlite"),
                         help="SQLite path (default: ./state/workflow.sqlite)")
        if name == "submit":
            sub.add_argument("file", type=Path, help="strict request JSON file, maximum 16 KiB")
            sub.add_argument("--profile", choices=[p.value for p in Profile], default="success")
        elif name not in {"init"}:
            sub.add_argument("request_id")
        if name in {"submit", "advance", "review", "cancel"}:
            sub.add_argument("--command-id", required=True)
        if name == "review":
            sub.add_argument("--decision", choices=("approve", "reject"), required=True)
            sub.add_argument("--reviewer", required=True,
                             help="synthetic allowlisted label; not authenticated identity")
            sub.add_argument("--reason", required=True)
            sub.add_argument("--expected-version", type=int, required=True)
        if name == "cancel":
            sub.add_argument("--reason", required=True)
    return root


def run(argv: list[str] | None = None) -> dict:
    args = parser().parse_args(argv)
    store = Store(args.db)
    match args.operation:
        case "init":
            return store.init()
        case "submit":
            try:
                with args.file.open("rb") as stream:
                    content = stream.read(MAX_FILE_BYTES + 1)
            except OSError as exc:
                raise WorkflowError("input_file_error", str(exc)) from exc
            request = RequestInput.from_json_bytes(content)
            return store.submit(request, Profile(args.profile), args.command_id)
        case "advance":
            return store.advance(args.request_id, args.command_id)
        case "review":
            return store.review(args.request_id, args.command_id, decision=args.decision,
                                reviewer=args.reviewer, review_reason=args.reason,
                                expected_version=args.expected_version)
        case "cancel":
            return store.cancel(args.request_id, args.command_id, cancel_reason=args.reason)
        case "show":
            return store.show(args.request_id)
        case "audit":
            return store.audit(args.request_id)
    raise AssertionError("argparse supplied an unknown operation")


def main(argv: list[str] | None = None) -> int:
    try:
        response = run(argv)
    except (InputError, WorkflowError) as exc:
        code = exc.code if isinstance(exc, WorkflowError) else "invalid_input"
        print(json.dumps({"code": code, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(response, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
