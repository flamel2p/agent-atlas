# Conversational Agent specification

Slug: 16-conversational
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Problem and scope

A learner explores three synthetic courses through short English turns. The learning objective is dialogue management with stable persona, recent context, durable explicit preferences, clarification, and a gate before ordinary memory processing. Responses and intent recognition are deterministic fixtures. Supported dialogue is a documented finite grammar, not general natural-language understanding.

## Evidence and decisions

Source facts are recorded in the [retained brief](../../agent-library-analysis/agents/16-conversational.md). Chapter 10 describes an entry sentinel, working and archived memory, a dialog manager, and a stable persona. Its snippets do not integrate long-term retrieval into the turn handler or implement durable user isolation. Recorded locators are printed pp.282-293 and 1-based PDF pp.313-324. The original book was not re-inspected for this implementation.

Selected decisions follow the brief's synthetic course-navigation proposal. Use stdlib SQLite and frozen domain records. Archive only an explicit `lesson_style` preference, `short` or `standard`. Working memory is bounded recent completed turns plus authoritative session state. This case does not call archived preferences semantic knowledge or infer a profile. A host-owned fixture composer receives validated course/context/preference data and cannot change policy.

Normalized state is selected over an event journal. Current focus, pending choices, and preference replacement are direct transactional updates. Event replay would add versioning and compaction beyond the objective. There is no LLM/provider, vector database, summary model, authenticated human handoff, or deployment.

## Inputs and outputs

Public commands are one `turn` with user label, session label, and message, plus an explicit user-scoped `forget` command. User/session/workspace labels use a bounded ASCII allowlist. A message is nonempty, at most 500 characters, and rejects control characters. The CLI uses a named workspace under the current case directory's `private-data/`; reject traversal, symlink components, and nonregular database files. Run commands from this case directory or an isolated copy. The application has no arbitrary file-path or SQL input.

Bundled synthetic course IDs and facts are immutable packaged resources. The three courses have distinct titles, durations, prerequisites, and short descriptions. The finite grammar below includes course listing, course overview, duration/prerequisite questions, singular follow-ups, choice clarification, explicit lesson-style preference writes/corrections, help, and goodbye. Requests with multiple course matches preserve candidates and ask for a choice. A new explicit topic replaces prior focus. Unsupported input and configured benign scope/persona triggers return `out_of_scope` with no storage access or composition. The gate's finite matching rules do not guarantee semantic safety coverage.

Every result is a bounded JSON record with status, host-composed response, dialogue state, selected course if any, preference used if any, and a trace sufficient to establish gate/context/composition/persistence decisions. No traceback, raw database error, credentials, or other users' data enters public output. Success is returned only after commit. Exact status names and CLI exit codes are defined below.

### Selected finite grammar

Matching ignores English letter case, collapses whitespace, and removes trailing question marks, exclamation marks, and periods. No other free-form text is accepted. A message containing one of `ignore previous`, `change your persona`, `act as`, `system prompt`, `weather`, or `stock price` is gated first, even if it also contains a supported preference or course request. Any unsupported or mixed request is then gated as a whole, before any preference write. Input validation precedes the gate.

The packaged courses are `python` / Python Foundations, 6 hours, `workflows` / Workflow Automation, 8 hours, and `agents` / Agent Design, 10 hours. Their exact prerequisites and descriptions are in [courses.json](src/conversational/data/courses.json). Accepted course aliases are `python foundations`, `python`, `workflow automation`, `workflows`, `automation`, `agent design`, `agents`, and `agent`.

In the templates below, `C` is one course alias or multiple aliases joined by `and`, `or`, or a comma. Candidate order follows first occurrence, and repeated aliases for one course collapse to one candidate.

| Intent | Accepted turns |
| --- | --- |
| Help | `help`, `hello`, `hi` |
| List and choose | `list courses`, `courses`, `what courses are available` |
| Overview | `C`, `tell me about C`, `what is C`, `what are C`, `overview of C` |
| Duration | `how long is C`, `how long are C`, `how long does C take`, `duration of C`, `C duration`, `what is the duration of C` |
| Prerequisites | `what are the prerequisites for C`, `prerequisites for C`, `C prerequisites`, `what do i need for C` |
| Singular overview | `tell me more`, `tell me about it`, `overview` |
| Singular duration | `how long is it`, `how long does it take`, `duration` |
| Singular prerequisites | `prerequisites`, `what are the prerequisites`, `what does it require` |
| Choice | `1`, `first`, `the first`, `2`, `second`, `the second`, `3`, `third`, `the third` |
| Invalid-choice clarification | `4`, `fourth` |
| Explicit preference | One of `remember lesson style`, `set lesson style`, `use`, or `actually use`, followed by `short` or `standard`, optionally followed by `lessons` |
| Recent working context | `recap` |
| Closure | `goodbye`, `bye`, `quit` |

Listing enters choosing state with all three courses in displayed order and overview as the pending detail. Ambiguous detail questions preserve their requested detail. An invalid ordinal or singular follow-up while choosing preserves pending candidates and asks again. A bare candidate name resolves that pending detail. A different explicit course or full explicit course question replaces the pending topic. Help, recap, and preference updates preserve the current state. A singular follow-up in ready state asks for a course. Recap lists distinct course titles represented by the previous four completed turns in chronological first-occurrence order. Recap never searches another session.

### Selected public results

The JSON fields are `status`, `response`, `state`, `course_id`, `preference_used`, and `trace`. `response` contains at most 1,200 characters. `state` is `ready`, `choosing`, `focused`, `closed`, or null when no dialogue state is returned. `course_id` identifies a course used in this response, so help, recap, listing, and clarification return null. `preference_used` is `short`, `standard`, or null for a result that bypasses ordinary dialogue. Default style is standard. The host response prefix is always `Course guide: `. Short overview gives the course title and duration. Standard overview also gives description and prerequisites. Other facts do not change with style.

| Status | Exit code | Persisted outcome |
| --- | --- | --- |
| `answered` | 0 | One completed turn and its state |
| `clarification` | 0 | One completed turn and preserved or new clarification state |
| `preference_updated` | 0 | One completed turn, session state, and replacement preference |
| `session_closed` | 0 | One completed turn and terminal closed state |
| `already_closed` | 0 | No dialogue mutation or composition |
| `out_of_scope` | 0 | No store creation, reads, writes, or composition |
| `forgotten` | 0 | Atomic user deletion, no ordinary turn |
| `invalid_input` | 2 | No storage access |
| `limit` | 3 | No committed state change or composition |
| `storage_error` | 4 | No committed dialogue change, including invalid composer output or transactional exceptions |
| `cancelled` | 130 | The CLI catches interruption and any open transaction rolls back |

Trace values describe gate, context, preference eligibility, composition, and commit decisions. Failure traces distinguish context not loaded and composition skipped, attempted, or completed before rollback. They contain no raw text, SQL, paths, or exception details. `--help` prints CLI usage instead of a dialogue result. A broken output stream exits 1 and cannot guarantee delivery of JSON or undo a completed commit.

## Architecture and state

The public service receives a typed turn request. A pure parser/gate precedes the store. The dialogue policy consumes a scoped immutable snapshot and returns a typed next state and response plan. A deterministic composer renders the plan under one stable concise course-guide persona. SQLite owns atomic loading, response-associated state updates, and recent-turn retention.

Session state is an explicit variant or equivalent enum-backed record with valid combinations for `ready`, `choosing`, `focused`, and `closed`. Choosing state retains candidate course IDs and pending detail intent. A singular follow-up resolves only one focused course. A choice resolves only against persisted candidates. A new session restores the user's unexpired preference but never another session's focus or turns. History trimming cannot erase the authoritative session state. No previous-session raw turns enter response composition.

State uses exact `(user_id, session_id)` keys and a user-scoped preference row. The same session label across users is independent. History/session/user caps and preference/session expiry are defined below and enforced in code. A limit rejects the request without silently evicting another user's eligible state. An expired preference is unavailable before composition. Expired session context cannot resolve a follow-up. Retention is local logical deletion, not secure erasure or encrypted storage.

### Selected persistence and limits

Labels match `[A-Za-z0-9][A-Za-z0-9_-]{0,31}` exactly. Labels remain case-sensitive. Messages are 1 to 500 characters, contain non-whitespace text, and reject Unicode control, format, surrogate, private-use, and unassigned characters. The public CLI accepts no database path. It resolves `private-data/<workspace>/state.sqlite3` below the invocation directory. Existing symlinks, nonregular files, or multiply linked database/journal/WAL/SHM files are rejected. Directory symlinks are rejected. New directories use mode 0700 and a new database uses 0600. Existing file modes are preserved. A database without write permission fails explicitly.

The database is limited to 2 MiB and 512 SQLite pages. Every open validates exact schema version 1 and table definitions, checks SQLite integrity, and validates the bounded stored rows before expiry. Invalid phase combinations, course IDs, styles, timestamps, history sequences, foreign keys, provenance field shapes, or extra schema objects fail without resetting the database. SQLite busy timeout is 200 ms. There is no application retry. Failure or cancellation can leave a newly initialized empty schema, but never a partially saved dialogue turn.

| Limit | Value and accounting |
| --- | --- |
| Users | 8 distinct labels across unexpired sessions and preferences |
| Sessions per user | 4, including closed sessions |
| Sessions per workspace | 16 total, including closed sessions |
| Completed turns per session | 40 cumulative until session expiry or forgetting |
| Retained completed turns | Latest 4 canonical recognized intents and host responses per session |
| Session expiry | 24 hours since the last committed ordinary turn, expired at the exact boundary |
| Preference expiry | 30 days since the last explicit preference save, expired at the exact boundary |

Global expiry cleanup runs inside an accepted request's transaction before context retrieval and cap accounting. Gated or invalid input does not sweep storage. A failed or limited turn rolls cleanup back. Reads do not refresh preference expiry. Already-closed replies do not refresh session expiry or commit cleanup. An expired session label starts ready again, with an unexpired user preference if present. Limits reject requests without evicting any eligible user/session. Forget remains available at limits.

The session row owns the current state and cumulative counter. Canonical recent history drives recap, while focus survives history trimming. History stores no raw input. A preference row stores the current style and its explicit source session and turn number. Preference correction replaces the row. It retains no superseded preference value or separate lineage, and preference-update history uses a generic intent and response without the value. Preference provenance can outlive its source session. If that session label still exists, its last update cannot predate the preference save. Equal timestamps also require the preference source turn to be no greater than the session counter. Older provenance can belong to an expired generation of a reused label, so its counter is not compared to the new session. These consistency checks do not authenticate externally modified records or reconstruct deleted source evidence. This is local retention, not identity verification or privacy against filesystem administrators.

One bounded SQLite transaction commits session state, completed user/assistant turn, and explicit preference changes together. Failures roll back the turn. No automatic application retries. A busy database terminates within the configured SQLite timeout. Validate schema version and fail explicitly on corrupt or incompatible state. Forget deletes only the selected user's preference, turns, and sessions transactionally and is idempotent. It creates no ordinary dialogue memory.

## Tools and authority

Only local packaged catalogue reads and guarded workspace SQLite writes are permitted. The host chooses grammar, persona, facts, session transitions, memory eligibility, expiry, and limits. User text cannot supply policy, SQL, paths, arbitrary preference keys, tools, or course facts. Gated text never becomes normal memory. Namespaces demonstrate logical isolation only, without authentication, encryption, multi-process security, or protection against a malicious local filesystem actor.

## Execution and termination

1. Validate CLI arguments and bounded text.
2. Parse and gate before storage access or response composition. Stop on gated input.
3. Open the guarded store with a finite busy timeout and validate its schema.
4. In one transaction, load only the user's eligible preference and selected session. Apply expiry and caps.
5. Compute one dialogue transition. Compose at most one response. A closed session accepts no further dialogue mutations.
6. Commit all allowed changes and bounded recent history atomically. Return one JSON result and stop.

There is no autonomous conversation loop, retry loop, provider call, or external effect. Invalid input, limit exhaustion, storage failure, broken output, and cancellation terminate explicitly. A process interrupted before commit leaves no partial turn. Once commit succeeds, output loss may hide a completed turn; request deduplication is outside scope and must be disclosed.

## Acceptance criteria

All criteria use fixture/local SQLite evidence.

1. A course question followed by a singular duration question resolves the selected course, including after process restart in the same session.
2. An explicit lesson-style preference affects later composition in another session and survives restart. Correction replaces it. A fresh user receives the default.
3. Ambiguous course mentions enter choosing state. Supported choice replies resolve only the recorded candidates. A follow-up without focus clarifies without fabricating a course.
4. A gated request containing preference text invokes neither storage nor the composer and enters no ordinary memory. Persona cannot change through user text.
5. New sessions and other users cannot recover another session's focus or another user's preference. Exact session labels shared by users remain isolated.
6. History retention, expiry, user/session caps, input bounds, closed-session stopping, and idempotent forgetting have observable boundary checks.
7. Injected persistence failure rolls back every turn-associated mutation. Busy, corrupt, incompatible, unsafe-path, and unwritable storage fail explicitly with no raw error leakage.
8. Source-checkout commands, case-only copied installation, and installed-wheel execution succeed without siblings, credentials, network, or repository `PYTHONPATH`. Packaged course facts remain available.

## Dependencies and open decisions

Python 3.14.8, stdlib runtime, a case-local uv lock, and Hatchling 1.32.4 for packaging. Offline installation and wheel execution establish local compatibility only. No service/API compatibility claim or material product decision remains open.
