import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from planning_agent import cli
from planning_agent.contracts import Failure


@pytest.mark.parametrize("example,status,code", [("normal", "completed", 0),
    ("reviewer-unavailable", "completed", 0), ("no-reviewer", "blocked", 2),
    ("deadline", "limit_reached", 2), ("task-failure", "failed", 2)])
def test_cli_json_stdout_and_exit_codes(example, status, code, capsys):
    assert cli.main(["--example", example]) == code
    captured = capsys.readouterr()
    assert captured.err == ""
    report = json.loads(captured.out)
    assert report["status"] == status and report["mode"] == "replay"


@pytest.mark.parametrize("failure,status,code,reason", [
    (Failure("missing_credentials"), "failed", 2, "missing_credentials"),
    (Failure("missing_live_dependency"), "failed", 2, "missing_live_dependency"),
    (KeyboardInterrupt(), "cancelled", 130, "interrupted"),
])
def test_preflight_failure_and_interrupt_before_planning(failure, status, code, reason, monkeypatch, capsys):
    def fail(key):
        raise failure
    monkeypatch.setattr(cli, "OpenAIPlanner", fail)
    assert cli.main(["--mode", "live"]) == code
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == status and report["reason"] == reason
    assert report["planning_calls"] == 0 and report["release_artifact"] is None


@pytest.mark.parametrize("args", [["--example", "unknown"], ["--mode", "unknown"], ["--input", "private-file"]])
def test_argument_errors_are_argparse_exit_two(args):
    with pytest.raises(SystemExit) as error:
        cli.main(args)
    assert error.value.code == 2


def test_replay_import_and_cli_need_no_provider_or_credentials():
    env = {key: value for key, value in os.environ.items() if not key.startswith("OPENAI_")}
    source = "import sys; sys.modules['openai']=None; from planning_agent.cli import main; raise SystemExit(main())"
    process = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True,
                             env=env, cwd=Path(__file__).parents[1], timeout=5)
    assert process.returncode == 0 and process.stderr == ""
    assert json.loads(process.stdout)["status"] == "completed"
