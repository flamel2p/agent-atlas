import os
from pathlib import Path
import sqlite3

import pytest

from memory_agent.agent import ask, forget
from memory_agent.contracts import Request


def request_at(tmp_path):
    return ask(Request("a", "s", "working memory", "example-first"), case_root=tmp_path)


@pytest.mark.parametrize("location", ["directory", "database", "journal", "wal", "shm"])
def test_symlinks_are_rejected_without_target_changes(tmp_path, location):
    external = tmp_path / "external"
    external.mkdir()
    sentinel = external / "sentinel"
    sentinel.write_bytes(b"unchanged")
    directory = tmp_path / "private-data"
    if location == "directory":
        directory.symlink_to(external, target_is_directory=True)
    else:
        directory.mkdir()
        suffix = {"database": "", "journal": "-journal", "wal": "-wal", "shm": "-shm"}[location]
        (directory / f"demo.sqlite3{suffix}").symlink_to(sentinel)
    result = request_at(tmp_path)
    assert result["failure_code"] == "unsafe_state_path"
    assert sentinel.read_bytes() == b"unchanged"


def test_dangling_symlink_rejected(tmp_path):
    directory = tmp_path / "private-data"
    directory.mkdir()
    (directory / "demo.sqlite3").symlink_to(tmp_path / "missing")
    assert request_at(tmp_path)["failure_code"] == "unsafe_state_path"
    assert not (tmp_path / "missing").exists()


@pytest.mark.parametrize("suffix", ["", "-journal", "-wal", "-shm"])
def test_hard_links_rejected(tmp_path, suffix):
    directory = tmp_path / "private-data"
    directory.mkdir()
    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(b"unchanged")
    os.link(sentinel, directory / f"demo.sqlite3{suffix}")
    assert request_at(tmp_path)["failure_code"] == "unsafe_state_path"
    assert sentinel.read_bytes() == b"unchanged"


@pytest.mark.parametrize("kind", ["directory", "fifo"])
def test_nonregular_database_rejected(tmp_path, kind):
    directory = tmp_path / "private-data"
    directory.mkdir()
    path = directory / "demo.sqlite3"
    path.mkdir() if kind == "directory" else os.mkfifo(path)
    assert request_at(tmp_path)["failure_code"] == "unsafe_state_path"


@pytest.mark.parametrize("content", [b"corrupted store: private sentinel", b""])
def test_corrupt_or_empty_existing_store_is_preserved(tmp_path, content):
    directory = tmp_path / "private-data"
    directory.mkdir()
    path = directory / "demo.sqlite3"
    path.write_bytes(content)
    result = request_at(tmp_path)
    assert result["status"] == "failed"
    assert result["failure_code"] in ("storage_schema", "storage_failure")
    assert path.read_bytes() == content
    assert "sentinel" not in str(result)


@pytest.mark.parametrize("alteration", ["PRAGMA user_version = 99", "CREATE TABLE extra (value TEXT)",
    "CREATE TRIGGER unauthorized AFTER INSERT ON episodes BEGIN DELETE FROM preferences; END"])
def test_incompatible_schema_preserved(turn, tmp_path, alteration):
    turn(remember_style="example-first")
    path = tmp_path / "private-data/demo.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(alteration)
    before = path.read_bytes()
    assert request_at(tmp_path)["failure_code"] == "storage_schema"
    assert path.read_bytes() == before


def test_sqlite_prefix_lookalike_trigger_cannot_cross_user_scope(turn, tmp_path):
    turn(remember_style="example-first")
    turn(user="learner-b", remember_style="step-by-step")
    path = tmp_path / "private-data/demo.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TRIGGER sqlitex_cross_user AFTER INSERT ON episodes BEGIN
            DELETE FROM preferences WHERE user_id != NEW.user_id;
            DELETE FROM episodes WHERE user_id != NEW.user_id; END""")
    before = path.read_bytes()
    assert turn()["failure_code"] == "storage_schema"
    assert path.read_bytes() == before
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT style FROM preferences WHERE user_id = 'learner-b'").fetchone() == ("step-by-step",)
        assert connection.execute("SELECT COUNT(*) FROM episodes WHERE user_id = 'learner-b'").fetchone() == (1,)


def test_locked_store_fails_without_overwrite(turn, tmp_path):
    turn(remember_style="example-first")
    path = tmp_path / "private-data/demo.sqlite3"
    with sqlite3.connect(path) as locker:
        locker.execute("BEGIN EXCLUSIVE")
        result = request_at(tmp_path)
        assert result["failure_code"] == "storage_failure"
        assert locker.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 1


@pytest.mark.parametrize("sql", [
    "UPDATE preferences SET created_at = 'z-invalid'", "UPDATE preferences SET record_id = 'bad'",
    "UPDATE episodes SET query = char(0)", "UPDATE episodes SET faq_ids = '[\"invented\"]'",
])
def test_invalid_stored_records_fail_closed(turn, tmp_path, sql):
    turn(remember_style="example-first")
    path = tmp_path / "private-data/demo.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(sql)
    before = path.read_bytes()
    result = turn()
    assert result["failure_code"] == "storage_data"
    assert result["answer"] is None
    assert path.read_bytes() == before


def test_forget_cannot_escape_path(tmp_path):
    assert forget("a", "../escape", case_root=tmp_path)["failure_code"] == "invalid_input"
    assert forget("../escape", case_root=tmp_path)["failure_code"] == "invalid_input"
    assert not (tmp_path / "private-data").exists()
