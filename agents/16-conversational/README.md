# Conversational Agent

Slug: 16-conversational
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

A synthetic course guide demonstrates persistent dialogue context, explicit cross-session lesson preferences, clarification, stable persona, and a scope gate. See [SPEC.md](SPEC.md) and [PLAN.md](PLAN.md). This deterministic fixture demo has no LLM or network.

## Setup and run

Run from this directory with uv and Python 3.14.8. The offline commands require cached Python and the pinned build backend `hatchling==1.32.4`. Runtime dependencies are entirely Python stdlib. No credentials or `.env` file is needed.

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --offline --locked
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline conversational turn --workspace demo --user alice --session first --message 'Tell me about Python'
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline conversational turn --workspace demo --user alice --session first --message 'How long is it?'
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline conversational turn --workspace demo --user alice --session first --message 'Remember lesson style short'
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline conversational turn --workspace demo --user alice --session second --message 'Agent design'
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline conversational forget --workspace demo --user alice
```

Each invocation returns one JSON record and stops. The duration follow-up returns Python Foundations and 6 hours after a process restart. The new session uses the saved short style. `forget` deletes only Alice's preference, sessions, and history and can be repeated.

Workspace data is plaintext in `private-data/demo/state.sqlite3` below the current directory. Labels use 1 to 32 ASCII letters, digits, underscores, or hyphens and start with a letter or digit. Labels are case-sensitive namespaces, not authenticated identities. Run from this case directory or an isolated copy.

## Supported dialogue

Use `list courses`, then `second`, or ask `tell me about python`, `how long is workflows`, or `prerequisites for agents`. The three synthetic courses are Python Foundations, Workflow Automation, and Agent Design.

`How long are python and agents?` preserves both candidates and the pending duration question. `second` or the bare name `agents` selects Agent Design. An invalid supported choice such as `fourth` asks again. A full explicit course question changes the topic. `how long is it` and `prerequisites` use only this session's single focused course. Without one, the guide asks for a course.

Save a preference with `remember lesson style short`. Correct it with `actually use standard lessons`. No preference is inferred from casual text. `recap` lists courses represented by the latest four completed turns, and `goodbye` closes the session. `help` preserves context. See the [complete finite grammar, statuses, and exit codes](SPEC.md#selected-finite-grammar).

Unsupported input, mixed instructions, and the configured benign scope/persona triggers return `out_of_scope` before storage or composition. Input is at most 500 characters and contains no controls. Unknown text is never echoed or stored. The finite gate has no general semantic safety guarantee.

## State and authority

The host owns grammar, course facts, persona, state transitions, preference eligibility, and local writes. There is no model, arbitrary tool, SQL input, external service, or autonomous loop. Composition uses a fixed `Course guide: ` prefix and packaged facts. Typed state is ready, choosing, focused, or closed.

One SQLite transaction loads eligible context, composes once, and commits state, canonical history, and explicit preference replacement together. Success follows commit. A closed session skips composition and writes. Corrupt, incompatible, busy, unwritable, or unsafe state returns a sanitized error. Database, journal, WAL, and SHM path aliases are checked. Static checks do not protect against a malicious local filesystem actor racing replacements.

Retention is 4 recent turns, 40 cumulative turns per session, 4 sessions per user, 16 sessions per workspace, and 8 users. Closed sessions count toward caps. Session context expires after 24 hours of inactivity. Preferences expire 30 days after their last explicit save, independent of reads. A successful accepted request performs expired-state cleanup before cap accounting. A gated or failed request performs no committed cleanup. The [persistence contract](SPEC.md#selected-persistence-and-limits) gives exact boundaries.

The archive contains only the current explicit `short` or `standard` preference and its source session/turn. Correction retains no superseded value. Recent history contains canonical recognized intents and fixed responses, with generic preference-update entries. It contains no raw input. Logical deletion is not secure erasure, and SQLite is unencrypted.

## Source reading guide

Read these files in order:

1. [cli.py](src/conversational/cli.py) defines the one-turn JSON boundary, help delivery, output failure handling, and exit codes.
2. [service.py](src/conversational/service.py) validates requests and gates before store creation.
3. [domain.py](src/conversational/domain.py) defines immutable states, typed preferences, snapshots, plans, results, and limits.
4. [dialogue.py](src/conversational/dialogue.py) owns the finite grammar, pure policy, clarification, recap, and deterministic persona.
5. [courses.json](src/conversational/data/courses.json) contains the synthetic packaged facts and aliases.
6. [store.py](src/conversational/store.py) enforces guarded paths, schema validation, scoped memory, expiry, caps, and atomic commit/rollback.
7. [test_conversation.py](tests/test_conversation.py) exercises behavior, authority, isolation, limits, corruption, path aliases, and injected failures.
8. [qualify.py](scripts/qualify.py) reproduces copied-case and installed-wheel tests with actual process restarts.
9. [verify_independent.py](scripts/verify_independent.py) checks literal course facts, dialogue transitions, isolation, and no-write behavior through 99 fresh public CLI processes.

## Verification

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/qualify.py
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/verify_independent.py --cli .venv/bin/conversational --case .
```

Verified on: 2026-10-22
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/qualify.py
Verification mode: fixture
Verification result: passed
Verified scope: 43 tests in a standalone case copy and installed wheel; each environment passed 21 restart/failure CLI invocations and the independent 99-process dialogue oracle; isolated site-packages imports with no siblings, credentials, runtime network, or PYTHONPATH

The parent also passed all 43 tests in the source checkout, the standalone 99-process oracle, the five-command documented walkthrough, and document-link/whitespace checks on Python 3.14.8 on macOS. All installation, building, and testing ran offline using the existing cache. Counts describe distinct checks within each run, not different tests when repeated across environments.

Independent review found output errors for JSON and help that returned 120 or 0 instead of the promised exit 1 and raised a preference provenance consistency question. Regressions reproduced `120 != 1`, `0 != 1`, and `answered != storage_error` before their fixes. Centralized stdout handling and retained-source consistency validation now pass, including preference recall after source-session expiry and label reuse. Final independent review passed a 144-subprocess matrix covering buffered/unbuffered module and console output, help, ordinary exit codes, and closed-reader pipes with empty stderr. No actionable findings remain in the reviewed scope. Cancellation probes inject interruption at the service boundary rather than measuring signal timing. No live-model, provider, hosted CI, deployment, or production evidence is claimed.

## Limitations and references

This is a finite dialogue grammar and synthetic catalogue. Local user labels provide namespacing, not authentication. State is plaintext SQLite. No clinical or general conversational safety claim is made.

A 200 ms SQLite busy timeout bounds lock waiting, with no application retry. Composition and pre-commit failures roll back. An interrupted process before commit leaves no partial turn. Output loss after commit can hide a completed turn, and requests have no deduplication key. A broken output stream exits 1. Forgetting is scoped logical deletion, not secure erasure or deletion of backups.

Inspired by Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 10, printed pp.282-293, PDF pp.313-324, as recorded in the [retained source brief](../../agent-library-analysis/agents/16-conversational.md). Original book snippets and their source-era dependencies are not copied.
