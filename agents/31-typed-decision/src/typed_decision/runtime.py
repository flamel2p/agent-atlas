"""Run exactly one fixed synthetic adapter with a bounded child lifetime.

The child receives an immutable, size-checked fixture snapshot over stdin. It
cannot select executable code, read caller paths, or invoke a provider. Host
validation and decision policy run after its response, never in untrusted text.
This process boundary supplies cancellation and timeout, not a security sandbox.
"""

import signal
import subprocess
import sys
import time
from pathlib import Path
from threading import Event

from .contracts import Policy, Request, Result, decide, fields
from .json_boundary import Invalid, MAX_BYTES, dumps, loads, snapshot

CLEANUP_SECONDS = 0.3
POLL_SECONDS = 0.01


def _cleanup(process: subprocess.Popen) -> None:
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                process.kill()
                # A fixed stdlib worker cannot catch SIGKILL. Failure to reap is
                # reported as backend failure rather than claiming clean timeout.
                process.wait(timeout=0.2)
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                stream.close()
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


def predict(raw_request: object, *, fixture: object, policy: Policy = Policy(),
            cancel: Event | None = None) -> Result:
    """Return one terminal result from a caller request and synthetic fixture.

    Library inputs are ordinary JSON-shaped dictionaries, with Decimal, int or
    float numeric values. Floats use their shortest decimal spelling. A host
    Event is the only cooperative cancellation input. It is never passed to
    the worker. SIGINT is translated into the same cancellation outcome.
    """
    request = None
    try:
        request = Request.parse(raw_request)
        if type(policy) is not Policy:
            raise Invalid("invalid_policy")
        policy = policy.checked()
    except (Invalid, TypeError, ValueError, OverflowError):
        return Result(request.request_id if request else None, "invalid_input", "request_or_policy")
    if cancel is not None and not isinstance(cancel, Event):
        return Result(request.request_id, "invalid_input", "invalid_cancellation")
    if cancel is not None and cancel.is_set():
        return Result(request.request_id, "cancellation", "cancelled_before_attempt", threshold=policy.threshold)
    try:
        # Round-trip gives the library the same size/depth/type boundary as CLI.
        data = fields(snapshot(fixture), {"request", "behavior", "response"})
        bound = Request.parse(data["request"])
        if bound != request:
            raise Invalid("fixture_request_mismatch")
        if type(data["behavior"]) is not str or data["behavior"] not in {"return", "fail", "hang"}:
            raise Invalid("fixture_behavior")
        payload = dumps(data).encode("utf-8")
        if len(payload) > MAX_BYTES:
            raise Invalid("json_byte_limit")
    except (Invalid, TypeError, ValueError, OverflowError, RecursionError):
        return Result(request.request_id, "invalid_output", "fixture_contract", threshold=policy.threshold)

    process = None
    attempts = 0
    result = None
    deadline = time.monotonic() + policy.timeout_seconds
    try:
        # Defer SIGINT until the process handle is owned. An interrupt inside
        # Popen construction must not leave an unreachable child behind.
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
        try:
            process = subprocess.Popen([sys.executable, "-I", str(Path(__file__).with_name("_worker.py"))],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, close_fds=True,
                                       start_new_session=True)
            attempts = 1
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        pending = payload
        while result is None:
            if cancel is not None and cancel.is_set():
                result = Result(request.request_id, "cancellation", "cancelled", attempts,
                                threshold=policy.threshold)
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                result = Result(request.request_id, "timeout", "deadline_exceeded", attempts,
                                threshold=policy.threshold)
                break
            try:
                output, _ = process.communicate(pending, timeout=min(POLL_SECONDS, remaining))
            except subprocess.TimeoutExpired:
                pending = None
                continue
            # Cancellation and deadline win over a simultaneously completed result.
            if cancel is not None and cancel.is_set():
                result = Result(request.request_id, "cancellation", "cancelled", attempts,
                                threshold=policy.threshold)
            elif time.monotonic() >= deadline:
                result = Result(request.request_id, "timeout", "deadline_exceeded", attempts,
                                threshold=policy.threshold)
            elif process.returncode != 0:
                result = Result(request.request_id, "backend_failure", "adapter_failed", attempts,
                                threshold=policy.threshold)
            else:
                try:
                    result = decide(request, loads(output), policy, attempts=attempts)
                except Invalid:
                    result = Result(request.request_id, "invalid_output", "response_contract", attempts,
                                    threshold=policy.threshold)
    except KeyboardInterrupt:
        result = Result(request.request_id, "cancellation", "interrupted", attempts,
                        threshold=policy.threshold)
    except (OSError, ValueError, subprocess.SubprocessError):
        result = Result(request.request_id, "backend_failure", "worker_unavailable", attempts,
                        threshold=policy.threshold)
    finally:
        if process is not None:
            try:
                _cleanup(process)
            except KeyboardInterrupt:
                result = Result(request.request_id, "cancellation", "interrupted", attempts,
                                threshold=policy.threshold)
            except (OSError, subprocess.SubprocessError):
                result = Result(request.request_id, "backend_failure", "cleanup_failed", attempts,
                                threshold=policy.threshold)
    return result
