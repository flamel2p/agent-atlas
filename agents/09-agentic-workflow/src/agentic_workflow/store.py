"""Own SQLite identity, snapshots, history, and all command transactions.

Every mutation starts a short BEGIN IMMEDIATE transaction. Its command receipt,
snapshot, one state event, and optional synthetic fulfillment record commit as a
unit. The request snapshot is authoritative; events are ordered application
history, not a tamper-proof or replay-derived source of truth. A stored command
response is a historical receipt: replay returns it byte-for-byte as parsed JSON
even if the request has since advanced. Call show to inspect current state.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Iterator

from .domain import (POLICY_VERSION, REVIEWERS, Profile, RequestInput, State,
                     TERMINAL, digest, identifier, reason, simulate, InputError)


APP_ID = 0x41473039
SCHEMA_VERSION = 1
IDENTITY = "agentic-workflow-demo-v1"
DAY_MS = 86_400_000
SCHEMA = (
    "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    """CREATE TABLE requests (
        request_id TEXT PRIMARY KEY,
        requester_id TEXT NOT NULL, equipment_code TEXT NOT NULL,
        quantity INTEGER NOT NULL, justification TEXT NOT NULL,
        fingerprint TEXT NOT NULL, profile TEXT NOT NULL,
        policy_version TEXT NOT NULL, total_sen INTEGER NOT NULL,
        needs_review INTEGER NOT NULL, state TEXT NOT NULL,
        version INTEGER NOT NULL, attempts INTEGER NOT NULL,
        created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL, next_attempt_at INTEGER,
        review_decision TEXT, reviewer_id TEXT, review_reason TEXT,
        result_reason TEXT
    )""",
    """CREATE TABLE events (
        request_id TEXT NOT NULL REFERENCES requests(request_id),
        seq INTEGER NOT NULL, command_id TEXT NOT NULL,
        old_state TEXT, new_state TEXT NOT NULL, actor TEXT NOT NULL,
        reason TEXT NOT NULL, at INTEGER NOT NULL,
        PRIMARY KEY (request_id, seq)
    )""",
    """CREATE TABLE commands (
        command_id TEXT PRIMARY KEY, command_hash TEXT NOT NULL,
        response TEXT NOT NULL
    )""",
    """CREATE TABLE fulfillments (
        request_id TEXT PRIMARY KEY REFERENCES requests(request_id),
        receipt TEXT NOT NULL UNIQUE, at INTEGER NOT NULL
    )""",
)
REQUIRED_COLUMNS = {
    "metadata": {"key", "value"},
    "requests": {"request_id", "requester_id", "equipment_code", "quantity",
                 "justification", "fingerprint", "profile", "policy_version",
                 "total_sen", "needs_review", "state", "version", "attempts",
                 "created_at", "expires_at", "updated_at", "next_attempt_at",
                 "review_decision", "reviewer_id", "review_reason", "result_reason"},
    "events": {"request_id", "seq", "command_id", "old_state", "new_state",
               "actor", "reason", "at"},
    "commands": {"command_id", "command_hash", "response"},
    "fulfillments": {"request_id", "receipt", "at"},
}


class WorkflowError(Exception):
    """Stable public error code plus a safe explanation for CLI JSON output."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class Store:
    """One transaction owner for one case-local database.

    clock returns UTC epoch milliseconds; before_commit is an optional test seam called
    before COMMIT. Neither is exposed by the normal CLI. Each public method
    opens and closes its own connection, so no process-local workflow state is
    required to resume after restart.
    """

    def __init__(self, path: str | Path, *, clock: Callable[[], int] | None = None,
                 before_commit: Callable[[], None] | None = None):
        self.path = Path(path)
        self.clock = clock or (lambda: time.time_ns() // 1_000_000)
        self.before_commit = before_commit

    def _open(self, *, creating: bool = False) -> sqlite3.Connection:
        if not creating and not self.path.is_file():
            raise WorkflowError("database_missing", "initialize the database first")
        try:
            if creating:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(self.path.resolve(), autocommit=True, timeout=1.0)
            else:
                conn = sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True,
                                       autocommit=True, timeout=1.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=1000")
            return conn
        except sqlite3.Error as exc:
            raise self._storage_error(exc) from exc
        except OSError as exc:
            raise WorkflowError("storage_error", str(exc)) from exc

    @staticmethod
    def _storage_error(exc: sqlite3.Error) -> WorkflowError:
        if isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc).lower():
            return WorkflowError("storage_busy", "database is locked; retry this command ID")
        if isinstance(exc, sqlite3.DatabaseError) and any(
            marker in str(exc).lower() for marker in ("malformed", "not a database", "disk image")
        ):
            return WorkflowError("database_incompatible", "database is corrupt or incompatible")
        return WorkflowError("storage_error", str(exc))

    @staticmethod
    def _schema_digest(conn: sqlite3.Connection) -> str:
        definitions = [tuple(row) for row in conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT GLOB 'sqlite_*' ORDER BY type, name")]
        return digest({"definitions": definitions})

    def _identity(self, conn: sqlite3.Connection) -> None:
        try:
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise WorkflowError("database_incompatible", "database integrity check failed")
            if conn.execute("PRAGMA application_id").fetchone()[0] != APP_ID or \
                    conn.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                raise WorkflowError("database_incompatible", "unsupported database identity or schema")
            row = conn.execute("SELECT value FROM metadata WHERE key='identity'").fetchone()
            if row is None or row[0] != IDENTITY:
                raise WorkflowError("database_incompatible", "unsupported database identity")
            recorded = conn.execute("SELECT value FROM metadata WHERE key='schema_digest'").fetchone()
            if recorded is None or recorded[0] != self._schema_digest(conn):
                raise WorkflowError("database_incompatible", "database schema has changed")
            names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"metadata", "requests", "events", "commands", "fulfillments"} <= names:
                raise WorkflowError("database_incompatible", "incomplete database schema")
            for table, columns in REQUIRED_COLUMNS.items():
                actual = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                if actual != columns:
                    raise WorkflowError("database_incompatible", "incompatible database columns")
        except sqlite3.Error as exc:
            if isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc).lower():
                raise self._storage_error(exc) from exc
            raise WorkflowError("database_incompatible", "database is corrupt or incompatible") from exc

    def init(self) -> dict[str, Any]:
        conn = self._open(creating=True)
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT name FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'").fetchall()
            if existing:
                self._identity(conn)
            else:
                # A crash before initial COMMIT may leave an empty file. No
                # foreign or partially populated schema is ever overwritten.
                app_id = conn.execute("PRAGMA application_id").fetchone()[0]
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                if app_id != 0 or version != 0:
                    raise WorkflowError("database_incompatible", "empty database has foreign identity")
                for statement in SCHEMA:
                    conn.execute(statement)
                conn.execute("INSERT INTO metadata VALUES ('identity', ?)", (IDENTITY,))
                conn.execute("INSERT INTO metadata VALUES ('schema_digest', ?)",
                             (self._schema_digest(conn),))
                conn.execute(f"PRAGMA application_id={APP_ID}")
                conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            conn.execute("COMMIT")
            return {"code": "initialized", "database": str(self.path)}
        except sqlite3.Error as exc:
            raise self._storage_error(exc) from exc
        finally:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            conn.close()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._open()
        try:
            yield conn
        except sqlite3.Error as exc:
            raise self._storage_error(exc) from exc
        finally:
            conn.close()

    @staticmethod
    def _snapshot(conn: sqlite3.Connection, request_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM requests WHERE request_id=?", (request_id,)).fetchone()
        if row is None:
            raise WorkflowError("request_missing", "unknown request_id")
        result = dict(row)
        result.pop("fingerprint")
        result["needs_review"] = bool(result["needs_review"])
        fulfillment = conn.execute("SELECT receipt, at FROM fulfillments WHERE request_id=?",
                                   (request_id,)).fetchone()
        result["fulfillment"] = dict(fulfillment) if fulfillment else None
        return result

    def show(self, request_id: str) -> dict[str, Any]:
        identifier(request_id, "request_id")
        with self._connection() as conn:
            self._identity(conn)
            conn.execute("BEGIN")
            snapshot = self._snapshot(conn, request_id)
            return {"code": "observed", "request": snapshot,
                    "deadline_elapsed": self.clock() >= snapshot["expires_at"]}

    def audit(self, request_id: str) -> dict[str, Any]:
        identifier(request_id, "request_id")
        with self._connection() as conn:
            self._identity(conn)
            conn.execute("BEGIN")
            self._snapshot(conn, request_id)
            events = [dict(row) for row in conn.execute(
                "SELECT * FROM events WHERE request_id=? ORDER BY seq", (request_id,))]
            return {"code": "audit", "request_id": request_id, "events": events}

    def _command(self, command_id: str, payload: dict[str, Any],
                 perform: Callable[[sqlite3.Connection, int], dict[str, Any]]) -> dict[str, Any]:
        identifier(command_id, "command_id")
        command_hash = digest(payload)
        with self._connection() as conn:
            self._identity(conn)
            try:
                conn.execute("BEGIN IMMEDIATE")
                saved = conn.execute("SELECT command_hash, response FROM commands WHERE command_id=?",
                                     (command_id,)).fetchone()
                if saved:
                    if saved["command_hash"] != command_hash:
                        raise WorkflowError("command_conflict", "command_id was used for different content")
                    conn.execute("COMMIT")
                    return json.loads(saved["response"])
                response = perform(conn, self.clock())
                conn.execute("INSERT INTO commands VALUES (?, ?, ?)",
                             (command_id, command_hash, _json(response)))
                if self.before_commit:
                    self.before_commit()
                conn.execute("COMMIT")
                return response
            except BaseException as exc:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                if isinstance(exc, sqlite3.Error):
                    raise self._storage_error(exc) from exc
                raise

    @staticmethod
    def _event(conn: sqlite3.Connection, request_id: str, command_id: str,
               old: str | None, new: str, actor: str, why: str, now: int,
               version: int) -> None:
        conn.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (request_id, version, command_id, old, new, actor, why, now))

    def submit(self, request: RequestInput, profile: Profile, command_id: str) -> dict[str, Any]:
        fingerprint = request.fingerprint(profile)
        payload = {"operation": "submit", "input": asdict(request),
                   "actor": request.requester_id, "profile": profile.value}

        def perform(conn: sqlite3.Connection, now: int) -> dict[str, Any]:
            prior = conn.execute("SELECT fingerprint FROM requests WHERE request_id=?",
                                 (request.request_id,)).fetchone()
            if prior:
                if prior[0] != fingerprint:
                    raise WorkflowError("request_conflict", "request_id has different input or profile")
                row = self._row(conn, request.request_id)
                expired = self._expire(conn, row, command_id, now)
                if expired:
                    return expired
                return {"code": "duplicate_submission", "request": self._snapshot(conn, request.request_id)}
            total, needs_review = request.assessment()
            conn.execute("""INSERT INTO requests
                (request_id, requester_id, equipment_code, quantity, justification,
                 fingerprint, profile, policy_version, total_sen, needs_review,
                 state, version, attempts, created_at, expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?)""",
                (request.request_id, request.requester_id, request.equipment_code,
                 request.quantity, request.justification, fingerprint, profile.value,
                 POLICY_VERSION, total, int(needs_review), State.SUBMITTED.value,
                 now, now + DAY_MS, now))
            self._event(conn, request.request_id, command_id, None, State.SUBMITTED.value,
                        request.requester_id, "submitted", now, 1)
            return {"code": "submitted", "request": self._snapshot(conn, request.request_id)}

        return self._command(command_id, payload, perform)

    def _transition(self, conn: sqlite3.Connection, row: sqlite3.Row, command_id: str,
                    state: State, actor: str, why: str, now: int,
                    **fields: Any) -> dict[str, Any]:
        version = row["version"] + 1
        updates = {"state": state.value, "version": version, "updated_at": now, **fields}
        assignments = ", ".join(f"{key}=?" for key in updates)
        conn.execute(f"UPDATE requests SET {assignments} WHERE request_id=?",
                     (*updates.values(), row["request_id"]))
        self._event(conn, row["request_id"], command_id, row["state"], state.value,
                    actor, why, now, version)
        return {"code": state.value, "request": self._snapshot(conn, row["request_id"])}

    def _row(self, conn: sqlite3.Connection, request_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM requests WHERE request_id=?", (request_id,)).fetchone()
        if row is None:
            raise WorkflowError("request_missing", "unknown request_id")
        return row

    def _expire(self, conn: sqlite3.Connection, row: sqlite3.Row,
                command_id: str, now: int) -> dict[str, Any] | None:
        # Deadline precedes a current, otherwise valid action, including cancel.
        if State(row["state"]) not in TERMINAL and now >= row["expires_at"]:
            return self._transition(conn, row, command_id, State.EXPIRED,
                                    "system", "deadline_elapsed", now,
                                    next_attempt_at=None, result_reason="deadline_elapsed")
        return None

    def advance(self, request_id: str, command_id: str) -> dict[str, Any]:
        identifier(request_id, "request_id")
        payload = {"operation": "advance", "request_id": request_id, "actor": "system"}

        def perform(conn: sqlite3.Connection, now: int) -> dict[str, Any]:
            row = self._row(conn, request_id)
            expired = self._expire(conn, row, command_id, now)
            if expired:
                return expired
            state = State(row["state"])
            if state == State.SUBMITTED:
                target = State.AWAITING_REVIEW if row["needs_review"] else State.READY
                return self._transition(conn, row, command_id, target, "system",
                                        "assessment", now)
            if state == State.AWAITING_REVIEW:
                return {"code": "awaiting_review", "request": self._snapshot(conn, request_id)}
            if state == State.RETRY_WAIT and now < row["next_attempt_at"]:
                return {"code": "retry_not_due", "request": self._snapshot(conn, request_id)}
            if state in TERMINAL:
                return {"code": "terminal_noop", "request": self._snapshot(conn, request_id)}
            attempt = row["attempts"] + 1
            outcome = simulate(Profile(row["profile"]), attempt)
            if outcome == "success":
                # A unique request key makes a second local effect impossible even
                # if the transition logic is accidentally invoked twice.
                receipt = f"synthetic-{request_id}-{attempt}"
                conn.execute("INSERT INTO fulfillments VALUES (?, ?, ?)",
                             (request_id, receipt, now))
                return self._transition(conn, row, command_id, State.FULFILLED,
                                        "simulator", "simulated_success", now,
                                        attempts=attempt, next_attempt_at=None,
                                        result_reason="simulated_success")
            if outcome == "permanent" or attempt >= 3:
                return self._transition(conn, row, command_id, State.FAILED,
                                        "simulator", f"{outcome}_failure", now,
                                        attempts=attempt, next_attempt_at=None,
                                        result_reason=f"{outcome}_failure")
            delay = 1000 if attempt == 1 else 2000
            return self._transition(conn, row, command_id, State.RETRY_WAIT,
                                    "simulator", "transient_failure", now,
                                    attempts=attempt, next_attempt_at=now + delay,
                                    result_reason="transient_failure")

        return self._command(command_id, payload, perform)

    def review(self, request_id: str, command_id: str, *, decision: str,
               reviewer: str, review_reason: str, expected_version: int) -> dict[str, Any]:
        identifier(request_id, "request_id")
        identifier(reviewer, "reviewer")
        review_reason = reason(review_reason)
        if decision not in {"approve", "reject"}:
            raise InputError("decision must be approve or reject")
        if type(expected_version) is not int or expected_version <= 0:
            raise InputError("expected_version must be a positive integer")
        if reviewer not in REVIEWERS:
            raise WorkflowError("reviewer_forbidden", "reviewer label is not allowlisted")
        payload = {"operation": "review", "request_id": request_id, "actor": reviewer,
                   "decision": decision, "reason": review_reason,
                   "expected_version": expected_version}

        def perform(conn: sqlite3.Connection, now: int) -> dict[str, Any]:
            row = self._row(conn, request_id)
            if reviewer == row["requester_id"]:
                raise WorkflowError("self_review", "requester cannot review own request")
            if expected_version != row["version"]:
                raise WorkflowError("stale_version", "expected_version is not current")
            if State(row["state"]) in TERMINAL:
                raise WorkflowError("terminal_state", "terminal request cannot be reviewed")
            expired = self._expire(conn, row, command_id, now)
            if expired:
                return expired
            if row["state"] != State.AWAITING_REVIEW.value:
                raise WorkflowError("invalid_state", "request is not awaiting review")
            target = State.READY if decision == "approve" else State.REJECTED
            return self._transition(conn, row, command_id, target, reviewer,
                                    review_reason, now, review_decision=decision,
                                    reviewer_id=reviewer, review_reason=review_reason,
                                    result_reason=None if decision == "approve" else "review_rejected")

        return self._command(command_id, payload, perform)

    def cancel(self, request_id: str, command_id: str, *, cancel_reason: str) -> dict[str, Any]:
        identifier(request_id, "request_id")
        cancel_reason = reason(cancel_reason)
        payload = {"operation": "cancel", "request_id": request_id,
                   "actor": "requester", "reason": cancel_reason}

        def perform(conn: sqlite3.Connection, now: int) -> dict[str, Any]:
            row = self._row(conn, request_id)
            if State(row["state"]) in TERMINAL:
                raise WorkflowError("terminal_state", "terminal request cannot be cancelled")
            expired = self._expire(conn, row, command_id, now)
            if expired:
                return expired
            return self._transition(conn, row, command_id, State.CANCELLED,
                                    row["requester_id"], cancel_reason, now,
                                    next_attempt_at=None, result_reason="cancelled")

        return self._command(command_id, payload, perform)
