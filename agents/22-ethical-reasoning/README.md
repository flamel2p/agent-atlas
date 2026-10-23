# Ethical Reasoning

Slug: 22-ethical-reasoning
Status: demo-ready
Runtime: Python 3.14, standard-library runtime, strict JSON CLI

## Purpose and contract

Evaluate synthetic report proposals against a versioned host policy, then simulate publication or return a review case. One restricted-field redaction is permitted, followed by full policy revalidation. The actual dispatcher enforces policy, not an earlier permission label. Read the [behavior contract](SPEC.md) for exact schemas, rules, limits, and acceptance criteria.

The disparity threshold is an arbitrary demonstration policy. This demo makes no hiring, legal-compliance, real-world fairness, model-quality, network, or persistent-audit claim.

## Architecture and flow

1. The CLI bounds and strictly decodes one JSON request.
2. Immutable typed records carry a symbolic action and aggregate group counts.
3. The dispatcher evaluates every host rule and records the attempt before any simulated effect.
4. The controller redacts restricted field names at most once, then calls the same enforcing dispatcher.
5. The terminal output contains `completed` or `review_required`, events, symbolic effects, and any review findings. Invalid requests produce `invalid_input` before dispatch.

All state is run-scoped. Nothing is sent to a human reviewer. The owner label identifies the next responsibility only.

## Source reading guide

- [cli.py](src/ethical_reasoning/cli.py) owns bounded JSON, duplicate-key rejection, safe errors, and exit status.
- [domain.py](src/ethical_reasoning/domain.py) owns request records and validated count/identifier invariants.
- [policy.py](src/ethical_reasoning/policy.py) owns the immutable host registry, exact disparity rule, and structured findings.
- [engine.py](src/ethical_reasoning/engine.py) owns dispatcher-level authority, audit-before-effect, one repair, run state, and terminal review.
- [test_agent.py](tests/test_agent.py) checks externally observable effects, direct dispatch bypass attempts, policy boundaries, and strict decoding.
- [verify_distribution.py](scripts/verify_distribution.py) checks a case-only copy and an installed wheel from outside the repository.

## Setup and run

Run from this directory with uv and Python 3.14 available:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --offline --locked
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline ethical-reasoning fixtures/allowed.json
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline ethical-reasoning fixtures/redact.json
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline ethical-reasoning fixtures/forbidden.json
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline ethical-reasoning fixtures/disparity.json
```

The first two commands that run fixtures return `completed`, one effect, and exit 0. The last two return `review_required`, zero effects, and exit 3. For stdin, use `ethical-reasoning -`. The equivalent module entry is `python -m ethical_reasoning`.

No runtime packages, environment variables, providers, credentials, network services, or sibling cases are required. Offline setup needs Python 3.14 and the pinned build dependency already cached. Omit `--offline` for an initial permitted dependency install when that cache is absent.

## Verification

Verified on: 2026-10-23
Verification command: `.venv/bin/python -m unittest discover -s tests`
Verification mode: fixture
Verification result: passed
Verified scope: 26 tests cover normal publication, exactly one simulated effect, one redaction with full revalidation, failed disclosure mitigation, disparity and insufficient-evidence review, direct-dispatch policy enforcement, replay/attempt bounds, context binding, immutable policy, audit failure before effect, strict input, and actual module CLI outcomes.

Environment was CPython 3.14.8 on macOS arm64. `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --offline --locked` completed. Actual console runs of `fixtures/allowed.json` and `fixtures/forbidden.json` returned exit 0 with one effect and exit 3 with zero effects, respectively.

Verified on: 2026-10-23
Verification command: `.venv/bin/python scripts/verify_distribution.py`
Verification mode: fixture
Verification result: passed
Verified scope: 26 tests passed in a case-only temporary copy and 26 tests passed against an installed wheel from outside the repository. Console fixtures checked allowed, forbidden, redacted, and disparity outcomes. The installed import resolved inside the fresh environment. Temporary build and installation artifacts were removed.

Independent review identified a stdout flush defect. Parent regression checks reproduced exit 120 for buffered output and exit 130 for immediate broken pipes before the fix. Both result and help output now flush inside the controlled boundary, silence failed shutdown flushes, and return I/O exit 2. The 26-test suite and both isolated distributions passed again after the fix. Independent fix review passed. Status is `demo-ready` for this fixture scope; the parent owns catalogue integration. No mocked-provider, live-model, deployment, or production checks ran. These are local fixture and packaging checks only.

## Limitations and references

Only symbolic field names and unverified synthetic aggregate counts are accepted. Input does not establish that counts are authentic or complete. The selection-rate ratio does not establish causal fairness, a statistical guarantee, or legal compliance. Redaction does not alter counts, policy, recipient, or action kind. Review is terminal for this run.

There is one sequential action per process, at most two dispatcher attempts, and one repair. The in-memory audit has no durability or tamper evidence. Replays in new processes are independent and can create another simulated receipt. The trusted Python host is not a sandbox against code that edits its internals.

Inspired by Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 12, printed pp.330-346. See the retained [source brief](../../agent-library-analysis/agents/22-ethical-reasoning.md) and [foundations](../../agent-library-analysis/foundations.md). This implementation is independent and uses no purchased source text or source code. The repository MIT license remains in force.
