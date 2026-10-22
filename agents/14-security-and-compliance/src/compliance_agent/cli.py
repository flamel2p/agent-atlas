"""Read one bounded snapshot and emit one deterministic JSON record.

Only fixed packaged resources or stdin can supply bytes. Argument text never
becomes a path or report value. Source proposals have no runtime tool authority.
Operational errors use fixed messages so exceptions cannot disclose source data.
"""

from importlib.resources import files
import io
import json
import sys
from typing import BinaryIO, TextIO

from .assessor import MAX_SOURCE_BYTES, SCHEMA_VERSION, assess
from .policy import MAX_POLICY_BYTES, PolicyError, decode_policy

SCENARIOS = (
    "clean", "blocked", "alias", "ambiguous", "mixed", "reassigned",
    "unsupported", "masking", "prior-block", "syntax-error",
)
EXIT_CODES = {"passed": 0, "blocked": 1, "review_required": 2}
ERROR_MESSAGES = {
    "invalid_usage": "Select one supported scenario, --stdin, or --list-scenarios.",
    "policy_invalid": "The bundled policy failed validation.",
    "policy_unavailable": "The bundled policy could not be read.",
    "scenario_unavailable": "The selected bundled scenario could not be read.",
    "input_read_failed": "The input could not be read.",
    "operational_failure": "The assessment could not be completed.",
    "cancelled": "The assessment was interrupted.",
}


class CliFailure(Exception):
    def __init__(self, code: str):
        self.code = code


def _resource(name: str, limit: int, error_code: str) -> bytes:
    try:
        with files("compliance_agent").joinpath("resources", name).open("rb") as stream:
            return stream.read(limit + 1)
    except OSError:
        raise CliFailure(error_code) from None


def _invoke(argv: list[str], stdin: BinaryIO | None) -> tuple[dict[str, object], int]:
    if argv == ["--list-scenarios"]:
        return {"schema_version": SCHEMA_VERSION, "scenarios": list(SCENARIOS)}, 0
    use_stdin = argv == ["--stdin"]
    use_scenario = len(argv) == 2 and argv[0] == "--scenario" and argv[1] in SCENARIOS
    if not use_stdin and not use_scenario:
        raise CliFailure("invalid_usage")
    policy = decode_policy(_resource("policy.json", MAX_POLICY_BYTES, "policy_unavailable"))
    if use_stdin:
        if stdin is None:
            raise CliFailure("input_read_failed")
        try:
            raw = stdin.read(MAX_SOURCE_BYTES + 1)
        except (OSError, ValueError):
            raise CliFailure("input_read_failed") from None
    else:
        raw = _resource(f"scenarios/{argv[1]}.py.txt", MAX_SOURCE_BYTES, "scenario_unavailable")
    assessment = assess(raw, policy)
    return assessment.to_dict(), EXIT_CODES[assessment.status]


def main(argv: list[str] | None = None, *, stdin: BinaryIO | None = None, stdout: TextIO | None = None) -> int:
    """CLI entry point with injectable streams for operational-failure checks.

    The caller owns stdout and any redirected file. There are no retries or
    writes elsewhere. Failed runs never contain a partial policy assessment.
    """
    try:
        record, exit_code = _invoke(sys.argv[1:] if argv is None else argv, getattr(sys.stdin, "buffer", None) if stdin is None else stdin)
    except KeyboardInterrupt:
        code, exit_code = "cancelled", 130
    except PolicyError:
        code, exit_code = "policy_invalid", 3
    except CliFailure as error:
        code, exit_code = error.code, 3
    except Exception:
        # This last boundary prevents unforeseen operational errors from printing
        # source-bearing tracebacks. It does not convert failure into a decision.
        code, exit_code = "operational_failure", 3
    else:
        code = None
    if code is not None:
        record = {"schema_version": SCHEMA_VERSION, "status": "failed", "error": {"code": code, "message": ERROR_MESSAGES[code]}}
    try:
        output = sys.stdout if stdout is None else stdout
        if output is None:
            return 3
        output.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        output.flush()
    except (OSError, ValueError):
        # A failed output channel cannot carry a second error record. Exit without
        # retrying the write. Replace failed process stdout with an in-memory sink
        # so interpreter shutdown cannot retry flushing it and print a traceback.
        if stdout is None:
            sys.stdout = io.StringIO()
        return 3
    return exit_code
