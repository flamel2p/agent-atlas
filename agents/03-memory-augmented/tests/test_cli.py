import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest


CASE = Path(__file__).resolve().parents[1]


def command(*args, cwd=None):
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("OPENAI_", "MEMORY_AGENT_")) and key != "PYTHONPATH"}
    result = subprocess.run([sys.executable, "-m", "memory_agent", *args], capture_output=True,
                            text=True, env=environment, cwd=cwd or CASE, timeout=10)
    return result, json.loads(result.stdout)


def test_separate_processes_remember_recall_correct_and_forget(tmp_path):
    store = "test-" + uuid4().hex
    def ask_cli(session, *extra):
        return command("ask", "--user", "cli-learner", "--session", session, "--query", "working memory",
                       "--store", store, *extra, cwd=tmp_path)
    try:
        first_process, first = ask_cli("first", "--remember-style", "example-first")
        second_process, second = ask_cli("second")
        assert first_process.returncode == second_process.returncode == 0
        assert first_process.stderr == second_process.stderr == ""
        assert second["preference"] == {**first["preference"], "source": "memory"}
        assert second["recalled_episodes"][0]["source_session"] == "first"
        assert (CASE / f"private-data/{store}.sqlite3").exists()
        assert not (tmp_path / "private-data").exists()
        _, correction = ask_cli("third", "--remember-style", "step-by-step")
        _, recalled = ask_cli("fourth")
        assert recalled["preference"] == {**correction["preference"], "source": "memory"}
        forgotten_process, forgotten = command("forget", "--user", "cli-learner", "--store", store)
        assert forgotten_process.returncode == 0 and forgotten["deleted"] == {"preferences": 1, "episodes": 4}
        _, fresh = ask_cli("fifth")
        assert fresh["preference"]["source"] == "default" and fresh["recalled_episodes"] == []
    finally:
        for suffix in ("", "-journal", "-wal", "-shm"):
            (CASE / f"private-data/{store}.sqlite3{suffix}").unlink(missing_ok=True)


@pytest.mark.parametrize("args", [[], ["forget"], ["ask", "--user", "a"], ["unknown"],
    ["forget", "--user", "../escape"], ["forget", "--user", "a", "--store", "../escape"],
    ["ask", "--user", "a", "--session", "s", "--query", "working", "--mode", "invalid"]])
def test_invalid_cli_always_has_sanitized_json(args):
    process, result = command(*args)
    assert process.returncode == 2 and process.stderr == ""
    assert result["failure_code"] == "invalid_input" and result["answer"] is None
    assert "../escape" not in process.stdout


def test_help_is_available_without_credentials():
    result = subprocess.run([sys.executable, "-m", "memory_agent", "--help"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and "ask" in result.stdout and "forget" in result.stdout
