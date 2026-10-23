# Legal Intelligence Agent

Slug: 27-legal-intelligence
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

This independent learning demo retrieves and ranks original fictional authorities, drafts a tagged memorandum, and verifies every citation before a simulated reviewer handoff. It uses fictional Alder and Brume jurisdictions and lantern-lease rules. It provides no real legal advice or human approval.

[SPEC.md](SPEC.md) owns exact schemas, host policy, limits, and outcomes. [PLAN.md](PLAN.md) records decisions and outstanding review. The [source brief](../../agent-library-analysis/agents/27-legal-intelligence.md) distinguishes book claims and gaps from this original implementation.

## Setup and run

Run from this case directory with Python 3.14 and uv. Runtime uses only the standard library. The build backend is pinned to hatchling 1.32.4. No credentials or environment configuration are needed. Offline commands require cached Python and build packages.

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline legal-intelligence
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline legal-intelligence --help
```

For your own structured JSON file, append `--input /absolute/regular/matter.json`. Explicit paths reject symlinks, including parent links, and non-regular files. On macOS use canonical `/private/tmp/...` instead of the `/tmp` symlink for explicit input.

Default output covers notice/export, ranks ALD-101 ahead of ALD-102, cites ALD-101 and ALD-201, records citation checks and snapshot metadata, and returns `simulated_reviewer_handoff`. It sets `simulated_release` true and `human_approval` to `not_granted`. No message is sent. Exit codes are 0 for simulated handoff, 1 for blocked evidence or closed stdout, 2 for invalid input, and 130 for cancellation.

Minimal input requests host drafting:

```json
{"matter":{"matter_id":"lantern-01","jurisdiction":"ALDER","issues":["notice","export"]}}
```

Optional `draft` replaces host drafting with structured proposals. This fabricated citation returns `blocked_review` and exit 1:

```json
{"matter":{"matter_id":"lantern-02","jurisdiction":"ALDER","issues":["notice"]},"draft":[{"issue":"notice","rule":"notice_before_pause","citations":[{"authority_id":"FABRICATED","version":"v1"}]}]}
```

Claims accept issue/rule tags and versioned citations only. The host owns sentence text. Input cannot supply status, approval, tools, or arbitrary prose. Verification checks existence, version, jurisdiction, explicit current status, exact source-to-claim support, and complete issue coverage. Every citation must pass. Empty drafts/citations fail. ALD-099 and ALD-103 demonstrate superseded and unknown status. Retention has no source and remains uncovered.

## Architecture and source reading guide

1. [cli.py](src/legal_intelligence/cli.py) owns arguments, packaged fixtures, cancellation, reports, and explicit stdout flushing. [__main__.py](src/legal_intelligence/__main__.py) provides module execution.
2. [boundary.py](src/legal_intelligence/boundary.py) bounds JSON and traverses files without following links. Inspect duplicate-key, scalar, size, depth, and regular-file gates here.
3. [core.py](src/legal_intelligence/core.py) defines frozen per-run types, exact issue/rule policy, fixture validation, authority ranking, deterministic drafting, citation findings, coverage, and terminal transitions. Host policy controls simulated release; drafts remain proposals.
4. [corpus.json](src/legal_intelligence/fixtures/corpus.json) contains seven original fictional sources. [matter.json](src/legal_intelligence/fixtures/matter.json) is the original normal fixture. Status refers only to snapshot `alder-brume-2026-10-01`, recorded at `2026-10-01T00:00:00Z`.
5. [test_demo.py](tests/test_demo.py) checks normal/failure outcomes and real CLI processes. [qualify_isolation.py](qualify_isolation.py) checks a case-only copy and installed wheel, deleting copied sources before installed execution.

The finite flow is validate, retrieve, draft, verify, then simulated handoff or blocked review. Limits are 32,768 input bytes, eight container levels, 512 characters per JSON string, three requested issues, 16 corpus sources, six claims, and four citations per claim. ASCII identifiers are at most 48 characters. There are no retries, repairs, models, persistent state, or background work.

## Verification

Run from this case directory:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python qualify_isolation.py
```

Verified on: 2026-10-23
Verification command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v`
Verification mode: fixture
Verification result: passed
Verified scope: 24 tests on CPython 3.14.8. Ranked memo/reviewer ownership; fabricated, superseded, unknown-status, stale-version, wrong-jurisdiction, inapplicable, and empty citations; empty drafts and uncovered issues; strict JSON/schema validation; hostile corpus metadata; regular-file boundary; actual module/help/explicit-input/error exits; buffered/unbuffered closed stdout for help, result, and error; cancellation handler via injected KeyboardInterrupt.

Verified on: 2026-10-23
Verification command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python qualify_isolation.py`
Verification mode: fixture
Verification result: passed
Verified scope: case-only copy passed 24 tests and console CLI. Wheel built with cached hatchling 1.32.4 and installed outside checkout. Removed copied source, checked package origin, passed 24 tests and module/console/help execution with isolated Python.

Also ran the documented sync, normal console, and help commands successfully. The cancellation test injects KeyboardInterrupt and does not establish signal-timing qualification. Independent review passed. The parent owns root structure verification and catalogue integration. Status is `demo-ready` for the selected fixture scope.

## Limits and deferred work

Exact tags demonstrate evidence gates, not factual analogy, semantic retrieval, natural-language extraction, legal reasoning, currency, or real corpus authenticity. Sentences are fictional conclusions without real applicability. The package-owned corpus has no ingestion adapter or external status refresh. Version and time are explicit but static. Sample-contract/clause-review branches are deferred under parent scope refinement to keep one coherent memo flow. Live-model, real-service, deployment, production, and professional qualification are unverified and outside this demo's authority.
