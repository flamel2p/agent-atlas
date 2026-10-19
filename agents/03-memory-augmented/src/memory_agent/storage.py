from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from .contracts import Failure, Request, STYLES, timestamp, validate_name, validate_query, validate_timestamp
from .knowledge import faq, tokens


CASE_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = 1
SCHEMA = {
    "preferences": """CREATE TABLE preferences (
        user_id TEXT PRIMARY KEY NOT NULL,
        record_id TEXT NOT NULL UNIQUE,
        session_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        style TEXT NOT NULL CHECK (style IN ('concise','step-by-step','example-first'))
    )""",
    "episodes": """CREATE TABLE episodes (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        query TEXT NOT NULL,
        faq_ids TEXT NOT NULL,
        style TEXT NOT NULL CHECK (style IN ('concise','step-by-step','example-first'))
    )""",
    "episodes_user_time": "CREATE INDEX episodes_user_time ON episodes(user_id, created_at DESC, record_id DESC)",
}


def _regular_single_link(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise Failure("unsafe_state_path")


def _directory(path: Path) -> None:
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise Failure("unsafe_state_path")


def state_path(case_root: Path, name: str) -> tuple[Path, bool]:
    validate_name(name)
    _directory(case_root)
    directory = case_root / "private-data"
    if not directory.exists() and not directory.is_symlink():
        directory.mkdir(mode=0o700)
    _directory(directory)
    path = directory / f"{name}.sqlite3"
    for candidate in (path, *(Path(str(path) + suffix) for suffix in ("-journal", "-wal", "-shm"))):
        _regular_single_link(candidate)
    created = not path.exists()
    if created:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
    return path, created


class Store:
    def __init__(self, name: str, *, case_root: Path = CASE_ROOT):
        self.name = name
        self.case_root = case_root
        self.connection: sqlite3.Connection | None = None

    def __enter__(self):
        try:
            path, created = state_path(self.case_root, self.name)
            self.connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=0.5, isolation_level=None)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA trusted_schema = OFF")
            if created:
                self.connection.execute("BEGIN IMMEDIATE")
                for statement in SCHEMA.values():
                    self.connection.execute(statement)
                self.connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                self.connection.commit()
            schema = {row["name"]: row["sql"] for row in self.connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'"
            )}
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version != SCHEMA_VERSION or schema != SCHEMA:
                raise Failure("storage_schema")
            self.connection.execute("BEGIN IMMEDIATE")
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        if self.connection is not None:
            try:
                self.connection.rollback()
            finally:
                self.connection.close()
                self.connection = None

    def recall(self, user: str, query: str, now: datetime) -> tuple[dict | None, list[dict]]:
        cutoff = timestamp(now - timedelta(days=30))
        row = self.connection.execute(
            "SELECT * FROM preferences WHERE user_id = ? AND created_at > ?", (user, cutoff)
        ).fetchone()
        preference = None
        if row is not None:
            self._validate_record(row)
            if not re.fullmatch(r"pref-[0-9a-f]{32}", row["record_id"]):
                raise Failure("storage_data")
            preference = {
                "style": row["style"], "source": "memory", "remembered": True,
                "record_id": row["record_id"], "source_session": row["session_id"],
                "created_at": row["created_at"],
            }
        ranked = []
        query_tokens = tokens(query)
        allowed = {entry["id"] for entry in faq()}
        for row in self.connection.execute(
            "SELECT * FROM episodes WHERE user_id = ? AND created_at > ? ORDER BY created_at DESC, record_id DESC LIMIT 20",
            (user, cutoff),
        ):
            self._validate_record(row)
            try:
                validate_query(row["query"])
                ids = json.loads(row["faq_ids"])
                if not isinstance(ids, list) or len(ids) > 3 or any(not isinstance(key, str) or key not in allowed for key in ids):
                    raise ValueError
                if len(set(ids)) != len(ids) or not isinstance(row["record_id"], int) or row["record_id"] < 1:
                    raise ValueError
            except (Failure, TypeError, ValueError):
                raise Failure("storage_data") from None
            overlap = len(query_tokens & tokens(row["query"]))
            if overlap:
                episode = {
                    "record_id": row["record_id"], "source_session": row["session_id"],
                    "created_at": row["created_at"], "query": row["query"],
                    "faq_ids": ids, "style": row["style"],
                }
                ranked.append((overlap, episode))
        ranked.sort(key=lambda item: (item[0], item[1]["created_at"], item[1]["record_id"]), reverse=True)
        return preference, [episode for _, episode in ranked[:3]]

    @staticmethod
    def _validate_record(row: sqlite3.Row) -> None:
        try:
            validate_name(row["session_id"])
            validate_timestamp(row["created_at"])
            if row["style"] not in STYLES:
                raise ValueError
        except (Failure, TypeError, ValueError):
            raise Failure("storage_data") from None

    def persist(self, request: Request, preference: dict, selection: list[str], now: datetime) -> int:
        cutoff = timestamp(now - timedelta(days=30))
        for table in ("episodes", "preferences"):
            self.connection.execute(f"DELETE FROM {table} WHERE user_id = ? AND created_at <= ?", (request.user, cutoff))
        if request.remember_style is not None:
            self.connection.execute(
                """INSERT INTO preferences VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET record_id = excluded.record_id,
                session_id = excluded.session_id, created_at = excluded.created_at, style = excluded.style""",
                (request.user, preference["record_id"], request.session, timestamp(now), request.remember_style),
            )
        cursor = self.connection.execute(
            "INSERT INTO episodes (user_id, session_id, created_at, query, faq_ids, style) VALUES (?, ?, ?, ?, ?, ?)",
            (request.user, request.session, timestamp(now), request.query, json.dumps(selection), preference["style"]),
        )
        self.connection.execute(
            """DELETE FROM episodes WHERE user_id = ? AND record_id NOT IN
            (SELECT record_id FROM episodes WHERE user_id = ? ORDER BY created_at DESC, record_id DESC LIMIT 20)""",
            (request.user, request.user),
        )
        self.connection.commit()
        return cursor.lastrowid

    def forget(self, user: str) -> dict:
        counts = {}
        for table in ("preferences", "episodes"):
            counts[table] = self.connection.execute(f"DELETE FROM {table} WHERE user_id = ?", (user,)).rowcount
        self.connection.commit()
        return counts
