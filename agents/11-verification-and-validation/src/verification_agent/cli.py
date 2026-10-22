"""POSIX command boundary with bounded reads and complete report construction.

Exit 0 means a report or requested help, not a favorable verdict. No report bytes
are written until validation, verification, and serialization finish. A broken
pipe can truncate output; the process exits 1 and creates no persistent artifact.
"""

import json
import sys

from .domain import InputError, SourceError
from .files import REQUEST_LIMIT, read_regular
from .verifier import verify_document


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    try:
        if arguments == ["--help"]:
            output = "usage: verification-agent FILE\nVerify structured claims against fixed bundled synthetic evidence.\n"
        elif len(arguments) != 1 or arguments[0].startswith("-"):
            raise InputError("invalid_arguments")
        else:
            document = read_regular(arguments[0], REQUEST_LIMIT, InputError)
            report = verify_document(document)
            output = json.dumps(report.as_dict(), indent=2, ensure_ascii=True, allow_nan=False) + "\n"
        sys.stdout.write(output)
        sys.stdout.flush()
        return 0
    except InputError as error:
        sys.stderr.write(f"input_error:{error.code}\n")
        return 2
    except SourceError as error:
        sys.stderr.write(f"source_error:{error.code}\n")
        return 3
    except KeyboardInterrupt:
        sys.stderr.write("interrupted\n")
        return 130
    except BrokenPipeError:
        # Discard the failed stream so interpreter shutdown cannot retry its flush.
        sys.stdout = None
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
