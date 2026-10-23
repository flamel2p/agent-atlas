"""CLI authority adapter for fixed data, one optional file, and stdout reports.

The domain owns all recommendation policy. This adapter owns strict argument
handling, package-resource reads, sanitized failures, and explicit output flush.
No error includes a raw argument, path, request value, or traceback.
"""

import argparse
import json
import sys

from .documents import InputError, ResourceError, read_request, read_resource
from .domain import recommend

_SCENARIOS = ("normal", "cold-start", "no-match", "constrained", "no-eligible")


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InputError()

    def exit(self, status: int = 0, message: str | None = None) -> None:
        # Help has the same explicit output-failure behavior as reports.
        sys.stdout.flush()
        raise SystemExit(status)


def _error(code: str, message: str) -> None:
    if sys.stderr is None:
        return
    try:
        sys.stderr.write(json.dumps({"error": {"code": code, "message": message}}) + "\n")
        sys.stderr.flush()
    except (OSError, ValueError, UnicodeError):
        sys.stderr = None


def main(argv: list[str] | None = None) -> int:
    """Run once. Valid outcomes return 0, invalid input 2, and I/O failures 1."""
    parser = _Parser(
        description="Recommend synthetic exercises from explicit interests and constraints.",
        allow_abbrev=False,
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--scenario", choices=_SCENARIOS, help="packaged request, defaults to normal")
    source.add_argument("--request", metavar="PATH", help="one UTF-8 JSON regular file")
    try:
        # CPython uses None when the inherited stdout descriptor is closed.
        # Check before argparse can redirect help text to another stream.
        if sys.stdout is None:
            raise OSError("stdout is unavailable")
        args = parser.parse_args(argv)
        catalogue = read_resource("catalogue.json")
        request = (read_request(args.request) if args.request is not None
                   else read_resource(f"scenarios/{args.scenario or 'normal'}.json"))
        output = json.dumps(recommend(request, catalogue), ensure_ascii=True, allow_nan=False, sort_keys=True) + "\n"
        sys.stdout.write(output)
        # Flush inside the guarded operation. Otherwise a buffered broken pipe
        # can fail at interpreter shutdown after main already returned success.
        sys.stdout.flush()
        return 0
    except InputError:
        _error("invalid_input", "Input does not satisfy the recommendation contract.")
        return 2
    except ResourceError:
        _error("resource_unavailable", "A packaged input could not be read.")
        return 1
    except (OSError, ValueError, UnicodeError):
        # Removing the failed stream prevents another shutdown flush, including
        # Python's otherwise noisy buffered BrokenPipeError traceback.
        sys.stdout = None
        _error("output_unavailable", "The report could not be written.")
        return 1
    except KeyboardInterrupt:
        _error("interrupted", "The run was interrupted.")
        return 130
