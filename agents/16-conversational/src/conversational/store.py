"""Guarded local SQLite snapshots with one atomic transaction per allowed turn.

The store owns expiry, caps, canonical recent history, and explicit preference
provenance. BEGIN IMMEDIATE serializes writers so composition and the saved
answer use one snapshot. No application retry follows a lock or commit failure.
Static path aliases are rejected. This is not protection against a malicious
local actor replacing filesystem entries concurrently.
"""

from collections import Counter
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
from typing import Callable

from .dialogue import BY_ID, compose, transition
from .domain import (
    BUSY_TIMEOUT, DATABASE_BYTES, HISTORY_LIMIT, MAX_RESPONSE, PREFERENCE_TTL,
    SESSION_TTL, SESSION_TURN_LIMIT, TOTAL_SESSION_LIMIT, USER_LIMIT, USER_SESSION_LIMIT,
    Choosing, Closed, Detail, Focused, Intent, LessonStyle, Ready, RecentTurn,
    Snapshot, TurnRequest, TurnResult, state_name, terminal, valid_label,
)

SCHEMA_VERSION = 1
SCHEMA = {
    "sessions": """CREATE TABLE sessions (
        user_id TEXT NOT NULL, session_id TEXT NOT NULL,
        phase TEXT NOT NULL, focus TEXT, candidates TEXT NOT NULL, detail TEXT,
        turn_count INTEGER NOT NULL, updated_at INTEGER NOT NULL,
        PRIMARY KEY (user_id, session_id))""",
    "preferences": """CREATE TABLE preferences (
        user_id TEXT PRIMARY KEY, style TEXT NOT NULL, updated_at INTEGER NOT NULL,
        source_session TEXT NOT NULL, source_turn INTEGER NOT NULL)""",
    "turns": """CREATE TABLE turns (
        user_id TEXT NOT NULL, session_id TEXT NOT NULL, number INTEGER NOT NULL,
        intent TEXT NOT NULL, course_id TEXT, response TEXT NOT NULL,
        PRIMARY KEY (user_id, session_id, number),
        FOREIGN KEY (user_id, session_id) REFERENCES sessions(user_id, session_id) ON DELETE CASCADE)""",
}
CANONICAL = re.compile(r"(?:preference_update|(?:help|list|detail|choice|close|recap):(?:overview|duration|prerequisites):(?:[a-z]+(?:,[a-z]+)*)?:[1-4]?)\Z")


class StoreFailure(Exception):
    """A deliberately detail-free boundary error. SQLite errors never become output."""


def _directory(path: Path) -> None:
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise StoreFailure()


def _file(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > DATABASE_BYTES:
        raise StoreFailure()


def database_path(root: Path, workspace: str) -> Path:
    """Resolve an allowlisted namespace below CWD/private-data, without path input."""
    if not valid_label(workspace) or root.is_symlink() or not root.is_dir():
        raise StoreFailure()
    private = root / "private-data"
    _directory(private)
    directory = private / workspace
    _directory(directory)
    path = directory / "state.sqlite3"
    for suffix in ("", "-journal", "-wal", "-shm"):
        _file(path.with_name(path.name + suffix))
    return path


def _state(row: sqlite3.Row):
    candidates = json.loads(row["candidates"])
    if not isinstance(candidates, list) or len(candidates) > len(BY_ID):
        raise StoreFailure()
    if any(not isinstance(cid, str) or cid not in BY_ID for cid in candidates) or len(set(candidates)) != len(candidates):
        raise StoreFailure()
    phase, focus, detail = row["phase"], row["focus"], row["detail"]
    if phase == "choosing" and focus is None and len(candidates) >= 2:
        return Choosing(tuple(candidates), Detail(detail))
    if candidates or detail is not None:
        raise StoreFailure()
    if phase == "focused" and focus in BY_ID:
        return Focused(focus)
    if focus is None and phase in ("ready", "closed"):
        return Ready() if phase == "ready" else Closed()
    raise StoreFailure()


def _integer(value: object, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


class Store:
    """One workspace. Construction is lazy so the gate can bypass every file access."""

    def __init__(self, workspace: str, *, root: Path | None = None,
                 clock: Callable[[], float] = time.time,
                 composer: Callable = compose,
                 before_commit: Callable[[sqlite3.Connection], None] | None = None):
        self.workspace = workspace
        self.root = root if root is not None else Path.cwd()
        self.clock = clock
        self.composer = composer
        self.before_commit = before_commit

    def _connect(self) -> sqlite3.Connection:
        path = database_path(self.root, self.workspace)
        existed = path.exists()
        connection = sqlite3.connect(path, timeout=BUSY_TIMEOUT)
        try:
            if not existed:
                os.chmod(path, 0o600)
            elif not path.stat().st_mode & 0o222:
                raise StoreFailure()
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            if not existed:
                connection.execute("PRAGMA page_size=4096")
                connection.execute("BEGIN IMMEDIATE")
                for statement in SCHEMA.values():
                    connection.execute(statement)
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                connection.commit()
            actual = {row["name"]: row["sql"] for row in connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
            if (actual != SCHEMA or connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION
                    or connection.execute("PRAGMA page_size").fetchone()[0] != 4096):
                raise StoreFailure()
            if connection.execute("PRAGMA quick_check(1)").fetchone()[0] != "ok":
                raise StoreFailure()
            connection.execute("PRAGMA max_page_count=512")
            return connection
        except BaseException:
            connection.close()
            raise

    def _validate(self, db: sqlite3.Connection, now: int) -> None:
        """Validate the bounded persisted representation before expiry can discard it."""
        sessions = db.execute("SELECT * FROM sessions LIMIT ?", (TOTAL_SESSION_LIMIT + 1,)).fetchall()
        preferences = db.execute("SELECT * FROM preferences LIMIT ?", (USER_LIMIT + 1,)).fetchall()
        turns = db.execute("SELECT * FROM turns ORDER BY user_id, session_id, number LIMIT ?",
                           (TOTAL_SESSION_LIMIT * HISTORY_LIMIT + 1,)).fetchall()
        if len(sessions) > TOTAL_SESSION_LIMIT or len(preferences) > USER_LIMIT or len(turns) > TOTAL_SESSION_LIMIT * HISTORY_LIMIT:
            raise StoreFailure()
        users = {row["user_id"] for row in sessions} | {row["user_id"] for row in preferences}
        if len(users) > USER_LIMIT or any(not valid_label(user) for user in users):
            raise StoreFailure()
        if any(count > USER_SESSION_LIMIT for count in Counter(row["user_id"] for row in sessions).values()):
            raise StoreFailure()
        keys = {}
        for row in sessions:
            if (not valid_label(row["session_id"]) or not _integer(row["turn_count"], 1, SESSION_TURN_LIMIT)
                    or not _integer(row["updated_at"], 0, now) or len(row["candidates"]) > 100):
                raise StoreFailure()
            _state(row)
            keys[(row["user_id"], row["session_id"])] = row["turn_count"]
        session_rows = {(row["user_id"], row["session_id"]): row for row in sessions}
        for row in preferences:
            LessonStyle(row["style"])
            if (not _integer(row["updated_at"], 0, now) or not valid_label(row["source_session"])
                    or not _integer(row["source_turn"], 1, SESSION_TURN_LIMIT)):
                raise StoreFailure()
            source = session_rows.get((row["user_id"], row["source_session"]))
            # Older provenance may belong to an expired generation of a reused session label.
            # Equal timestamps still prove that a source counter cannot exceed this session's count.
            if source is not None and (
                row["updated_at"] > source["updated_at"]
                or row["updated_at"] == source["updated_at"] and row["source_turn"] > source["turn_count"]
            ):
                raise StoreFailure()
        grouped = {key: [] for key in keys}
        for row in turns:
            key = row["user_id"], row["session_id"]
            intent = row["intent"]
            if (key not in keys or not isinstance(intent, str) or len(intent) > 100 or not CANONICAL.fullmatch(intent)
                    or row["course_id"] is not None and row["course_id"] not in BY_ID
                    or not isinstance(row["response"], str) or not 0 < len(row["response"]) <= MAX_RESPONSE
                    or not row["response"].startswith("Course guide: ")
                    or not _integer(row["number"], 1, keys[key])):
                raise StoreFailure()
            if ":" in intent and any(cid not in BY_ID for cid in intent.split(":")[2].split(",") if cid):
                raise StoreFailure()
            grouped[key].append(row["number"])
        for key, count in keys.items():
            if grouped[key] != list(range(max(1, count - HISTORY_LIMIT + 1), count + 1)):
                raise StoreFailure()
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise StoreFailure()

    def _expire(self, db: sqlite3.Connection, now: int) -> None:
        db.execute("DELETE FROM sessions WHERE updated_at <= ?", (now - SESSION_TTL,))
        db.execute("DELETE FROM preferences WHERE updated_at <= ?", (now - PREFERENCE_TTL,))

    def turn(self, request: TurnRequest, intent: Intent) -> TurnResult:
        context, composition = "not_loaded", "skipped"
        try:
            with closing(self._connect()) as db:
                try:
                    db.execute("BEGIN IMMEDIATE")
                    now = int(self.clock())
                    self._validate(db, now)
                    self._expire(db, now)
                    row = db.execute("SELECT * FROM sessions WHERE user_id=? AND session_id=?",
                                     (request.user_id, request.session_id)).fetchone()
                    preference = db.execute("SELECT * FROM preferences WHERE user_id=?", (request.user_id,)).fetchone()
                    style = LessonStyle(preference["style"]) if preference else LessonStyle.STANDARD
                    if row and isinstance(_state(row), Closed):
                        db.rollback()
                        return TurnResult("already_closed", "Course guide: This session is already closed. Start a new session to continue.",
                                          "closed", preference_used=style.value,
                                          trace=("gate:passed", "context:restored", "compose:skipped", "persistence:unchanged"))
                    counts = db.execute("SELECT count(*) FROM sessions").fetchone()[0]
                    user_sessions = db.execute("SELECT count(*) FROM sessions WHERE user_id=?", (request.user_id,)).fetchone()[0]
                    users = {r[0] for r in db.execute("SELECT user_id FROM sessions UNION SELECT user_id FROM preferences")}
                    if ((request.user_id not in users and len(users) >= USER_LIMIT)
                            or row is None and (counts >= TOTAL_SESSION_LIMIT or user_sessions >= USER_SESSION_LIMIT)
                            or row is not None and row["turn_count"] >= SESSION_TURN_LIMIT):
                        db.rollback()
                        return terminal("limit", "Course guide: A local retention limit was reached. Forget your stored data or wait for expiry.",
                                        "gate:passed", "compose:skipped", "persistence:unchanged")
                    recent = tuple(RecentTurn(r["number"], r["intent"], r["course_id"], r["response"]) for r in db.execute(
                        "SELECT * FROM turns WHERE user_id=? AND session_id=? ORDER BY number", (request.user_id, request.session_id)))
                    snapshot = Snapshot(_state(row) if row else Ready(), row["turn_count"] if row else 0,
                                        recent, style, preference is not None, row is not None)
                    context = "restored" if row else "new"
                    plan = transition(snapshot, intent)
                    style = plan.save_style or snapshot.style
                    composition = "attempted"
                    response = self.composer(plan, style)
                    if not isinstance(response, str) or not 0 < len(response) <= MAX_RESPONSE or not response.startswith("Course guide: "):
                        raise StoreFailure()
                    composition = "fixture"
                    number = snapshot.turn_count + 1
                    state = plan.state
                    db.execute("""INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?)
                        ON CONFLICT(user_id,session_id) DO UPDATE SET phase=excluded.phase,focus=excluded.focus,
                        candidates=excluded.candidates,detail=excluded.detail,turn_count=excluded.turn_count,updated_at=excluded.updated_at""",
                        (request.user_id, request.session_id, state_name(state), state.course_id if isinstance(state, Focused) else None,
                         json.dumps(state.candidates if isinstance(state, Choosing) else ()),
                         state.detail.value if isinstance(state, Choosing) else None, number, now))
                    if plan.save_style:
                        db.execute("""INSERT INTO preferences VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
                            style=excluded.style,updated_at=excluded.updated_at,source_session=excluded.source_session,source_turn=excluded.source_turn""",
                            (request.user_id, style.value, now, request.session_id, number))
                    db.execute("INSERT INTO turns VALUES(?,?,?,?,?,?)", (request.user_id, request.session_id, number,
                               intent.canonical(), plan.course_id, response))
                    db.execute("DELETE FROM turns WHERE user_id=? AND session_id=? AND number <= ?",
                               (request.user_id, request.session_id, number - HISTORY_LIMIT))
                    if self.before_commit:
                        self.before_commit(db)
                    db.commit()
                    return TurnResult(plan.status, response, state_name(state), plan.course_id, style.value,
                                      ("gate:passed", "context:restored" if row else "context:new",
                                       "preference:updated" if plan.save_style else "preference:stored" if preference else "preference:default",
                                       "compose:fixture", "persistence:committed"))
                except BaseException:
                    db.rollback()
                    raise
        except Exception:
            return terminal("storage_error", "Course guide: Local state could not be processed. No dialogue changes were committed.",
                            "gate:passed", f"context:{context}", f"compose:{composition}", "persistence:rolled_back")

    def forget(self, user_id: str) -> TurnResult:
        try:
            with closing(self._connect()) as db:
                try:
                    db.execute("BEGIN IMMEDIATE")
                    self._validate(db, int(self.clock()))
                    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
                    db.execute("DELETE FROM preferences WHERE user_id=?", (user_id,))
                    if self.before_commit:
                        self.before_commit(db)
                    db.commit()
                except BaseException:
                    db.rollback()
                    raise
            return terminal("forgotten", "Course guide: This user's saved preferences and sessions are forgotten.", "persistence:committed")
        except Exception:
            return terminal("storage_error", "Course guide: Local state could not be processed. No dialogue changes were committed.",
                            "persistence:rolled_back")
