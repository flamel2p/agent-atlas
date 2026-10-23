"""Stdin/stdout transport with sanitized failures and closed-pipe cleanup.

Argument parsing never delegates to argparse's input-echoing diagnostics.
Explicit flush is part of emission, including help. Rebinding descriptor 1 to
/dev/null after write errors prevents Python's buffered shutdown from failing again.
"""

import errno
import json
import os
import sys

from .core import InvalidInput, run_session
from .validation import MAX_BYTES, load_request

HELP = "collective-intelligence\nRead one bounded JSON request from stdin. See SPEC.md for the replay schema.\n"


def _emit(text: str) -> bool:
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
        return True
    except OSError as exc:
        # All output errors can leave buffered bytes for interpreter shutdown.
        descriptor = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(descriptor, sys.stdout.fileno())
        finally:
            os.close(descriptor)
        if exc.errno != errno.EPIPE:
            raise
        return False


def main() -> int:
    try:
        if sys.argv[1:] == ["--help"]:
            _emit(HELP)
            return 0
        if sys.argv[1:]:
            raise InvalidInput("Invalid arguments")
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        report = run_session(load_request(raw)).to_dict()
        code = 0
    except InvalidInput:
        report = {"status": "invalid-input", "error": "Invalid request or arguments."}
        code = 2
    except KeyboardInterrupt:
        report = {"status": "cancelled", "error": "Run cancelled."}
        code = 130
    except Exception:
        report = {"status": "failed", "error": "Internal execution failure."}
        code = 1
    try:
        if not _emit(json.dumps(report, ensure_ascii=True, allow_nan=False,
                                separators=(",", ":")) + "\n"):
            return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
