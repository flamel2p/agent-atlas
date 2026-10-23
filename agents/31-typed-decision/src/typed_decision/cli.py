"""Actual CLI. Explicit input files enter strict boundaries; output is local JSON.

Exit codes are 0 for decision/abstention, 2 for invalid input/output, 3 for
backend/output failure, 4 for timeout, and 130 for cancellation. Argument errors
never echo untrusted arguments. Help and results flush inside the output guard.
"""

import argparse
import os
import sys
from importlib.resources import files

from .contracts import Policy, Result
from .json_boundary import Invalid, loads, number, read_file
from .runtime import predict

EXIT_CODES = {"decision": 0, "abstention": 0, "invalid_input": 2,
              "invalid_output": 2, "backend_failure": 3, "timeout": 4, "cancellation": 130}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Invalid("invalid_arguments")

    def _print_message(self, message, file=None):
        # argparse suppresses OSError from help writes. Let the shared output
        # guard observe failures in unbuffered mode as well as buffered flushes.
        if message:
            (file if file is not None else sys.stderr).write(message)


def _run() -> int:
    parser = Parser(description="Validate synthetic typed-decision mechanics. No model inference.",
                    allow_abbrev=False)
    parser.add_argument("--request", help="Explicit regular UTF-8 JSON request file")
    parser.add_argument("--fixture", help="Explicit regular synthetic fixture JSON file")
    parser.add_argument("--threshold", default="0.6", help="Host concentration threshold [0,1]")
    parser.add_argument("--timeout", default="2", help="Host timeout in seconds [0.05,10]")
    try:
        if len(sys.argv) > 16 or any(len(arg) > 4096 for arg in sys.argv):
            raise Invalid("argument_limit")
        args = parser.parse_args()
        policy = Policy(number(args.threshold), float(number(args.timeout))).checked()
        try:
            request_path = args.request if args.request else files("typed_decision").joinpath("data/request.json")
            request_bytes = read_file(request_path)
            request = loads(request_bytes)
        except Invalid:
            result = Result(None, "invalid_input", "request_file_or_json")
        else:
            try:
                fixture_path = args.fixture if args.fixture else files("typed_decision").joinpath("data/decision.json")
                fixture_bytes = read_file(fixture_path)
                fixture = loads(fixture_bytes)
            except Invalid:
                result = Result(None, "invalid_output", "fixture_file_or_json")
            else:
                result = predict(request, fixture=fixture, policy=policy)
    except (Invalid, ValueError, OverflowError):
        result = Result(None, "invalid_input", "invalid_arguments")
    except KeyboardInterrupt:
        result = Result(None, "cancellation", "interrupted")
    except OSError:
        result = Result(None, "backend_failure", "resource_unavailable")
    sys.stdout.buffer.write((result.to_json() + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()
    return EXIT_CODES[result.status]


def main() -> int:
    try:
        try:
            return _run()
        except SystemExit as exc:
            # argparse help writes through stdout before returning SystemExit.
            sys.stdout.flush()
            return exc.code
    except OSError as error:
        # Redirect before shutdown so a failed buffered flush cannot replace
        # the intended exit code with Python's shutdown-flush error code 120.
        fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(fd, sys.stdout.fileno())
        os.close(fd)
        return 0 if isinstance(error, BrokenPipeError) else 3
