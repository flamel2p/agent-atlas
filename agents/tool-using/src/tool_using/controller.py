from contextlib import suppress
import json
import multiprocessing
from multiprocessing.connection import Connection
import os
from pathlib import Path
import signal
import struct
import time
from typing import Any, Callable
from uuid import uuid4

from .contracts import (
    DATASET_ID, MAX_RESPONSES, MAX_TOOL_ATTEMPTS, MODEL,
    REQUEST_SECONDS, RUN_SECONDS, Failure, RunConfig,
)


def case_directory() -> Path:
    return Path(__file__).absolute().parents[2]


def _check_directory(path: Path, root: Path) -> None:
    if path.is_symlink() or not path.is_dir() or not path.resolve().is_relative_to(root.resolve()):
        raise Failure("artifact_error", phase="artifacts")


def _create_run(root: Path, run_id: str) -> Path:
    if root.is_symlink() or not root.is_dir():
        raise Failure("artifact_error", phase="artifacts")
    artifacts = root / "artifacts"
    artifacts.mkdir(mode=0o700, exist_ok=True)
    _check_directory(artifacts, root)
    run_dir = artifacts / run_id
    run_dir.mkdir(mode=0o700)
    _check_directory(run_dir, root)
    return run_dir


def _open_new(path: Path):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    return os.fdopen(os.open(path, flags, 0o600), "w", encoding="utf-8")


def _worker(
    config: RunConfig, root: Path, run_dir: Path, run_id: str,
    api_key: str | None, connection: Connection, backend_factory: Callable | None,
) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    backend = None
    terminal = None

    def emit(kind: str, **data: Any) -> None:
        connection.send({"kind": kind, "at": time.monotonic(), **data})

    try:
        from .backends import OpenAIBackend, ReplayBackend
        from .tools import ToolSet

        tools = ToolSet(root, run_dir, run_id, config.output_format)
        emit("dataset", sha256=tools.dataset_sha256)
        backend = backend_factory(config) if backend_factory else (
            OpenAIBackend(config, api_key=api_key) if config.mode == "live" else ReplayBackend(config)
        )
        previous = None
        attempts = 0
        for response_number in range(1, MAX_RESPONSES + 1):
            if config.mode == "live":
                emit("request_started")
            try:
                decision = backend.next(previous)
            except Failure:
                metadata = getattr(backend, "last_metadata", None)
                if metadata is not None:
                    emit("backend_response", number=response_number, metadata=metadata)
                raise
            finally:
                if config.mode == "live":
                    emit("request_finished")
            emit("backend_response", number=response_number, metadata=decision.metadata)
            if len(decision.calls) > 1:
                raise Failure("invalid_tool_call", status="rejected", phase="dispatch")
            if not decision.calls:
                summary, chart = tools.finish()
                terminal = {"kind": "success", "summary": summary, "chart": chart}
                break
            if attempts >= MAX_TOOL_ATTEMPTS:
                raise Failure("limit_reached", status="limit_reached", phase="tools")
            attempts += 1
            call = decision.calls[0]
            previous = tools.execute(call.name, call.arguments)
            emit("tool_result", number=attempts, tool=call.name, arguments=tools.last_arguments, result=previous)
        else:
            raise Failure("limit_reached", status="limit_reached", phase="responses")
    except Failure as failure:
        terminal = {"kind": "failure", "status": failure.status, "error": failure.as_dict()}
    except Exception:
        terminal = {"kind": "failure", "status": "failed", "error": Failure("invalid_tool_result").as_dict()}
    finally:
        if backend is not None:
            try:
                backend.close()
            except Exception:
                terminal = {"kind": "failure", "status": "failed", "error": Failure("provider_error", phase="cleanup").as_dict()}
        if terminal is not None:
            with suppress(BrokenPipeError, EOFError, OSError):
                connection.send({"at": time.monotonic(), **terminal})
        connection.close()


def _empty_report(config: RunConfig, run_id: str | None) -> dict:
    return {
        "run_id": run_id, "mode": config.mode, "status": "failed",
        "dataset_id": DATASET_ID, "dataset_sha256": None,
        "requested_format": config.output_format, "intent_validation": "not_performed",
        "summary": None, "chart": None, "error": None,
        "provider": {"requested_model": MODEL, "reported_model": None, "usage": None, "responses": 0} if config.mode == "live" else None,
    }


def error_report(config: RunConfig, failure: Failure) -> dict:
    report = _empty_report(config, None)
    report.update(status=failure.status, error=failure.as_dict())
    return report


def exit_code(report: dict) -> int:
    if report["status"] == "completed":
        return 0
    if report["status"] == "cancelled":
        return 130
    if report["status"] == "rejected" or report["error"]["code"] in {"invalid_input", "missing_credentials"}:
        return 2
    return 1


def _merge_metadata(report: dict, metadata: dict) -> None:
    provider = report["provider"]
    if provider is None:
        return
    provider["responses"] += 1
    if metadata.get("reported_model"):
        provider["reported_model"] = metadata["reported_model"]
    usage = metadata.get("usage")
    if isinstance(usage, dict) and all(type(usage.get(key)) is int and usage[key] >= 0 for key in ("input_tokens", "output_tokens", "total_tokens")):
        if provider["usage"] is None:
            provider["usage"] = {key: 0 for key in ("input_tokens", "output_tokens", "total_tokens")}
        for key in provider["usage"]:
            provider["usage"][key] += usage[key]


def _publish(run_dir: Path, root: Path, report: dict) -> None:
    _check_directory(root, root)
    _check_directory(run_dir.parent, root)
    _check_directory(run_dir, root)
    pending = run_dir / "chart.pending.png"
    final = run_dir / "chart.png"
    if report["status"] == "completed" and report["chart"]:
        chart = report["chart"]
        if (
            pending.is_symlink() or not pending.is_file() or final.exists() or final.is_symlink()
            or chart.get("path") != str(final.relative_to(root))
            or chart.get("summary_id") != report["summary"].get("summary_id")
        ):
            raise Failure("artifact_error", phase="publication")
        with pending.open("rb") as handle:
            header = handle.read(24)
        if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR" or struct.unpack(">II", header[16:24]) != (960, 540):
            raise Failure("artifact_error", phase="publication")
        os.link(pending, final, follow_symlinks=False)
        pending.unlink()
    elif pending.exists() or pending.is_symlink():
        pending.unlink()
    temporary = run_dir / "report.pending.json"
    with _open_new(temporary) as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")
    os.replace(temporary, run_dir / "report.json")


def _rollback_publication(run_dir: Path, root: Path) -> None:
    _check_directory(root, root)
    _check_directory(run_dir.parent, root)
    _check_directory(run_dir, root)
    for name in ("chart.png", "chart.pending.png", "report.pending.json"):
        with suppress(FileNotFoundError):
            (run_dir / name).unlink()


def run(
    config: RunConfig, *, root: Path | None = None, api_key: str | None = None,
    backend_factory: Callable | None = None,
    request_seconds: float = REQUEST_SECONDS, run_seconds: float = RUN_SECONDS,
) -> dict:
    """Supervise a trusted worker; injectable paths/backends/limits are test seams, not CLI options."""
    if config.mode == "live" and (not isinstance(api_key, str) or not api_key.strip()):
        return error_report(config, Failure("missing_credentials", status="rejected", phase="configuration"))
    root = root or case_directory()
    run_id = uuid4().hex
    report = _empty_report(config, run_id)
    try:
        run_dir = _create_run(root, run_id)
        trace = _open_new(run_dir / "trace.jsonl")
    except (OSError, Failure):
        return error_report(config, Failure("artifact_error", phase="artifacts"))

    context = multiprocessing.get_context("spawn")
    reader, writer = context.Pipe(duplex=False)
    worker = context.Process(target=_worker, args=(config, root, run_dir, run_id, api_key, writer, backend_factory))
    started = time.monotonic()
    deadline = started + run_seconds
    request_deadline = None
    outcome = None

    def record(event: dict) -> None:
        trace.write(json.dumps({"elapsed_seconds": round(time.monotonic() - started, 6), **event}, allow_nan=False) + "\n")
        trace.flush()

    try:
        record({"event": "run_started", "mode": config.mode, "requested_format": config.output_format})
        worker.start()
        writer.close()
        while True:
            now = time.monotonic()
            if now >= deadline:
                raise Failure("limit_reached", status="limit_reached", phase="run_deadline")
            if request_deadline is not None and now >= request_deadline:
                raise Failure("provider_timeout", phase="provider")
            wait_until = min(deadline, request_deadline or deadline)
            if reader.poll(min(0.05, max(0, wait_until - now))):
                try:
                    message = reader.recv()
                except EOFError:
                    break
                kind = message["kind"]
                if kind == "request_started":
                    request_deadline = min(deadline, message["at"] + request_seconds)
                elif kind == "request_finished":
                    if request_deadline is None or message["at"] > request_deadline:
                        raise Failure("provider_timeout", phase="provider")
                    request_deadline = None
                elif kind == "dataset":
                    report["dataset_sha256"] = message["sha256"]
                    record({"event": "dataset_loaded", "sha256": message["sha256"]})
                elif kind == "backend_response":
                    _merge_metadata(report, message["metadata"])
                    record({"event": kind, "number": message["number"], "metadata": message["metadata"]})
                elif kind == "tool_result":
                    record({"event": kind, **{key: message[key] for key in ("number", "tool", "arguments", "result")}})
                elif kind in {"success", "failure"}:
                    outcome = message
                    request_deadline = None
            if not worker.is_alive() and not reader.poll():
                break
        worker.join(timeout=max(0, min(1, deadline - time.monotonic())))
        if worker.is_alive() or worker.exitcode != 0 or outcome is None:
            raise Failure("invalid_tool_result", phase="worker")
        if time.monotonic() >= deadline:
            raise Failure("limit_reached", status="limit_reached", phase="run_deadline")
        if outcome["kind"] == "success":
            report.update(status="completed", summary=outcome["summary"], chart=outcome["chart"])
        else:
            report.update(status=outcome["status"], error=outcome["error"])
    except KeyboardInterrupt:
        failure = Failure("cancelled", status="cancelled", phase="run")
        report.update(status=failure.status, error=failure.as_dict())
    except Failure as failure:
        report.update(status=failure.status, error=failure.as_dict())
    except Exception:
        report.update(status="failed", error=Failure("artifact_error", phase="controller").as_dict())
    finally:
        if worker.pid is not None:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=1)
            if worker.is_alive():
                worker.kill()
                worker.join(timeout=1)
        reader.close()
        writer.close()

    if report["status"] != "completed":
        report.update(summary=None, chart=None)
    try:
        _publish(run_dir, root, report)
    except (KeyboardInterrupt, OSError, ValueError, Failure) as error:
        failure = Failure("cancelled", status="cancelled", phase="publication") if isinstance(error, KeyboardInterrupt) else Failure("artifact_error", phase="publication")
        report.update(status=failure.status, summary=None, chart=None, error=failure.as_dict())
        with suppress(OSError, ValueError, Failure):
            _rollback_publication(run_dir, root)
            _publish(run_dir, root, report)
    finally:
        with suppress(OSError, ValueError):
            record({"event": "run_finished", "status": report["status"], "error": report["error"]})
        trace.close()
    return report
