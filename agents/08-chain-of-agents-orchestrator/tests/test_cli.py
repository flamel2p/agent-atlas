"""Exercise the installed module CLI through real subprocesses and Unix SIGINT."""

import json
import os
import signal
import subprocess
import sys

import pytest

from chain_orchestrator.evidence import SCENARIOS


@pytest.mark.parametrize("scenario,status,code", [
    ("consistent", "complete", 0),
    ("contradictory", "review_required", 2),
    ("negative", "review_required", 2),
    ("missing-evidence", "review_required", 2),
    ("prerequisite-failure", "failed", 1),
    ("downstream-failure", "failed", 1),
    ("timeout", "timed_out", 1),
    ("scoped", "complete", 0),
])
def test_documented_scenarios_emit_one_json_report(scenario, status, code, tmp_path):
    result = subprocess.run([sys.executable, "-m", "chain_orchestrator", scenario],
                            cwd=tmp_path, capture_output=True, text=True, timeout=5)
    assert result.returncode == code
    report = json.loads(result.stdout)
    assert report["mode"] == "fixture" and report["status"] == status
    assert len(report["tasks"]) == 3
    assert result.stderr == ""


@pytest.mark.parametrize("args", [
    ["../private.json"], ["consistent", "--target-release", "absent"],
    ["--provider", "SECRET"], ["--target-release"], ["consistent", "extra"],
])
def test_bad_arguments_have_bounded_diagnostic_no_traceback_or_partial_json(args):
    result = subprocess.run([sys.executable, "-m", "chain_orchestrator", *args],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and result.stdout == ""
    assert len(result.stderr) < 120
    assert "Traceback" not in result.stderr and "SECRET" not in result.stderr


def test_help_and_target_release_selection():
    result = subprocess.run([sys.executable, "-m", "chain_orchestrator", "--help"],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and result.stderr == ""
    assert all(name in result.stdout for name in SCENARIOS)
    result = subprocess.run([sys.executable, "-m", "chain_orchestrator", "scoped",
                             "--target-release", "v0.9"],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 2
    assert json.loads(result.stdout)["target_release"] == "v0.9"


@pytest.mark.skipif(os.name != "posix", reason="SIGINT process check uses POSIX signals")
def test_keyboard_interrupt_cleans_up_and_exits_130():
    # Synchronize from inside a started child, so SIGINT cannot race Python startup.
    script = '''
import asyncio
from chain_orchestrator import cli
from chain_orchestrator.manager import analyze_release
async def specialist(request):
    print("started", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        print("cleaned", flush=True)
async def analysis(*args):
    return await analyze_release(_specialist=specialist)
cli.analyze_release = analysis
raise SystemExit(cli.main([]))
'''
    process = subprocess.Popen([sys.executable, "-u", "-c", script],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "started"
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 130
        assert stdout.strip() == "cleaned" and stderr.strip() == "interrupted"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
