# Autonomous Decision-Making Agent

Slug: 01-autonomous-decision-making
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

A bounded support-triage demo that chooses an autonomous status reply, guided clarification, or local human-handoff record. It uses synthetic tickets and a read-only synthetic status tool. The model proposes; deterministic policy controls authority and host templates produce the output. See [SPEC.md](SPEC.md) for the selected behavior and [PLAN.md](PLAN.md) for the build plan.

## Architecture and flow

Validate ticket → apply hard policy gates → observe synthetic status → request one proposal → arbitrate policy → prepare response/handoff → stop. State lives only within the run. Nothing is sent to a customer or human queue.

## Setup and run

From this directory, with [uv](https://docs.astral.sh/uv/) installed:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked autonomous-decision-making --example routine-outage
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked pytest -q
```

The case pins Python 3.14.8 and its own dependencies in `pyproject.toml`/`uv.lock`. No root installation, sibling case, credentials, or provider SDK is needed for replay. The temporary cache path accommodates this workspace's permissions; it can be changed for another machine. Fresh installation needs package access; execution uses only bundled synthetic data. The CLI defaults to `routine-outage` in `replay` mode.

| Replay example | Expected result | Exit |
| --- | --- | --- |
| `routine-outage` | Autonomous reply grounded in fresh outage evidence | 0 |
| `healthy-service`, `medium-confidence` | Guided clarification | 0 |
| `low-confidence` | Local handoff | 0 |
| `refund-request`, `human-request`, `high-impact`, `injection-attempt` | Handoff before lookup or proposal | 0 |
| `unavailable-human` | Queued local handoff before lookup or proposal | 0 |
| `restricted-proposal` | Restricted effect denied; local handoff | 0 |
| `missing-confidence` | Invalid proposal; failure handoff | 2 |

Fixtures live under `src/autonomous_decision_making/fixtures/` so they are included in the package. A few explicitly override the offline proposal to demonstrate policy and validation boundaries. Live mode uses the selected ticket/status but ignores replay proposal overrides.

The report includes the terminal route/status, host-derived priority, policy reason, validated proposal/evidence, prepared text or local handoff, fixed-label trace, and lookup/proposal attempt counts. It omits the raw ticket message, model prose, exception payloads, and credentials. Application output is stdout JSON; it writes no artifacts or persistent state. Exit 0 includes intentional policy handoffs; exit 2 identifies configuration, validation, tool, or provider failures; cancellation exits 130 without preparing an action.

For optional live cognition, install the isolated extra and set `OPENAI_API_KEY` in the invoking shell:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --extra live
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --extra live autonomous-decision-making --mode live --example routine-outage
```

`.env.example` lists the variable; no `.env` is loaded or discovered. Live preflight requires credentials and the supported SDK before any lookup/proposal, including hard-gated tickets. The only network capability is one OpenAI Responses request to the official endpoint, with model `gpt-6-luna`, strict JSON schema, no tools, `store=false`, 400 output tokens, retries disabled, and 20-second SDK/controller timeouts. Known reasoning metadata is discarded without reading its content; only one completed assistant message with one valid structured payload is accepted. Failure never triggers a silent replay fallback or second request.

## Decision rules

Trusted synthetic metadata supplies request kind, impact, human preference, and priority inputs. Message text is untrusted and cannot override gates. Human requests, high impact, refund/account/security requests, and unknown intent hand off before observation or cognition. Human unavailability queues a record and never grants autonomy.

Every remaining decision reads one allowlisted `api` or `dashboard` snapshot. Unknown status, mismatched service, invalid shape, future timestamps, or evidence older than 300 seconds fails safely before cognition. One validated proposal then passes through host policy: restricted effects are denied; contradictory route/action pairs fail; candidate handoff or confidence below 0.50 hands off; guided proposals, confidence from 0.50 to below 0.80, or operational service guide; only autonomous/status-reply proposals at or above 0.80 with degraded/outage evidence produce an autonomous reply. Confidence is an uncalibrated routing input. Host templates own all rendered text.

Code boundaries: `contracts.py` validates inputs/results, `fixtures.py` owns synthetic lookup, `backends.py` proposes, `policy.py` controls authority and rendering, `controller.py` bounds the run, and `cli.py` selects the example/mode and renders JSON.

## Verification

Executed locally on macOS arm64 with Python 3.14.8 and uv 0.12.23:

- `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv lock --offline` resolved the case-local lock; `uv sync --locked --offline` installed the replay/test environment successfully.
- `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline autonomous-decision-making --example routine-outage` exited 0 with an autonomous reply, matching synthetic evidence, one lookup, and one proposal.
- `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline pytest -q` passed **123 tests** covering fixture control flow and mocked-provider behavior. No API calls were made.
- Parent integration independently exercised all 11 replay examples with credentials and `PYTHONPATH` unset; every expected route/exit matched, hard-gated examples made zero lookup/proposal attempts, and the unavailable-human record was queued.
- Parent isolation copied only this case to `/private/tmp/agent-atlas-01-isolation-w7gu10yr/01-autonomous-decision-making`, excluded virtual environments/caches/private configuration/artifacts, and ran `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline` and `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline pytest -q`: **123 passed in 0.26s**. The import resolved inside the copy; normal/refund/missing-confidence CLI paths had expected routes/exits. This used a populated shared dependency cache, with no sibling installation or provider credentials.
- Independent review reproduced **123 passing tests**. Its missing-SDK preflight finding was corrected and regression-tested; review reported no remaining actionable findings.

The selected fixture and mocked-provider acceptance criteria passed, including independent review and case-only installation. This case is `demo-ready` for the documented offline scenario. Live-model compatibility, model quality, provider connectivity, hosted CI, and deployment remain unverified. Mode-specific verification records follow.

Verified on: 2026-10-18
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline pytest -q tests/test_controller.py tests/test_cli.py
Verification mode: fixture
Verification result: passed
Verified scope: 96 tests covering routing thresholds and precedence, pre-tool gates, status freshness/integrity, strict input/proposal validation, tool failures, controller timeout/cancellation, output sanitization, run isolation, CLI/configuration behavior, and fresh-interpreter replay with SDK import/network denied.

Verified on: 2026-10-18
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline pytest -q tests/test_live_backend.py
Verification mode: mocked-provider
Verification result: passed
Verified scope: 27 tests covering one fake SDK request, strict request schema/options, no tools/retries, refusal/incomplete/invalid output, discarded reasoning metadata, transport failures/timeouts, sanitized handoff, and configuration preflight without a request. These checks do not exercise the real SDK transport or model.

## Limitations and references

The source is the retained [case brief](../../agent-library-analysis/agents/01-autonomous-decision-making.md), Chapter 5 of Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026. Its pseudocode and autonomy claims are not validation of this implementation. No real systems, payments, notifications, durable memory, adaptive learning, or production qualification are included. The replay backend is a deterministic baseline, and the demo trusts upstream metadata; it does not establish intent classification accuracy for arbitrary customer messages.

Live API references: [official structured output guide](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) and [Python SDK reference](https://developers.openai.com/api/reference/python). Package versions are pinned; availability and structured-output compatibility of the selected model still require a separately authorized live check.
