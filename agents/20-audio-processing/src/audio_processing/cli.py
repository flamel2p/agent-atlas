"""Own POSIX input authority and publish one bounded JSON report.

The CLI opens only the requested file, rejects special descriptors before any
read, then calls the fixed-resource facade. No report file, provider call,
retry, or persistent state is created. Flushing stdout is part of success.
"""

import argparse
import json
import os
import stat
import sys

from . import FIXTURE_IDS, Mode, Rejected, analyze, analyze_fixture
from .core import MAX_INPUT_BYTES, Outcome


class _Parser(argparse.ArgumentParser):
    def print_help(self, file=None) -> None:
        # argparse normally suppresses write errors and falls back to stderr
        # when stdout is absent. Help must obey the same output contract as JSON.
        stream = sys.stdout if file is None else file
        if stream is None:
            raise OSError("Standard output is unavailable.")
        stream.write(self.format_help())

    def error(self, _message: str) -> None:
        # argparse's normal diagnostic can echo an arbitrary path or raw token.
        self.print_usage(sys.stderr)
        self.exit(2, "audio-processing: invalid arguments; use --help.\n")


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="audio-processing",
        description="Measure PCM16 WAV with explicitly simulated fixture replay.",
        allow_abbrev=False,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixture", choices=FIXTURE_IDS)
    source.add_argument("--input", metavar="PATH")
    parser.add_argument("--mode", choices=tuple(mode.value for mode in Mode), default="clean")
    return parser


def read_input(path: str) -> bytes | Rejected:
    """Read at most the cap plus one byte from a verified regular descriptor.

    O_NOFOLLOW rejects the final symlink atomically. O_NONBLOCK makes opening a
    FIFO safe before fstat can reject it. Parent symlinks remain allowed because
    this reader does not claim filesystem sandboxing.
    """
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            return Rejected("invalid_input", "Input must be a regular file.")
        if info.st_size > MAX_INPUT_BYTES:
            return Rejected("invalid_input", "Input exceeds the byte limit.")
        chunks = []
        total = 0
        while total <= MAX_INPUT_BYTES:
            part = os.read(descriptor, MAX_INPUT_BYTES + 1 - total)
            if not part:
                return b"".join(chunks)
            chunks.append(part)
            total += len(part)
        return Rejected("invalid_input", "Input exceeds the byte limit.")
    except (OSError, ValueError):
        return Rejected("invalid_input", "Input cannot be opened or read safely.")
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _diagnostic(message: str) -> None:
    try:
        if sys.stderr is not None:
            sys.stderr.write(message + "\n")
            sys.stderr.flush()
    except (OSError, ValueError):
        pass


def _silence_shutdown_flush() -> None:
    # A failed buffered write can fail again during interpreter shutdown and
    # replace exit 1 with exit 120. Redirect that descriptor without creating a
    # file. A closed/absent stream needs no shutdown flush suppression.
    try:
        descriptor = sys.stdout.fileno() if sys.stdout is not None else None
        if descriptor is not None:
            null_descriptor = os.open(os.devnull, os.O_WRONLY)
            if null_descriptor != descriptor:
                try:
                    os.dup2(null_descriptor, descriptor)
                finally:
                    os.close(null_descriptor)
    except (OSError, ValueError):
        pass


def _output_failure() -> int:
    _silence_shutdown_flush()
    _diagnostic("audio-processing: output could not be written.")
    return 1


def _write_stdout(text: str) -> int:
    """Complete a stdout write and flush before reporting publication success."""
    try:
        if sys.stdout is None:
            return _output_failure()
        sys.stdout.write(text)
        sys.stdout.flush()
    except (OSError, ValueError):
        return _output_failure()
    return 0


def _publish(outcome: Outcome) -> int:
    payload = json.dumps(outcome.to_dict(), ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    if _write_stdout(payload + "\n"):
        return 1
    if isinstance(outcome, Rejected):
        return 3 if outcome.code == "invalid_assets" else 2
    return 0


def main(argv: list[str] | None = None) -> int:
    """Console entry point. Interrupted work cannot report a successful exit."""
    try:
        try:
            args = _parser().parse_args(argv)
        except SystemExit as stopped:
            if stopped.code != 0:
                raise
            # Help's successful argparse exit still owns buffered output. Usage
            # failures retain argparse's exit 2 and stderr diagnostic behavior.
            return _write_stdout("")
        except (OSError, ValueError):
            return _output_failure()
        mode = Mode(args.mode)
        if args.fixture is not None:
            outcome = analyze_fixture(args.fixture, mode)
        else:
            wav_bytes = read_input(args.input)
            outcome = wav_bytes if isinstance(wav_bytes, Rejected) else analyze(wav_bytes, mode)
        return _publish(outcome)
    except KeyboardInterrupt:
        _diagnostic("audio-processing: interrupted.")
        return 130
