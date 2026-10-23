"""Bounded file-to-JSON CLI. Host code owns input access and all stdout writes.

No caller strings appear in errors. Inputs must be regular files and final-path
symlinks are refused. Buffered output is explicitly flushed inside the handler,
so a closed pipe cannot cause an interpreter-shutdown traceback.
"""

from importlib.resources import files
import json
import os
import stat
import sys

from .core import InvalidInput, MAX_BYTES, parse_request, run

HELP = "Usage: education-demo [--input PATH | --help]\nNo arguments runs the packaged synthetic session.\n"


def read_input(path: str) -> bytes:
    if len(path) > 4096:
        raise InvalidInput("invalid_arguments")
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise InvalidInput("input_unavailable")
        if info.st_size > MAX_BYTES:
            raise InvalidInput("bound_exceeded")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise InvalidInput("bound_exceeded")
        return raw
    except (OSError, ValueError, UnicodeError):
        raise InvalidInput("input_unavailable") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _discard_stdout() -> None:
    # Both broken pipes and ordinary descriptor errors can retain buffered bytes.
    try:
        sink = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(sink, sys.stdout.fileno())
        finally:
            os.close(sink)
    except OSError:
        pass


def emit(value: str, code: int) -> int:
    try:
        sys.stdout.write(value)
        sys.stdout.flush()
        return code
    except BrokenPipeError:
        _discard_stdout()
        return 0
    except OSError:
        _discard_stdout()
        return 2


def main() -> int:
    try:
        arguments = sys.argv[1:]
        if arguments == ["--help"]:
            return emit(HELP, 0)
        if not arguments:
            raw = files("education_intelligence").joinpath("fixtures/session.json").read_bytes()
        elif len(arguments) == 2 and arguments[0] == "--input" and not arguments[1].startswith("--"):
            raw = read_input(arguments[1])
        else:
            raise InvalidInput("invalid_arguments")
        report = run(parse_request(raw)).record()
        code = 0
    except InvalidInput as error:
        report = {"status": "invalid_input", "error": error.code}
        code = 2
    except KeyboardInterrupt:
        report = {"status": "cancelled"}
        code = 130
    except OSError:
        report = {"status": "invalid_input", "error": "input_unavailable"}
        code = 2
    return emit(json.dumps(report, allow_nan=False, ensure_ascii=True, separators=(",", ":")) + "\n", code)
