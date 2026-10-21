# Agentic Workflow System

Slug: 09-agentic-workflow
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

This case runs a synthetic equipment request through assessment, a durable review checkpoint, and simulated fulfillment. Each CLI invocation performs one explicit command and exits. SQLite retains the request snapshot, ordered audit events, command receipts, attempts, and one possible fulfillment record across restarts. [SPEC.md](SPEC.md) owns the behavior contract and [PLAN.md](PLAN.md) records the selected design.

The host catalogue prices `keyboard` at RM250, `monitor` at RM900, and `laptop` at RM3,500. Total above RM1,000 or any laptop requires review. The request JSON cannot supply price, risk, state, or approval. Reviewer IDs are caller-supplied **synthetic labels, not authenticated identity**; anyone with CLI or database access can impersonate them. The simulator performs no real purchase, payment, inventory change, or message delivery.

## Source reading guide

Read [cli.py](src/agentic_workflow/cli.py) first for the bounded JSON file and command boundary, argument contract, and error output. [domain.py](src/agentic_workflow/domain.py) defines validated immutable input, state/profile enums, host assessment, and the one-attempt simulator. [store.py](src/agentic_workflow/store.py) owns schema identity, short SQLite transactions, deadline and review guards, replay receipts, ordered events, and the unique simulated fulfillment. [test_workflow.py](tests/test_workflow.py) exercises observable transitions, restart, concurrency, lock, and rollback behavior. [check_installed.py](scripts/check_installed.py) drives an installed console command from an unrelated directory. The [synthetic fixtures](fixtures/) supply harmless CLI inputs.

The request snapshot is authoritative. An event records a committed state change but is not a tamper-proof ledger or event-sourced projection. A saved command result is historical: replaying the same command ID and normalized content returns the original response even after later changes. Use `show` to inspect current state. State and events commit with the simulated fulfillment and receipt in one local transaction. This does not guarantee exactly-once external delivery.

## Setup and run

From this directory, with Python 3.14 and uv:

```sh
uv sync --locked
uv run --locked agentic-workflow --help
```

The default database is `./state/workflow.sqlite`; `state/` is ignored by Git. Each subcommand accepts `--db PATH` for an isolated local file. Only `init` creates a database. The path is trusted caller-owned storage, not a filesystem sandbox. Commands return JSON, while `--help` prints usage. Invalid commands return a stable error code and nonzero status. No credentials or services are required.

Routine path, using a fresh path of your choice:

```sh
uv run --locked agentic-workflow init --db state/routine.sqlite
uv run --locked agentic-workflow submit fixtures/keyboard.json --db state/routine.sqlite --command-id routine-submit
uv run --locked agentic-workflow advance keyboard-demo --db state/routine.sqlite --command-id routine-assess
uv run --locked agentic-workflow advance keyboard-demo --db state/routine.sqlite --command-id routine-fulfill
uv run --locked agentic-workflow audit keyboard-demo --db state/routine.sqlite
```

The expected state sequence is `submitted → ready → fulfilled`, with versions and event sequence `1, 2, 3`, derived total `25000` sen, one attempt, and one synthetic fulfillment receipt. Repeating `routine-fulfill` with the same command returns its saved response without another attempt.

Review path, using another fresh database:

```sh
uv run --locked agentic-workflow init --db state/review.sqlite
uv run --locked agentic-workflow submit fixtures/laptop.json --db state/review.sqlite --command-id review-submit
uv run --locked agentic-workflow advance laptop-demo --db state/review.sqlite --command-id review-assess
uv run --locked agentic-workflow show laptop-demo --db state/review.sqlite
uv run --locked agentic-workflow review laptop-demo --db state/review.sqlite --command-id review-approve --decision approve --reviewer ops-reviewer --reason 'Synthetic approval' --expected-version 2
uv run --locked agentic-workflow advance laptop-demo --db state/review.sqlite --command-id review-fulfill
```

The third command leaves `awaiting_review` at version 2 across process exit. `review` moves it to `ready`; only the following `advance` performs simulated fulfillment. The allowlisted reviewer label and version are policy checks, not authentication.

Retry path, again starting with a fresh database:

```sh
uv run --locked agentic-workflow init --db state/retry.sqlite
uv run --locked agentic-workflow submit fixtures/keyboard.json --profile transient_once --db state/retry.sqlite --command-id retry-submit
uv run --locked agentic-workflow advance keyboard-demo --db state/retry.sqlite --command-id retry-assess
uv run --locked agentic-workflow advance keyboard-demo --db state/retry.sqlite --command-id retry-attempt-1
uv run --locked agentic-workflow show keyboard-demo --db state/retry.sqlite
```

The first attempt enters `retry_wait` and stores `next_attempt_at` one second later. Run a new `advance` with a new command ID after that time to reach `fulfilled` on attempt 2. An immediate advance observes `retry_not_due` and records a replayable no-op receipt. `always_transient` stops at attempt 3; `permanent_failure` stops at attempt 1. There is no background scheduler or sleep loop.

## Verification

Verified on: 2026-10-21
Verification command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v`
Verification mode: fixture
Verification result: passed
Verified scope: 16 tests covering normal and review paths, retries and deadlines, historical replay including no-ops, cancellation, invalid Unicode and malformed JSON, schema rejection, special database paths, subprocess restart and races, write/pre-commit rollback, real SQLite COMMIT contention, and process termination around commit.

The local environment was macOS ARM64, Python 3.14.8, SQLite 3.53.1, and uv 0.12.23. The locked offline installation passed. The same 16 tests passed in `/tmp/agent09-case-only`, containing only this case with its own environment, with `PYTHONPATH` and `OPENAI_API_KEY` unset. No sibling case was needed.

The wheel built with `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv build --offline --wheel --out-dir artifacts/dist` and installed into `/tmp/agent09-wheel-verify`. Running `/Users/flame/.local/bin/python3.14 scripts/check_installed.py /tmp/agent09-wheel-verify/bin/agentic-workflow` passed 46 separate CLI invocations. Six scenarios reached the expected outcomes: routine fulfillment, approval then fulfillment, rejection, cancellation, transient recovery, and permanent failure. The same check verified replay, invalid review, malformed text, database filenames containing `?` and `#`, and a durable file named `:memory:`. These are simulation checks, not model evaluations.

The documented routine, review, and retry walkthroughs were also executed through separate CLI processes. The root structure check and `git diff --check` passed after catalogue integration. Independent review identified Unicode validation and database-path creation issues; both were fixed with regressions. A separate reviewer confirmed those fixes and real COMMIT-failure recovery, with no remaining actionable findings. The explanation review found no misleading source-reading or authority explanations.

To repeat the installed-command check with a fresh environment:

```sh
uv build --wheel --out-dir artifacts/dist
uv venv --python 3.14 artifacts/wheel-env
uv pip install --python artifacts/wheel-env/bin/python artifacts/dist/agentic_workflow_demo-0.1.0-py3-none-any.whl
uv run --locked python scripts/check_installed.py artifacts/wheel-env/bin/agentic-workflow
```

No live model, authenticated reviewer, real delivery, hosted CI, deployment, or production qualification was tested. This case deliberately implements deterministic simulation only.

## Limitations and reference

The [Agent 09 source brief](../../agent-library-analysis/agents/09-agentic-workflow.md) informs the branching and review pattern. This implementation is an original deterministic simulation based on retained analysis; the purchased book was not rechecked for this case. SQLite transaction controls guarantee at most one committed local fulfillment record for a request under the documented process and storage assumptions. Host clock rollback, hardware power loss, local database tampering, remote effect compensation, and identity verification are outside this demo.
