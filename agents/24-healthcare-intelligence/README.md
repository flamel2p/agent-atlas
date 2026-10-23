# Healthcare Intelligence Agent

Slug: 24-healthcare-intelligence
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

An original fictional evidence exercise demonstrates normalization, exact Bayesian updates, source conflicts, and simulated review. The three pattern labels and two signal names have no clinical meaning. No real records, diagnosis, treatment, EHR, models, network, or external alerts are supported.

[SPEC.md](SPEC.md) defines the complete schema, limits, evidence policy, and terminal outcomes. [PLAN.md](PLAN.md) records implementation reconciliation. Independent review and fix verification passed; readiness is limited to the fixture scope.

## Run the fixture

Run these commands from this case directory with `uv` and Python 3.14 available. The runtime has no third-party dependencies. Offline packaging requires cached `hatchling==1.32.4` and its build dependencies. Use `uv sync --locked` without `--offline` to populate a fresh development environment when network access is authorized.

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --offline --locked
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline healthcare-intelligence
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline healthcare-intelligence --input src/healthcare_intelligence/fixtures/normal.json
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline python -m unittest discover -s tests -v
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline python scripts/qualify.py
```

The CLI emits one JSON report to stdout. The default fixture returns `review_required`, with exact posterior values `20/23`, `3/46`, and `3/46`. The report retains observation times and both source/version/time records. Its review has `real_approval: false` and `effect: none`. Use `--help` for the single file-input option. No runtime report-file write is available.

## Behavior and limits

Structured observations use fictional `ticks` or `milli_ticks`. Host code normalizes them, derives toy `high` or `low` bands, and matches supplied likelihoods. It requires both signals, observations at most 24 hours old, and matched knowledge at most 30 days old. Conflicting matched records remain unresolved. Identical records add provenance without multiplying the same signal twice.

Only complete, fresh, compatible evidence with positive total mass produces a posterior. `pending`, `acknowledged`, and `rejected` simulated review inputs then yield `review_required`, `simulated_reviewed`, and `review_rejected`. Any evidence issue yields `unresolved` with a null posterior, even if review is acknowledged. Source labels and simulated decisions grant no real authority. Provenance identifies supplied records; it does not authenticate them.

The byte bound is 65,536, nesting depth is 8, and the node bound is 2,048. There are at most 2 unique signals and 16 knowledge records. Strict parsing rejects unknown or duplicate keys, nonfinite numbers, booleans, null, invalid units or labels, future or malformed timestamps, and invalid probability mass. Exact rational arithmetic prevents numerical underflow from turning positive mass into zero. Floating-point probabilities are display approximations. The likelihoods assume conditional independence by construction and have no empirical calibration.

Valid domain outcomes exit 0, including unresolved review. Invalid input or limits exit 2. Local I/O failures exit 3, interruption exits 130, and a broken output pipe exits 1. Diagnostic reports do not echo submitted values, paths, or underlying exception messages. Invalid CLI arguments use standard argparse usage errors. The file input must be a regular nonsymlink file. The CLI rejects FIFOs without waiting for a writer.

## Source reading guide

- [cli.py](src/healthcare_intelligence/cli.py) owns the real entry point, bounded regular-file read, interruption, JSON output, and exit behavior. [__main__.py](src/healthcare_intelligence/__main__.py) provides the equivalent module command.
- [boundary.py](src/healthcare_intelligence/boundary.py) owns strict JSON validation, bounds, exact decimal conversion, units, taxonomy, identities, and timestamps. Review this before the trusted kernel.
- [domain.py](src/healthcare_intelligence/domain.py) defines immutable run state, exact beliefs, supplied provenance, freshness/conflict gates, and simulated review. Inspect `evaluate` for the host-owned state transition and no-partial-posterior rule.
- [normal.json](src/healthcare_intelligence/fixtures/normal.json) is the original packaged fixture. Its expected unnormalized masses are `0.2`, `0.015`, and `0.015`; their sum is `0.23`.
- [test_demo.py](tests/test_demo.py) checks independent expected arithmetic, provenance, normalization equivalence, all evidence/review gates, parser bounds, file authority, and actual CLI behavior.
- [qualify.py](scripts/qualify.py) copies only this case to a temporary directory, runs the tests and real CLI, builds and installs its wheel, then repeats those checks outside the checkout with an isolated interpreter. Temporary artifacts are removed after execution.

The [source brief](../../agent-library-analysis/agents/24-healthcare-intelligence.md) distinguishes the book's architectural sketches and efficacy claims from this selected original fixture contract. No purchased source text or official sample code is included.

## Verification

Verified on: 2026-10-23
Verification command: `.venv/bin/python -m unittest discover -s tests`
Verification mode: fixture
Verification result: passed
Verified scope: 43 local tests on CPython 3.14.8; exact posterior and provenance, unit/order equivalence, duplicate-evidence policy, simulated review, missing/stale/conflicting/zero-mass gates, invalid input and bounds, CLI input/error/cancellation/help/broken-pipe behavior.

Additional commands actually run from the repository root on 2026-10-23:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv lock --offline --project agents/24-healthcare-intelligence
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --project agents/24-healthcare-intelligence healthcare-intelligence
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --project agents/24-healthcare-intelligence python agents/24-healthcare-intelligence/scripts/qualify.py
```

The lock command and real default CLI passed. The qualification command passed 43 tests in the case-only copy and 43 tests against the installed wheel, plus actual console CLI checks in both environments. The wheel check verified that imports came from its installed site-packages, and checked packaged fixture access and `--help`. These are local fixture and packaging results. Cancellation injection is a local mocked interrupt check, with no provider involvement. Live-model, real clinical service, calibration, CI, deployment, and production evidence remain unverified. Independent review and fix verification passed. Status is `demo-ready` for this fixture scope.

Independent review identified help output bypassing the controlled writer. A process regression reproduced buffered exit 120 and unbuffered exit 0 instead of the specified exit 1. Help and result output now share a protected flush and failure handler. Parent reran 43 tests locally and in each isolated distribution with `.venv/bin/python scripts/qualify.py`. Independent fix review passed.
