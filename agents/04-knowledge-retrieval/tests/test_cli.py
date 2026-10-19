import json
from pathlib import Path
import subprocess
import sys

import pytest

from knowledge_agent import cli


def command(*args, cwd=None):
    return subprocess.run([sys.executable, "-m", "knowledge_agent.cli", *args],
                          cwd=cwd, capture_output=True, text=True, timeout=10)


def test_cli_resources_outside_checkout_and_no_state(tmp_path):
    result = command("ask", "How can I cancel my subscription?", "--as-of", "2026-10-19", cwd=tmp_path)
    assert result.returncode == 0 and result.stderr == ""
    assert json.loads(result.stdout)["status"] == "answered"
    assert list(tmp_path.iterdir()) == []


def test_cli_unknown_topic():
    result = command("ask", "Can I pay with crypto?", "--as-of", "2026-10-19")
    body = json.loads(result.stdout)
    assert result.returncode == 0 and body["status"] == "abstained"
    assert body["answer"] == "" and body["citations"] == []


@pytest.mark.parametrize("args", [
    [], ["ask"], ["ask", ""], ["ask", "x" * 1001],
    ["ask", "cancel", "--backend", "malicious-secret"],
    ["ask", "cancel", "--audience", "admin"],
    ["ask", "cancel", "--as-of", "2026-02-30"],
    ["ask", "cancel", "--corpus", "/secret/path"],
    ["ask", "cancel", "--url", "https://malicious.invalid"],
])
def test_cli_invalid_input_has_json_and_exit_two(args):
    result = command(*args)
    body = json.loads(result.stdout)
    assert result.returncode == 2 and body["reason"] == "invalid_input"
    assert result.stderr == "" and "malicious-secret" not in result.stdout and "/secret/path" not in result.stdout


def test_cli_missing_credentials_has_no_fallback():
    result = command("ask", "cancel", "--backend", "openai", "--as-of", "2026-10-19")
    body = json.loads(result.stdout)
    assert result.returncode == 1 and body["reason"] == "missing_or_invalid_api_key"
    assert body["counts"] == {"search_calls": 0, "model_calls": 0}


def test_cli_cancellation_is_json_and_exit_130(monkeypatch, capsys):
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, "run", interrupt)
    assert cli.main(["ask", "cancel"]) == 130
    output = capsys.readouterr()
    assert json.loads(output.out)["status"] == "cancelled" and output.err == ""


def test_cli_help():
    result = command("--help")
    assert result.returncode == 0 and "ask" in result.stdout
