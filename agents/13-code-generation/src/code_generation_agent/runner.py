"""Bounded refinement loop and terminal publication owned by the host.

The developer is a proposal-only collaborator. Its immutable feedback cannot
change the oracle, evaluator, limits, or paths. Every invocation consumes one
attempt. Completed attempt records survive subsequent failures. A final report,
not an attempt file or temporary report, grants accepted-source authority.
"""

from dataclasses import replace
from pathlib import Path

from .artifacts import ArtifactError, ArtifactStore, InvalidInput, validate_workspace
from .developer import Developer, FixtureDeveloper
from .domain import (
    Attempt, Feedback, ORACLE_DIGEST, RunResult, SCENARIOS, SPECIFICATION,
    SPECIFICATION_DIGEST, Status, digest,
)
from .interpreter import Rejected, check_candidate, source_bytes


def run(
    scenario: str = "repair", max_attempts: int = 3, *,
    workspace: Path | str | None = None, developer: Developer | None = None,
    run_id: str | None = None,
) -> RunResult:
    """Run one fixture workflow; caller errors precede proposals and writes.

    developer and run_id are host integration/test seams, never candidate inputs.
    No credentials, provider, or persistent service is accessed.
    """
    if type(scenario) is not str or scenario not in SCENARIOS:
        raise InvalidInput("scenario")
    if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise InvalidInput("max_attempts")
    root = validate_workspace(Path.cwd() if workspace is None else workspace)
    proposer = FixtureDeveloper(scenario) if developer is None else developer
    history: list[Attempt] = []
    count = 0
    status = Status.EXHAUSTED
    error_code = None
    store = None
    try:
        store = ArtifactStore(root, run_id)
        for number in range(1, max_attempts + 1):
            count = number
            prior = tuple(attempt.feedback for attempt in history)
            source = None
            try:
                candidate = proposer.propose(SPECIFICATION, prior)
                source_bytes(candidate)
                source = candidate
                feedback = check_candidate(source)
            except Rejected as error:
                status, error_code = Status.FAILED, "developer_contract"
                feedback = Feedback("developer_error", error.code)
            except KeyboardInterrupt:
                status, error_code = Status.CANCELLED, "interrupted"
                feedback = Feedback("cancelled", error_code)
            except Exception:
                status, error_code = Status.FAILED, "developer_or_host_error"
                feedback = Feedback("host_error", error_code)
            attempt = Attempt(
                number, digest(source) if source is not None else None,
                f"attempt-{number}/candidate.txt" if source is not None else None,
                prior, feedback,
            )
            store.record(attempt, source)
            history.append(attempt)
            if status in (Status.FAILED, Status.CANCELLED):
                break
            if feedback.passed:
                status = Status.COMPLETED
                break
    except InvalidInput:
        raise
    except KeyboardInterrupt:
        status, error_code = Status.CANCELLED, "interrupted"
    except ArtifactError:
        status, error_code = Status.FAILED, "artifact_error"
    except Exception:
        status, error_code = Status.FAILED, "host_error"

    selected = history[-1].source_artifact if status == Status.COMPLETED else None
    result = RunResult(
        status, count, tuple(history), SPECIFICATION_DIGEST, ORACLE_DIGEST,
        str(store.directory) if store is not None else None,
        str(store.directory / "report.json") if store is not None else None,
        selected, error_code,
    )
    if store is None:
        return result
    try:
        store.publish(result)
    except KeyboardInterrupt:
        if store.published:
            return result
        cancelled = replace(result, status=Status.CANCELLED, accepted_source=None, error="interrupted")
        # A pre-publication interrupt may leave a temporary file. It is never
        # authoritative; retry only after removing this host-owned temporary.
        try:
            (store.directory / ".report.tmp").unlink(missing_ok=True)
            store.publish(cancelled)
            return cancelled
        except (Exception, KeyboardInterrupt):
            return cancelled if store.published else replace(cancelled, report_path=None)
    except Exception:
        if store.published:
            return result
        return replace(result, status=Status.FAILED, accepted_source=None, report_path=None, error="report_write")
    return result
