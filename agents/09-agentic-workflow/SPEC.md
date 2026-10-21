# Agentic Workflow System specification

Slug: 09-agentic-workflow
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Problem and scope

Teach business-process developers how an equipment request pauses for review, survives process exit, resumes on an explicit decision, and recovers without repeating committed simulated effects. This independently runnable case uses synthetic data and local SQLite only.

Included behavior is deterministic assessment, durable state, command deduplication, versioned review, cancellation, expiry, bounded fulfillment retries, and ordered audit records. It uses no LLM, network service, real procurement, inventory reservation, payment, or message delivery. The risk rule is an educational baseline, not a validated procurement policy.

## Evidence and decisions

The retained [source brief](../../agent-library-analysis/agents/09-agentic-workflow.md) locates Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 7, printed pp.195-200, physical PDF pp.226-231. It describes branching workflows and console review, but does not implement restart-safe persistence, authenticated review, transaction semantics, or rollback. This session uses the retained analysis and does not claim to have rechecked the purchased book.

Selected local decisions are a synthetic equipment scenario, deterministic catalogue-based assessment, a SQLite snapshot with audit and command receipts, and one bounded command per CLI invocation. The snapshot is authoritative. The audit is application history, not an event-sourced projection or tamper-proof ledger. See [PLAN.md](PLAN.md) for alternatives and implementation sequence.

Python transaction semantics were checked against [Python 3.14 sqlite3](https://docs.python.org/3.14/library/sqlite3.html#transaction-control) and [SQLite transactions](https://www.sqlite.org/lang_transaction.html) on 2026-10-21. With `autocommit=True`, explicit SQL `BEGIN IMMEDIATE`, `COMMIT`, and `ROLLBACK` own transactions. Connection `commit()` and `rollback()` do not provide that boundary in this mode.

## Inputs and outputs

Submission accepts a JSON object with exactly `request_id`, `requester_id`, `equipment_code`, `quantity`, and `justification`. IDs are 1-64 ASCII letters, digits, underscore, or hyphen. Quantity is an integer from 1 through 5, never a boolean. Justification and decision reasons must be valid Unicode text without unpaired surrogates. Justification is nonblank text of at most 500 characters. Reject duplicate keys, extra fields, nonfinite numbers, malformed JSON, files larger than 16 KiB, and unsupported equipment before business writes.

The fixed catalogue owns prices in RM sen. `keyboard` costs 25,000 sen, `monitor` costs 90,000 sen, and `laptop` costs 350,000 sen. A request requires review if its derived total exceeds 100,000 sen or the equipment is `laptop`. Store derived total and policy version with the immutable normalized input. The request cannot provide price, state, risk, review, or fulfillment authority.

Submission also accepts a separate simulation profile, one of `success`, `transient_once`, `always_transient`, and `permanent_failure`. Persist it and include it in duplicate-submission comparison. It is a simulator setting, not business input. Request IDs cannot be reused for changed payloads or profiles.

Every mutation requires an ID under the same identifier rules, supplied as `--command-id`. Its canonical command payload includes operation, request, meaningful arguments, actor, and expected version where applicable. Inputs and actor syntax are validated first. Reusing an ID with the same normalized payload returns the saved historical response without another transition, event, or attempt. Different content conflicts. Exact receipt replay then precedes current-state and expiry checks. Query `show` for current state after historical replay.

JSON output exposes the result code, request snapshot, state/version, attempt count, derived total, deadline, next eligible attempt, review information, and fulfillment receipt where applicable. `audit` returns ordered events. Errors have stable codes and nonzero exit status. CLI help, SPEC, and README explicitly label reviewer identity as simulated attribution.

## Architecture and state

`domain.py` owns immutable types, enums, input validation, catalogue assessment, and the pure fulfillment simulator. `store.py` owns transition eligibility, SQLite schema, command transactions, persistence, and queries. `cli.py` owns argument parsing, bounded JSON reading, presentation, and process exit codes. Keep module boundaries small; do not create a generic orchestration engine.

The database contains requests, events, commands, and fulfillments. Requests hold input, fingerprint, policy/profile, state, version, attempts, UTC timestamps, review, and result. Events have a contiguous per-request sequence and include command ID, old/new state, actor, reason, and time. Commands have a unique ID, canonical hash, and serialized historical response. Fulfillments have a unique request ID and synthetic receipt.

Use a supported schema version, database identity, and schema fingerprint. Explicit `init` creates an empty schema and is repeatable. It can initialize an existing empty SQLite file left by a crash before schema commit; it rejects a nonempty foreign or partial schema without reset or migration. Other commands reject missing databases. Existing incompatible or corrupt databases are rejected without reset or migration. Enable foreign keys and a finite one-second lock timeout. Do not disable journaling or relax SQLite durability defaults.

One short `BEGIN IMMEDIATE` transaction owns receipt lookup, guards, snapshot update, event insert, simulated effect, and receipt insert. A committed state change has one event, with version and sequence increasing together. No-op advances and exact duplicate requests create no new state event. Every successful new mutation command, including these no-ops, records its result for replay. Roll back all writes on failure and always close connections. Read queries use a consistent SQLite snapshot across their component SELECTs. No external effect occurs inside or outside this transaction.

State defaults to a case-local ignored `state/` directory. An explicit `--db` path selects caller-owned local storage, including an isolated installation's temporary directory. This is a trusted local file path, not a filesystem security sandbox. No root or sibling state/configuration is required.

## Tools and authority

Only host commands may change state. The simulator returns a bounded outcome and cannot approve review, choose an arbitrary state, or write storage. Input text is data, never executable instructions.

Review requires `approve` or `reject`, a nonblank reason of at most 500 characters, an allowlisted reviewer (`ops-reviewer` or `finance-reviewer`), and the current positive expected version. Reject self-review when requester and reviewer IDs match. Review is allowed only while awaiting review before expiry. Approval does not itself fulfill the request.

Reviewer IDs are local caller-supplied labels. Anyone with CLI/database access can impersonate them or edit the database. The executable demonstrates transition and role guards, not authenticated human approval or security against the local operator.

## Execution and termination

| State | Command or observation | Next state |
| --- | --- | --- |
| absent | Valid submit | submitted |
| submitted | Advance, routine policy | ready |
| submitted | Advance, review policy | awaiting_review |
| awaiting_review | Explicit valid approve | ready |
| awaiting_review | Explicit valid reject | rejected |
| ready or due retry_wait | Simulated success | fulfilled |
| ready or due retry_wait | Transient failure, attempts below 3 | retry_wait |
| ready or due retry_wait | Third transient failure or permanent failure | failed |
| Any nonterminal state | New valid mutation at or after expiry | expired |
| Any nonterminal state before expiry | Explicit cancel with reason | cancelled |

1. `submit` validates input and persists `submitted` with a fixed 24-hour expiry and immutable assessment inputs. A new command ID with the same request payload and profile observes the existing request, or expires it if its deadline has elapsed; changed payload/profile conflicts. The original command ID always replays its original response.
2. `advance` performs one transition or one eligible fulfillment attempt and exits. It never sleeps or loops. Waiting for review, a future retry, and terminal states return no-op observations.
3. Fulfillment failure increments durable attempts. Retry eligibility is one second after failure 1, and two seconds after failure 2. Failure 3 is terminal. Permanent failure consumes one attempt and is immediately terminal.
4. `review` accepts one explicit decision under the version/role guards. `cancel` terminates a nonterminal request before expiry. Terminal states never reopen.
5. For a new mutation, input and actor syntax validation, receipt replay, request lookup, reviewer eligibility, and the review version guard precede expiry. At `now >= expires_at`, a structurally valid current action expires a nonterminal request before state eligibility; a stale review or invalid reviewer leaves it unchanged. Expiry wins over approval, cancellation, and fulfillment. `show` reports stored state and elapsed expiry without mutation. No background scheduler is claimed.
6. Internal clocks can be injected for tests. The normal CLI uses host UTC time and has no time override. Persist epoch milliseconds, not a process-local monotonic clock. Host clock rollback protection is outside scope.

CLI commands are `init`, `submit FILE`, `advance REQUEST`, `review REQUEST`, `cancel REQUEST`, `show REQUEST`, and `audit REQUEST`, with shared `--db PATH` on each subcommand. Mutation commands require `--command-id`. Review also requires decision, reviewer, reason, and expected version. Cancel requires a reason. Unknown IDs, stale versions, changed duplicate IDs, invalid actors, and incompatible states fail without business mutation. A structurally valid late action returns the expired state rather than fulfilling or approving it.

SQLite lock contention produces a retryable storage error, consumes no attempt, and can be retried with the same command ID. A crash before commit leaves no committed partial result. A crash after commit but before output can be recovered by exact command replay. One unique committed local fulfillment record is guaranteed by transaction/schema controls. Exactly-once external delivery, compensation for remote effects, hardware power-loss guarantees, and a distributed scheduler are outside scope.

## Acceptance criteria

All selected criteria use fixture/simulation evidence.

1. Routine request reaches fulfilled through separate commands with derived pricing, ordered events, and one fulfillment record.
2. Review request pauses across fresh processes; only explicit valid approval resumes it. Rejection, self-review, unknown reviewer, stale version, and premature fulfillment cannot bypass the checkpoint.
3. Cancellation, exact-deadline expiry, and terminal immutability prevent later fulfillment and survive reopening the store.
4. Exact command replay returns its historical response without new events or attempts; conflicting command IDs and changed duplicate submissions fail.
5. Retries persist across restart, respect due time, and stop after three attempts. Permanent failure stops after one attempt.
6. Competing SQLite connections/processes serialize review and fulfillment/cancel races, with one valid final state and at most one fulfillment record.
7. Injected write/commit failures and process termination before commit leave snapshot, events, command receipt, and simulated effect consistent. Lost response after commit is recoverable.
8. Invalid input and missing/incompatible/corrupt databases fail visibly without reset or partial business records. Lock contention is bounded.
9. Documented CLI walkthrough, local tests, isolated case-only installation, and installed wheel run without credentials or sibling resources. Independent review reconciles substantive findings before demo-ready.

## Dependencies and open decisions

Python 3.14 standard library owns runtime behavior; packaging may use a pinned build backend. No provider SDK or runtime credentials are required. All material v1 decisions are selected above. Real identity, external fulfillment, model assessment, distributed scheduling, database migrations, and tamper-evident audit require a separately scoped extension.
