"""Read one bounded dataset, call the analysis boundary, and optionally publish.

File authority belongs here. Inputs are read-only regular files with no symlink
leaf. Output requires an existing parent and a new, exclusively created leaf
directory with no symlink ancestors. This ownership rule prevents competing
invocations from overwriting each other. Cleanup touches only files created by
this invocation. It is caught-failure cleanup, not crash-atomic publication or a
defense against a hostile process changing filesystem entries concurrently.
"""

import argparse
import os
import signal
import stat
from contextlib import ExitStack, contextmanager
from importlib.resources import files
from pathlib import Path

from .analysis import analyze, parse_question
from .domain import BUILTIN_SOURCE, MAX_BYTES, Completed, Failure, InvalidDataset, NeedsClarification, Outcome
from .rendering import outcome_json, render_svg


_EXIT_CODES = {"completed": 0, "needs_clarification": 2, "no_data": 2, "invalid_dataset": 3, "input_error": 3, "output_error": 3, "cancelled": 130}


def read_dataset(path: Path | None) -> tuple[bytes, str]:
    """Read at most the dataset limit plus one sentinel byte, without FIFO hangs."""
    if path is None:
        resource = files("data_analysis_agent").joinpath("data/quarterly_activity.csv")
        with resource.open("rb") as stream:
            contents = stream.read(MAX_BYTES + 1)
        return contents, BUILTIN_SOURCE
    if not stat.S_ISREG(path.lstat().st_mode):
        raise OSError("The dataset must be a regular file and cannot be a symlink leaf.")
    # NOFOLLOW checks the opened leaf too. NONBLOCK prevents a FIFO replacement
    # between lstat and open from hanging before fstat can reject its type.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise OSError("The opened dataset is not a regular file.")
        if info.st_size > MAX_BYTES:
            raise InvalidDataset("Dataset exceeds 256 KiB.")
        contents = stream.read(MAX_BYTES + 1)
    if len(contents) > MAX_BYTES:
        raise InvalidDataset("Dataset exceeds 256 KiB.")
    return contents, f"file:{path}"


@contextmanager
def _defer_sigint():
    """Deliver CLI Ctrl-C after filesystem ownership and stream closure are known.

    The CLI runs on the main thread. A temporary handler covers only acquisition,
    so a signal between a successful syscall and cleanup registration cannot
    strand output. Actual writes stay interruptible. This does not make arbitrary
    tracer-injected Python exceptions or process termination atomic.
    """
    pending = False

    def remember_interrupt(_signum, _frame):
        nonlocal pending
        pending = True

    previous = signal.signal(signal.SIGINT, remember_interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)
        if pending:
            raise KeyboardInterrupt


def publish(destination: Path, report_json: str, chart_svg: str) -> None:
    """Exclusively own a new directory and clean up on caught write failures.

    Parents must exist. Do not resolve symlinks before validation: doing so would
    hide the very traversal this policy rejects. Existing destinations, including
    dangling symlinks, fail unchanged. Never recursively remove an output tree.
    """
    destination = destination.absolute()
    for parent in reversed(destination.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise OSError("Output parents must be existing directories without symlinks.")
    owned_files: list[Path] = []
    owns_directory = False
    try:
        with _defer_sigint():
            destination.mkdir()
            owns_directory = True
        for name, contents in (("report.json", report_json), ("chart.svg", chart_svg)):
            path = destination / name
            with ExitStack() as streams:
                with _defer_sigint():
                    stream = streams.enter_context(path.open("x", encoding="utf-8", newline="\n"))
                    owned_files.append(path)
                stream.write(contents)
    except BaseException as error:
        if not owns_directory:
            raise
        cleanup_failed = False
        for path in reversed(owned_files):
            try:
                path.unlink()
            except OSError:
                cleanup_failed = True
        try:
            destination.rmdir()
        except OSError:
            cleanup_failed = True
        if cleanup_failed and isinstance(error, (OSError, KeyboardInterrupt)):
            message = "Artifact publication stopped; cleanup was incomplete. Inspect the destination before removing or reusing it."
            if isinstance(error, KeyboardInterrupt):
                raise KeyboardInterrupt(message) from None
            raise OSError(message) from None
        raise


def _run(args: argparse.Namespace) -> Outcome:
    plan = parse_question(args.question)
    if isinstance(plan, NeedsClarification):
        return plan
    try:
        contents, source_label = read_dataset(args.dataset)
    except InvalidDataset as error:
        return Failure("invalid_dataset", str(error))
    except (OSError, ValueError):
        return Failure("input_error", "Cannot read dataset: select a readable regular file without a symlink leaf.")
    outcome = analyze(args.question, contents, source_label)
    if isinstance(outcome, Completed) and args.output is not None:
        report_json, chart_svg = outcome_json(outcome), render_svg(outcome.report.chart)
        try:
            publish(args.output, report_json, chart_svg)
        except (OSError, ValueError) as error:
            message = "Cannot publish artifacts: use a new directory under existing, writable parents without symlinks."
            if "cleanup was incomplete" in str(error):
                message += " Cleanup was incomplete; inspect the destination before reuse."
            return Failure("output_error", message)
    return outcome


def main(argv: list[str] | None = None) -> int:
    """CLI terminal statuses are JSON; argparse retains its own option-error exit 2."""
    parser = argparse.ArgumentParser(description="Analyze observed product/date records using a constrained, deterministic question grammar.")
    parser.add_argument("--question", required=True, help="top N products by METRIC, monthly METRIC, or describe METRIC; then from YYYY-MM-DD to YYYY-MM-DD")
    parser.add_argument("--dataset", type=Path, help="UTF-8 CSV; defaults to packaged synthetic Q3 2026 activity")
    parser.add_argument("--output", type=Path, help="New artifact directory under existing parents; default writes no files")
    try:
        outcome = _run(parser.parse_args(argv))
    except KeyboardInterrupt as error:
        outcome = Failure("cancelled", str(error) or "Analysis cancelled.")
    print(outcome_json(outcome), end="")
    return _EXIT_CODES[outcome.status]


if __name__ == "__main__":
    raise SystemExit(main())
