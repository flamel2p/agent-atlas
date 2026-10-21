"""Behavioral checks for durable checkpoints, authority, and crash boundaries."""

from __future__ import annotations

from contextlib import closing, redirect_stdout
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from agentic_workflow.cli import main
from agentic_workflow.domain import InputError, Profile, RequestInput
from agentic_workflow.store import DAY_MS, Store, WorkflowError


def request(request_id="r1", equipment="keyboard", quantity=1,
            requester="alice") -> RequestInput:
    return RequestInput.from_json_bytes(json.dumps({
        "request_id": request_id, "requester_id": requester,
        "equipment_code": equipment, "quantity": quantity,
        "justification": "Synthetic equipment request",
    }).encode())


class Clock:
    def __init__(self, now=1_000_000):
        self.now = now

    def __call__(self):
        return self.now


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "workflow.sqlite"
        self.clock = Clock()
        self.store = Store(self.db, clock=self.clock)
        self.store.init()

    def assert_code(self, code, call):
        with self.assertRaises(WorkflowError) as raised:
            call()
        self.assertEqual(raised.exception.code, code)

    def test_routine_price_events_and_unique_effect(self):
        submitted = self.store.submit(request(), Profile.SUCCESS, "s1")
        self.assertEqual((submitted["request"]["total_sen"], submitted["request"]["version"]),
                         (25_000, 1))
        self.assertEqual(self.store.advance("r1", "a1")["code"], "ready")
        done = self.store.advance("r1", "a2")
        self.assertEqual(done["code"], "fulfilled")
        self.assertEqual(done["request"]["attempts"], 1)
        self.assertEqual(done["request"]["fulfillment"]["receipt"], "synthetic-r1-1")
        self.assertEqual(self.store.advance("r1", "a3")["code"], "terminal_noop")
        self.assertEqual([e["seq"] for e in self.store.audit("r1")["events"]], [1, 2, 3])
        with closing(sqlite3.connect(self.db, autocommit=True)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM fulfillments").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM commands").fetchone()[0], 4)

    def test_review_guards_checkpoint_and_rejection(self):
        self.store.submit(request(equipment="laptop", requester="ops-reviewer"), Profile.SUCCESS, "s1")
        self.assertEqual(self.store.advance("r1", "a1")["code"], "awaiting_review")
        self.assertEqual(self.store.advance("r1", "a2")["code"], "awaiting_review")
        self.assertEqual(self.store.advance("r1", "a2")["code"], "awaiting_review")
        self.assert_code("reviewer_forbidden", lambda: self.store.review(
            "r1", "rv0", decision="approve", reviewer="unknown",
            review_reason="Fine", expected_version=2))
        self.assert_code("self_review", lambda: self.store.review(
            "r1", "rv1", decision="approve", reviewer="ops-reviewer",
            review_reason="Fine", expected_version=2))
        self.assert_code("stale_version", lambda: self.store.review(
            "r1", "rv2", decision="approve", reviewer="finance-reviewer",
            review_reason="Fine", expected_version=1))
        self.assertEqual(self.store.show("r1")["request"]["version"], 2)
        self.assertEqual(len(self.store.audit("r1")["events"]), 2)
        with closing(sqlite3.connect(self.db, autocommit=True)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM commands").fetchone()[0], 3)
        approved = self.store.review("r1", "rv3", decision="approve",
                                      reviewer="finance-reviewer", review_reason="Allowed",
                                      expected_version=2)
        self.assertEqual(approved["code"], "ready")
        self.assertIsNone(approved["request"]["fulfillment"])
        self.assertEqual(self.store.advance("r1", "a3")["code"], "fulfilled")
        self.assertEqual(self.store.advance("r1", "a2")["code"], "awaiting_review")
        self.assertEqual(self.store.review("r1", "rv3", decision="approve",
                                           reviewer="finance-reviewer", review_reason="Allowed",
                                           expected_version=2), approved)
        self.assertEqual(self.store.show("r1")["request"]["attempts"], 1)
        self.assert_code("terminal_state", lambda: self.store.review(
            "r1", "rv4", decision="reject", reviewer="finance-reviewer",
            review_reason="Too late", expected_version=4))

    def test_reject_cancel_expire_and_terminal_immutability(self):
        self.store.submit(request("reject", "monitor", 2), Profile.SUCCESS, "s1")
        self.store.advance("reject", "a1")
        self.assertEqual(self.store.review("reject", "rv1", decision="reject",
                                           reviewer="finance-reviewer", review_reason="Budget",
                                           expected_version=2)["code"], "rejected")
        self.assert_code("terminal_state", lambda: self.store.cancel("reject", "c1", cancel_reason="No"))
        self.store.submit(request("cancel"), Profile.SUCCESS, "s2")
        self.assertEqual(self.store.cancel("cancel", "c2", cancel_reason="Withdrawn")["code"], "cancelled")
        self.assertEqual(self.store.advance("cancel", "a2")["code"], "terminal_noop")
        self.store.submit(request("expire", "laptop"), Profile.SUCCESS, "s3")
        self.store.advance("expire", "a3")
        self.clock.now += DAY_MS
        self.assertEqual(self.store.show("expire")["request"]["state"], "awaiting_review")
        self.assertTrue(self.store.show("expire")["deadline_elapsed"])
        self.assert_code("stale_version", lambda: self.store.review(
            "expire", "rv2", decision="approve", reviewer="ops-reviewer",
            review_reason="Late", expected_version=1))
        self.assertEqual(self.store.review("expire", "rv3", decision="approve",
                                           reviewer="ops-reviewer", review_reason="Late",
                                           expected_version=2)["code"], "expired")
        self.assertEqual(Store(self.db, clock=self.clock).show("expire")["request"]["state"], "expired")
        self.assertEqual(self.store.advance("expire", "a4")["code"], "terminal_noop")

    def test_command_replay_and_duplicate_submission_expiry(self):
        first = self.store.submit(request(), Profile.SUCCESS, "s1")
        self.store.advance("r1", "a1")
        self.assertEqual(self.store.submit(request(), Profile.SUCCESS, "s1"), first)
        self.assert_code("command_conflict", lambda: self.store.submit(
            request("different"), Profile.SUCCESS, "s1"))
        self.assert_code("request_conflict", lambda: self.store.submit(
            request(), Profile.PERMANENT_FAILURE, "s2"))
        duplicate = self.store.submit(request(), Profile.SUCCESS, "s2")
        self.assertEqual(duplicate["code"], "duplicate_submission")
        self.assertEqual(len(self.store.audit("r1")["events"]), 2)
        with closing(sqlite3.connect(self.db, autocommit=True)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM commands").fetchone()[0], 3)
        self.clock.now += DAY_MS
        expired = self.store.submit(request(), Profile.SUCCESS, "s3")
        self.assertEqual(expired["code"], "expired")
        self.assertEqual(self.store.submit(request(), Profile.SUCCESS, "s2"), duplicate)
        self.assertEqual(self.store.submit(request(), Profile.SUCCESS, "s3"), expired)
        self.assertEqual(len(self.store.audit("r1")["events"]), 3)

    def test_retry_due_time_and_three_attempt_limit_across_store_reopen(self):
        self.store.submit(request(), Profile.ALWAYS_TRANSIENT, "s1")
        self.store.advance("r1", "a1")
        first = self.store.advance("r1", "a2")
        self.assertEqual((first["code"], first["request"]["attempts"]), ("retry_wait", 1))
        reopened = Store(self.db, clock=self.clock)
        waiting = reopened.advance("r1", "a3")
        self.assertEqual(waiting["code"], "retry_not_due")
        self.assertEqual(waiting["request"]["attempts"], 1)
        self.clock.now += 1000
        second = reopened.advance("r1", "a4")
        self.assertEqual(second["request"]["next_attempt_at"], self.clock.now + 2000)
        self.clock.now += 2000
        third = reopened.advance("r1", "a5")
        self.assertEqual((third["code"], third["request"]["attempts"]), ("failed", 3))
        self.assertEqual(reopened.advance("r1", "a6")["code"], "terminal_noop")
        self.assertEqual(reopened.advance("r1", "a3"), waiting)
        self.assertEqual(reopened.show("r1")["request"]["attempts"], 3)
        self.assertEqual(len(reopened.audit("r1")["events"]), 5)

    def test_transient_once_and_permanent_failure(self):
        for name, profile in (("once", Profile.TRANSIENT_ONCE),
                              ("permanent", Profile.PERMANENT_FAILURE)):
            with self.subTest(profile=profile):
                self.store.submit(request(name), profile, f"s-{name}")
                self.store.advance(name, f"a-{name}")
                first = self.store.advance(name, f"b-{name}")
                if profile == Profile.PERMANENT_FAILURE:
                    self.assertEqual((first["code"], first["request"]["attempts"]), ("failed", 1))
                else:
                    self.clock.now += 1000
                    done = self.store.advance(name, f"c-{name}")
                    self.assertEqual((done["code"], done["request"]["attempts"]), ("fulfilled", 2))

    def test_valid_late_state_ineligible_action_expires_invalid_actor_does_not(self):
        self.store.submit(request(), Profile.SUCCESS, "s1")
        self.store.advance("r1", "a1")
        self.clock.now += DAY_MS
        self.assert_code("reviewer_forbidden", lambda: self.store.review(
            "r1", "r-bad", decision="approve", reviewer="stranger",
            review_reason="Late", expected_version=2))
        self.assertEqual(self.store.show("r1")["request"]["state"], "ready")
        late = self.store.review("r1", "r-late", decision="approve",
                                 reviewer="ops-reviewer", review_reason="Late", expected_version=2)
        self.assertEqual(late["code"], "expired")
        self.assertEqual(self.store.show("r1")["request"]["attempts"], 0)

    def test_invalid_input_and_database_identity(self):
        base = {"request_id": "x", "requester_id": "alice", "equipment_code": "keyboard",
                "quantity": 1, "justification": "Need"}
        for raw in (b'{"request_id":"x","request_id":"x"}',
                    json.dumps(base | {"quantity": True}).encode(),
                    json.dumps(base | {"price": 0}).encode(),
                    json.dumps(base | {"quantity": 1.0}).encode(),
                    json.dumps(base | {"quantity": float("nan")}).encode(),
                    (b"[" * 600) + b"0" + (b"]" * 600),
                    b"x" * (16 * 1024 + 1)):
            with self.subTest(raw=raw[:40]), self.assertRaises(InputError):
                RequestInput.from_json_bytes(raw)
        self.assert_code("database_missing", lambda: Store(Path(self.temp.name) / "missing.sqlite").show("x"))
        incompatible = Path(self.temp.name) / "other.sqlite"
        sqlite3.connect(incompatible).execute("CREATE TABLE foreign_data (value TEXT)").connection.close()
        self.assert_code("database_incompatible", lambda: Store(incompatible).init())
        empty = Path(self.temp.name) / "empty.sqlite"
        empty.touch()
        self.assertEqual(Store(empty).init()["code"], "initialized")
        for name, ddl in (("view.sqlite", "CREATE VIEW foreign_view AS SELECT 1 AS value"),
                          ("prefix.sqlite", "CREATE TABLE sqliteXnotes (value TEXT)")):
            foreign = Path(self.temp.name) / name
            with closing(sqlite3.connect(foreign, autocommit=True)) as conn:
                conn.execute(ddl)
            self.assert_code("database_incompatible", lambda foreign=foreign: Store(foreign).init())
        branded = Path(self.temp.name) / "branded.sqlite"
        with closing(sqlite3.connect(branded, autocommit=True)) as conn:
            conn.execute("PRAGMA application_id=777")
        self.assert_code("database_incompatible", lambda: Store(branded).init())
        incompatible.write_bytes(b"not sqlite")
        self.assert_code("database_incompatible", lambda: Store(incompatible).show("x"))
        self.assertEqual(incompatible.read_bytes(), b"not sqlite")
        special = Path(self.temp.name) / "name?#.sqlite"
        special_store = Store(special)
        special_store.init()
        special_store.submit(request("special"), Profile.SUCCESS, "special-command")
        self.assertEqual(Store(special).show("special")["request"]["state"], "submitted")
        with closing(sqlite3.connect(self.db, autocommit=True)) as conn:
            conn.execute("ALTER TABLE requests ADD COLUMN unapproved TEXT")
        self.assert_code("database_incompatible", lambda: self.store.show("r1"))

    def test_write_failure_rolls_back_all_records(self):
        def fail():
            raise RuntimeError("injected before commit")
        faulted = Store(self.db, clock=self.clock, before_commit=fail)
        with self.assertRaisesRegex(RuntimeError, "injected"):
            faulted.submit(request(), Profile.SUCCESS, "s1")
        with closing(sqlite3.connect(self.db, autocommit=True)) as conn:
            for table in ("requests", "events", "commands", "fulfillments"):
                self.assertEqual(conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)
        self.assertEqual(self.store.submit(request(), Profile.SUCCESS, "s1")["code"], "submitted")

    def test_invalid_unicode_returns_json_error_without_mutation(self):
        self.store.submit(request(equipment="laptop"), Profile.SUCCESS, "s1")
        self.store.advance("r1", "a1")
        before = self.store.show("r1")
        for invalid_text in (chr(0xD800), chr(0xDC00)):
            source = Path(self.temp.name) / "invalid-unicode.json"
            source.write_text(json.dumps({"request_id": "bad", "requester_id": "alice",
                "equipment_code": "keyboard", "quantity": 1, "justification": invalid_text}))
            commands = (
                ["submit", str(source), "--command-id", "bad-submit"],
                ["review", "r1", "--command-id", "bad-review", "--decision", "approve",
                 "--reviewer", "ops-reviewer", "--expected-version", "2", "--reason", invalid_text],
                ["cancel", "r1", "--command-id", "bad-cancel", "--reason", invalid_text],
            )
            for args in commands:
                with self.subTest(operation=args[0], character=ord(invalid_text)):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        status = main([*args, "--db", str(self.db)])
                    self.assertEqual(status, 2)
                    self.assertEqual(json.loads(output.getvalue())["code"], "invalid_input")
                    self.assertEqual(self.store.show("r1"), before)
        self.assert_code("request_missing", lambda: self.store.show("bad"))
        source.write_text(json.dumps({
            "request_id": "unicode", "requester_id": "alice", "equipment_code": "keyboard",
            "quantity": 1, "justification": "Keyboard for \U0001f600 lab"}))
        result = self.cli("submit", str(source), "--command-id", "unicode-submit")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["request"]["justification"], "Keyboard for \U0001f600 lab")

    def test_memory_named_path_is_a_durable_file(self):
        def run(*args):
            return subprocess.run([sys.executable, "-m", "agentic_workflow.cli", *args,
                                   "--db", ":memory:"], cwd=self.temp.name, text=True,
                                  capture_output=True, timeout=5)
        initialized = run("init")
        self.assertEqual(initialized.returncode, 0)
        self.assertTrue((Path(self.temp.name) / ":memory:").is_file())
        missing = run("show", "unknown")
        self.assertEqual(missing.returncode, 2)
        self.assertEqual(json.loads(missing.stdout)["code"], "request_missing")

    def test_sqlite_commit_busy_rolls_back_effect_and_all_state(self):
        self.store.submit(request(), Profile.SUCCESS, "s1")
        self.store.advance("r1", "a1")
        snapshot = self.store.show("r1")
        events = self.store.audit("r1")
        reached_commit = []
        writer = Store(self.db, clock=self.clock,
                       before_commit=lambda: reached_commit.append(True))
        with closing(sqlite3.connect(self.db, autocommit=True)) as reader:
            reader.execute("BEGIN")
            reader.execute("SELECT request_id FROM requests").fetchall()
            try:
                self.assert_code("storage_busy", lambda: writer.advance("r1", "commit-busy"))
                self.assertEqual(reached_commit, [True])
            finally:
                reader.execute("ROLLBACK")
        self.assertEqual(self.store.show("r1"), snapshot)
        self.assertEqual(self.store.audit("r1"), events)
        with closing(sqlite3.connect(self.db, autocommit=True)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM fulfillments").fetchone()[0], 0)
            self.assertIsNone(conn.execute("SELECT 1 FROM commands WHERE command_id='commit-busy'").fetchone())
        self.assertEqual(self.store.advance("r1", "commit-busy")["code"], "fulfilled")

    def test_effect_and_event_failures_rollback_snapshot_and_receipt(self):
        self.store.submit(request(), Profile.SUCCESS, "s1")
        self.store.advance("r1", "a1")

        class EventFaultStore(Store):
            def _event(self, *args, **kwargs):
                raise sqlite3.OperationalError("injected event write error")

        faulted_event = EventFaultStore(self.db, clock=self.clock)
        self.assert_code("storage_error", lambda: faulted_event.advance("r1", "a2"))
        self.assertEqual(self.store.show("r1")["request"]["state"], "ready")
        with closing(sqlite3.connect(self.db, autocommit=True)) as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM fulfillments WHERE request_id='r1'").fetchone())
            self.assertIsNone(conn.execute("SELECT 1 FROM commands WHERE command_id='a2'").fetchone())
        self.assertEqual(self.store.advance("r1", "a2")["code"], "fulfilled")

        self.store.submit(request("r2"), Profile.SUCCESS, "s2")
        self.store.advance("r2", "b1")
        faulted_commit = Store(self.db, clock=self.clock,
                               before_commit=lambda: (_ for _ in ()).throw(RuntimeError("commit fault")))
        with self.assertRaisesRegex(RuntimeError, "commit fault"):
            faulted_commit.advance("r2", "b2")
        self.assertEqual(self.store.show("r2")["request"]["state"], "ready")
        with closing(sqlite3.connect(self.db, autocommit=True)) as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM fulfillments WHERE request_id='r2'").fetchone())
            self.assertIsNone(conn.execute("SELECT 1 FROM commands WHERE command_id='b2'").fetchone())
        self.assertEqual(self.store.advance("r2", "b2")["code"], "fulfilled")

    def test_lock_contention_is_bounded_and_retryable(self):
        self.clock.now = time.time_ns() // 1_000_000
        self.store.submit(request(), Profile.SUCCESS, "s1")
        with closing(sqlite3.connect(self.db, autocommit=True)) as blocker:
            blocker.execute("BEGIN IMMEDIATE")
            result = self.cli("advance", "r1", "--command-id", "a1")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["code"], "storage_busy")
            blocker.execute("ROLLBACK")
        self.assertEqual(json.loads(self.cli("advance", "r1", "--command-id", "a1").stdout)["code"], "ready")

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "agentic_workflow.cli", *args,
                               "--db", str(self.db)], text=True, capture_output=True,
                              timeout=5)

    def test_subprocess_restart_review_and_race(self):
        source = Path(self.temp.name) / "request.json"
        source.write_text(json.dumps({"request_id": "subprocess", "requester_id": "alice",
                                      "equipment_code": "laptop", "quantity": 1,
                                      "justification": "Lab"}))
        self.assertEqual(json.loads(self.cli("submit", str(source), "--command-id", "s1").stdout)["code"], "submitted")
        self.assertEqual(json.loads(self.cli("advance", "subprocess", "--command-id", "a1").stdout)["code"], "awaiting_review")
        commands = [[sys.executable, "-m", "agentic_workflow.cli", "review", "subprocess",
                     "--db", str(self.db), "--command-id", command_id,
                     "--decision", "approve", "--reviewer", "ops-reviewer",
                     "--reason", "Allowed", "--expected-version", "2"]
                    for command_id in ("rv1", "rv2")]
        processes = [subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE) for cmd in commands]
        results = [process.communicate(timeout=5)[0] for process in processes]
        self.assertCountEqual([json.loads(result)["code"] for result in results], ["ready", "stale_version"])
        self.assertEqual(json.loads(self.cli("show", "subprocess").stdout)["request"]["version"], 3)
        commands = [[sys.executable, "-m", "agentic_workflow.cli", operation,
                     "subprocess", "--db", str(self.db), "--command-id", command_id,
                     *extra] for operation, command_id, extra in (
                         ("advance", "a2", []), ("cancel", "c1", ["--reason", "Withdrawn"]))]
        processes = [subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE) for cmd in commands]
        results = [json.loads(process.communicate(timeout=5)[0]) for process in processes]
        state = json.loads(self.cli("show", "subprocess").stdout)["request"]
        self.assertIn(state["state"], ("fulfilled", "cancelled"))
        self.assertLessEqual(sum(1 for result in results if result["code"] == "fulfilled"), 1)
        with closing(sqlite3.connect(self.db, autocommit=True)) as conn:
            self.assertLessEqual(conn.execute("SELECT count(*) FROM fulfillments").fetchone()[0], 1)

    def test_process_death_before_commit_and_lost_response_after_commit(self):
        script = """import os, sys
from agentic_workflow.domain import Profile, RequestInput
from agentic_workflow.store import Store
raw = b'{"request_id":"dead","requester_id":"alice","equipment_code":"keyboard","quantity":1,"justification":"Lab"}'
store = Store(sys.argv[1], before_commit=(lambda: os._exit(73)) if sys.argv[2] == 'before' else None)
store.submit(RequestInput.from_json_bytes(raw), Profile.SUCCESS, 's-dead')
os._exit(74)
"""
        before = subprocess.run([sys.executable, "-c", script, str(self.db), "before"], timeout=5)
        self.assertEqual(before.returncode, 73)
        self.assert_code("request_missing", lambda: self.store.show("dead"))
        after = subprocess.run([sys.executable, "-c", script, str(self.db), "after"], timeout=5)
        self.assertEqual(after.returncode, 74)
        saved = self.store.show("dead")["request"]
        self.assertEqual(saved["version"], 1)
        replay = self.store.submit(RequestInput.from_json_bytes(
            b'{"request_id":"dead","requester_id":"alice","equipment_code":"keyboard","quantity":1,"justification":"Lab"}'),
            Profile.SUCCESS, "s-dead")
        self.assertEqual(replay["request"], saved)
        self.assertEqual(len(self.store.audit("dead")["events"]), 1)


if __name__ == "__main__":
    unittest.main()
