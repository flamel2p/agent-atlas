"""Bounded strict JSON CLI. Invalid input never reaches the policy dispatcher.

One JSON result is written to stdout. Fixed error codes avoid echoing paths,
untrusted strings, or personal values. No provider or environment configuration
exists. The file read and stdin read both enforce the same byte bound.
"""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from .domain import InputError, POLICY_VERSION, Request, SCHEMA_VERSION, parse_request
from .engine import Status, run

MAX_BYTES = 16_384
MAX_DEPTH = 12


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate_key")
        result[key] = value
    return result


def _reject_number(_: str) -> None:
    raise InputError("invalid_number")


def _check_depth(raw: str) -> None:
    depth = 0
    in_string = False
    escaped = False
    for char in raw:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise InputError("nesting_limit")
        elif char in "]}":
            depth -= 1


def decode(raw: bytes) -> Request:
    """Decode one size/depth-bounded document and construct the validated domain."""

    if len(raw) > MAX_BYTES:
        raise InputError("input_size_limit")
    try:
        source = raw.decode("utf-8")
        _check_depth(source)
        value = json.loads(source, object_pairs_hook=_pairs,
                           parse_float=_reject_number, parse_constant=_reject_number)
        return parse_request(value)
    except InputError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise InputError("malformed_json") from exc


def failure(status: str, code: str) -> dict:
    return {"schema_version": SCHEMA_VERSION, "policy_version": POLICY_VERSION,
            "status": status, "action": None, "events": [], "effects": [],
            "review": None, "error": {"code": code}}


def _write(text: str) -> int:
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
        return 0
    except KeyboardInterrupt:
        return 130
    except OSError:
        # Failed buffered output must not be flushed again during interpreter exit.
        try:
            descriptor = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(descriptor, sys.stdout.fileno())
            finally:
                os.close(descriptor)
        except OSError:
            pass
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate one synthetic policy request.")
    parser.add_argument("request", help="UTF-8 JSON file, or - for stdin")
    arguments = list(sys.argv[1:] if argv is None else argv)
    # argparse suppresses some help-write failures, so help uses the result boundary.
    if "--help" in arguments or "-h" in arguments:
        return _write(parser.format_help())
    args = parser.parse_args(arguments)
    try:
        if args.request == "-":
            raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        else:
            with Path(args.request).open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
        result = run(decode(raw))
        output = asdict(result)
        code = 0 if result.status == Status.COMPLETED else 3
    except InputError as exc:
        output, code = failure("invalid_input", str(exc)), 2
    except OSError:
        output, code = failure("invalid_input", "input_io_error"), 2
    except KeyboardInterrupt:
        output, code = failure("cancelled", "interrupted"), 130
    return _write(json.dumps(output, sort_keys=True, allow_nan=False) + "\n") or code
