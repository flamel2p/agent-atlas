"""Strict bounded JSON boundary for classification and explanation replay.

This module alone reads files or stdin. It accepts one explicit regular file,
rejects final symlinks and FIFOs, and never writes state or invokes a provider.
Expected failures expose only stable codes. The policy and release gate remain
pure and determine whether a priority may appear at the top level.
"""

import json
import math
import os
import stat
import sys
from collections.abc import Sequence

from .contracts import ContractError
from .decision import classify, load_trace, parse_request
from .explanation import explain, outcome_to_dict, unavailable

MAX_BYTES = 32768
MAX_DEPTH = 16
HELP = "Usage: explainable {classify|explain} INPUT.json\nUse - as INPUT.json to read stdin.\n"


def read_input(path: str) -> bytes:
    """Bound reads before decoding. Explicit paths do not authorize other IO."""
    try:
        if path == "-":
            content = sys.stdin.buffer.read(MAX_BYTES + 1)
        else:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise ContractError("input_unreadable")
                # Regular-file reads are bounded even if the file grows after stat.
                content = b""
                while len(content) <= MAX_BYTES:
                    part = os.read(descriptor, MAX_BYTES + 1 - len(content))
                    if not part:
                        break
                    content += part
            finally:
                os.close(descriptor)
    except (OSError, ValueError):
        raise ContractError("input_unreadable") from None
    if len(content) > MAX_BYTES:
        raise ContractError("input_too_large")
    return content


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("json_invalid")
        result[key] = value
    return result


def _nonfinite(_: str) -> None:
    raise ContractError("json_invalid")


def parse_json(content: bytes) -> object:
    """Reject ambiguous JSON rather than silently choosing a duplicate field."""
    if len(content) > MAX_BYTES:
        raise ContractError("input_too_large")
    try:
        value = json.loads(content.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_nonfinite)
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            if depth > MAX_DEPTH or (type(item) is float and not math.isfinite(item)):
                raise ContractError("json_invalid")
            if type(item) is dict:
                pending.extend((child, depth + 1) for child in item.values())
            elif type(item) is list:
                pending.extend((child, depth + 1) for child in item)
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise ContractError("json_invalid") from None


def _write(text: str) -> int:
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
        return 0
    except KeyboardInterrupt:
        return 130
    except OSError:
        # Redirect the stream so interpreter shutdown cannot repeat the failed flush.
        try:
            descriptor = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(descriptor, sys.stdout.fileno())
            finally:
                os.close(descriptor)
        except OSError:
            pass
        return 2


def main(argv: Sequence[str] | None = None) -> int:
    """Write one safe JSON result. Completion is exit 0, review is exit 2."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args in (["--help"], ["-h"]):
        return _write(HELP)
    exit_code = 2
    try:
        if len(args) != 2 or args[0] not in ("classify", "explain"):
            raise ContractError("command_invalid")
        raw = parse_json(read_input(args[1]))
        trace = classify(parse_request(raw)) if args[0] == "classify" else load_trace(raw)
        outcome = explain(trace)
        exit_code = 0 if outcome.status == "completed" else 2
    except ContractError as error:
        outcome = unavailable(error.code)
    except KeyboardInterrupt:
        outcome = unavailable("cancelled")
        exit_code = 130
    return _write(json.dumps(outcome_to_dict(outcome), ensure_ascii=True,
                            allow_nan=False, separators=(",", ":")) + "\n") or exit_code
