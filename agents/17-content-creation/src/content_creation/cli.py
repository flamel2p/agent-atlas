"""Parse the read-only CLI boundary and emit one deterministic JSON report.

Exit 0 means both artifacts passed mechanical checks, 1 means a valid brief
remains unapproved, 2 means input/fixture/output failure, and 130 means interrupt.
Output is flushed before success. Broken pipes must not become successful runs.
"""

import argparse
from dataclasses import asdict
import json
import sys
from typing import TextIO

from .boundary import SCENARIOS, load_brief_file, load_scenario
from .domain import FixtureError, InputError, create_content


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's default error repeats caller-supplied argument values.
        raise InputError("Invalid command arguments; use --help for usage.")


def _diagnostic(stream: TextIO, message: str) -> None:
    try:
        stream.write("content-creation: " + message[:180] + "\n")
        stream.flush()
    except (OSError, ValueError):
        pass


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None,
         stderr: TextIO | None = None) -> int:
    output = sys.stdout if stdout is None else stdout
    errors = sys.stderr if stderr is None else stderr
    parser = Parser(description="Compose synthetic content with bounded mechanical review.",
                    allow_abbrev=False)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--scenario", choices=SCENARIOS, default=None)
    selection.add_argument("--brief", metavar="PATH")
    try:
        args = parser.parse_args(argv)
        brief = load_brief_file(args.brief) if args.brief is not None else load_scenario(args.scenario or "launch")
        result = create_content(brief)
        payload = json.dumps(asdict(result), ensure_ascii=True, indent=2, allow_nan=False) + "\n"
        try:
            if output.write(payload) != len(payload):
                raise OSError("Incomplete output write")
            output.flush()
        except (OSError, ValueError):
            _diagnostic(errors, "Unable to write the complete JSON report.")
            # A failed TextIOWrapper flush can retry at interpreter shutdown and
            # replace exit 2 with 120. Close the wrapper and clear stdout so the
            # interpreter cannot retry it. No replacement file is opened.
            if output is sys.stdout:
                try:
                    output.close()
                except (OSError, ValueError):
                    pass
                sys.stdout = None
            return 2
        return 0 if result.status == "validated" else 1
    except (InputError, FixtureError) as error:
        _diagnostic(errors, str(error))
        return 2
    except KeyboardInterrupt:
        _diagnostic(errors, "Interrupted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
