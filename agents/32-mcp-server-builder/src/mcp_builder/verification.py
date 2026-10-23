"""Bounded fixed subprocess gate. No model-provided commands are accepted."""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
from .runtime import strict_json


def clean_env():
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1', 'SYNTHETIC_API_TOKEN': 'synthetic-fixture-token'}


async def bounded_run(command, cwd, deadline=30):
    """Drain both pipes with hard byte caps; every exit path reaps the child."""
    process = await asyncio.create_subprocess_exec(*command, cwd=cwd, env=clean_env(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=True)
    async def read(stream):
        buf = bytearray()
        while chunk := await stream.read(8192):
            buf.extend(chunk)
            if len(buf) > 256 * 1024:
                raise ValueError('verification_output_limit')
        return bytes(buf)
    try:
        async with asyncio.timeout(deadline):
            out, err = await asyncio.gather(read(process.stdout), read(process.stderr))
            code = await process.wait()
        if code:
            raise ValueError('verifier_failed:' + err.decode(errors='replace')[-1500:])
        return out
    finally:
        # All descendants share this fresh process group; terminating the group
        # also stops a server child when the fixed checker itself was cancelled.
        import signal
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        # A leader may have exited while a descendant still owns a pipe.
        # Probe the group itself before escalating, not only the leader PID.
        stop = asyncio.get_running_loop().time() + 1
        while asyncio.get_running_loop().time() < stop:
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(.01)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if process.returncode is None:
            await process.wait()


async def verify(staging):
    command = [sys.executable, str(staging / 'server/check_server.py'), '--server', str(staging / 'server')]
    with tempfile.TemporaryDirectory(prefix='agent32-verifier-') as cwd:
        output = await bounded_run(command, cwd)
    report = strict_json(output)
    if report.get('result') != 'passed' or report.get('protocol') != '2026-07-28' or report.get('network_isolation') != 'sandbox-exec-fixture-port-only':
        raise ValueError('verification_report')
    return {'command': ['python', 'server/check_server.py', '--server', 'server'], **report}
