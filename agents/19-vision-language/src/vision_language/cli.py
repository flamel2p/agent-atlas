"""Expose one bounded request and report delivery failure independently.

Packaged scene names select PNG resources only. Their names and metadata never
reach perception as truth labels. JSON goes to stdout, and a failed write/flush
returns code 3. Interruptions return 130 without a success report.
"""

import argparse
from importlib.resources import as_file, files
import json
import os
import sys

from .agent import answer_image
from .domain import Invalid, Result

SCENES = ("clear", "occluded", "repeated", "empty", "swapped")
DEFAULT_QUESTION = "How many objects are visible?"


def _stderr(message: str) -> None:
    if sys.stderr is None:
        return
    try:
        sys.stderr.write(message + "\n")
        sys.stderr.flush()
    except (OSError, ValueError, UnicodeError):
        pass


def _silence_stdout() -> None:
    # A second interpreter flush must not turn a handled broken pipe into a
    # traceback or a different exit status. This opens no persistent output.
    try:
        with open(os.devnull, "w") as sink:
            os.dup2(sink.fileno(), sys.stdout.fileno())
    except (OSError, ValueError, AttributeError):
        pass


def main(argv: list[str] | None = None) -> int:
    if sys.stdout is None:
        _stderr("output_failed")
        return 3
    question = DEFAULT_QUESTION
    try:
        parser = argparse.ArgumentParser(description="Answer finite questions about supported rectangular PNG diagrams.")
        source = parser.add_mutually_exclusive_group()
        source.add_argument("--scene", choices=SCENES, help="packaged PNG scene (default: clear)")
        source.add_argument("--image", help="regular local PNG path; no final symlink")
        parser.add_argument("--question", default=DEFAULT_QUESTION, help="finite count or spatial question")
        args = parser.parse_args(argv)
        question = args.question
        if args.image is not None:
            result = answer_image(args.image, question)
        else:
            resource = files("vision_language").joinpath("scenes", f"{args.scene or 'clear'}.png")
            with as_file(resource) as path:
                result = answer_image(path, question)
    except KeyboardInterrupt:
        _stderr("interrupted")
        return 130
    except SystemExit as error:
        try:
            sys.stdout.flush()
        except (OSError, ValueError, UnicodeError):
            _silence_stdout()
            _stderr("output_failed")
            return 3
        return int(error.code)
    except (OSError, ValueError, UnicodeError):
        result = Result(Invalid("operational_error"), question)
    try:
        sys.stdout.write(json.dumps(result.to_dict(), ensure_ascii=True, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    except KeyboardInterrupt:
        _silence_stdout()
        _stderr("interrupted")
        return 130
    except (OSError, ValueError, UnicodeError):
        _silence_stdout()
        _stderr("output_failed")
        return 3
    return {"answered": 0, "uncertain": 1, "unsupported": 1, "invalid": 2}[result.outcome.status]
