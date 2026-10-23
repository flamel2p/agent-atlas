"""Read one bounded regular file, evaluate once, and emit JSON to stdout.

Default input is a packaged original synthetic fixture. The CLI grants no
network, medical, report-file writing, or real review authority. The file reader
opens without following symlinks and uses nonblocking open to reject FIFOs.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
from importlib.resources import files

from .boundary import InputFault, MAX_BYTES, parse_request
from .domain import evaluate


def read_regular(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise InputFault("regular_file_required")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read(MAX_BYTES + 1)
    finally:
        os.close(descriptor)


def _write(text: str) -> int:
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
        return 0
    except KeyboardInterrupt:
        return 130
    except OSError as error:
        # Avoid another interpreter-shutdown flush of the failed descriptor.
        try:
            descriptor = sys.stdout.fileno()
            with open(os.devnull, "w") as sink:
                os.dup2(sink.fileno(), descriptor)
        except (OSError, ValueError):
            pass
        return 1 if isinstance(error, BrokenPipeError) else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fictional evidence and simulated review only.")
    parser.add_argument("--input", type=Path, help="bounded regular JSON file; default packaged fixture")
    arguments = list(sys.argv[1:] if argv is None else argv)
    # argparse can suppress a failed help write, so help shares result output handling.
    if "--help" in arguments or "-h" in arguments:
        return _write(parser.format_help())
    args = parser.parse_args(arguments)
    code = 0
    try:
        path = args.input or Path(str(files("healthcare_intelligence").joinpath("fixtures/normal.json")))
        report = evaluate(parse_request(read_regular(path))).to_json()
    except InputFault as error:
        report = {"mode": "fixture", "outcome": error.outcome, "error": error.code}
        code = 2
    except OSError:
        report = {"mode": "fixture", "outcome": "io_error", "error": "local_io"}
        code = 3
    except KeyboardInterrupt:
        report = {"mode": "fixture", "outcome": "cancelled", "error": "interrupted"}
        code = 130
    return _write(json.dumps(report, sort_keys=True, allow_nan=False) + "\n") or code
