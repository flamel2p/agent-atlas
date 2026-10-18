import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from autonomous_decision_making import cli


def test_default_cli_is_offline_and_writes_only_json(capsys, monkeypatch, tmp_path):
    class NoEnvironmentAccess:
        def get(self, key, default):
            raise AssertionError("replay must not read credentials")

    monkeypatch.setattr(cli, "os", SimpleNamespace(environ=NoEnvironmentAccess()))
    monkeypatch.chdir(tmp_path)
    assert cli.main([]) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["mode"] == "replay" and result["route"] == "autonomous"
    assert captured.err == "" and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("argv", [["--example", "PRIVATE_PATH"], ["--mode", "PRIVATE_MODE"], ["--arbitrary", "PRIVATE_SECRET"]])
def test_invalid_cli_inputs_produce_sanitized_json(argv, capsys):
    assert cli.main(argv) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out)["policy_reason"] == "invalid_input"
    assert "PRIVATE" not in captured.out and captured.err == ""


def test_missing_live_credentials_stops_before_execution(capsys, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(cli, "load_example", lambda name: pytest.fail("must not read fixture"))
    assert cli.main(["--mode", "live"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["policy_reason"] == "invalid_configuration"
    assert report["lookup_attempts"] == report["cognition_attempts"] == 0


@pytest.mark.parametrize("example", ["routine-outage", "human-request"])
def test_missing_live_sdk_is_configuration_failure_even_for_hard_gate(example, capsys, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setitem(sys.modules, "openai", None)
    monkeypatch.setattr(cli, "load_example", lambda name: pytest.fail("must not read fixture"))
    assert cli.main(["--mode", "live", "--example", example]) == 2
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["policy_reason"] == "invalid_configuration"
    assert report["lookup_attempts"] == report["cognition_attempts"] == 0
    assert "synthetic-test-key" not in captured.out and captured.err == ""


def test_cli_failure_handoff_preserves_nonzero_exit(capsys):
    assert cli.main(["--example", "missing-confidence"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["route"] == "handoff" and report["status"] == "failed"


def test_replay_in_fresh_interpreter_forbids_sdk_import_and_network():
    code = '''
import importlib.abc
import socket
import sys
class DenyProvider(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "openai" or fullname.startswith("openai."):
            raise AssertionError("provider imported during replay")
sys.meta_path.insert(0, DenyProvider())
def denied(*args, **kwargs):
    raise AssertionError("network forbidden during replay")
socket.create_connection = denied
socket.socket.connect = denied
from autonomous_decision_making.cli import main
raise SystemExit(main([]))
'''
    env = {key: value for key, value in os.environ.items() if key != "OPENAI_API_KEY"}
    completed = subprocess.run([sys.executable, "-I", "-c", code], text=True, capture_output=True, env=env, timeout=10)
    assert completed.returncode == 0 and completed.stderr == ""
    assert json.loads(completed.stdout)["route"] == "autonomous"
