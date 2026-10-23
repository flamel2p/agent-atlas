# Financial Advisory Agent

Slug: 26-financial-advisory
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

This deterministic fictional portfolio demo calculates descriptive metrics, checks a host policy, and permits one equal-weight simulated revision. Completion returns a simulated allocation report. Incomplete data or a persistent violation returns `review_required` with no released allocation. Independent review passed.

There are no real prices, real client profiles, recommendations for actual investments, orders, brokers, accounts, models, network calls, or compliance certification. The historical book pattern informs the learning objective. [SPEC.md](SPEC.md) owns the selected behavior and exact schemas; [PLAN.md](PLAN.md) records implementation decisions.

## Run locally

From this case directory with uv and Python 3.14 available:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --offline --locked
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --locked financial-advisory --fixture normal
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --locked python -m financial_advisory --fixture persistent
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --locked python -m financial_advisory --help
```

Offline setup requires Python 3.14 and the pinned build dependency `hatchling==1.32.4` already cached. If they are unavailable, remove `--offline` for setup. The runtime has no dependencies outside the standard library and requires no credentials or environment configuration. The lockfile records the dependency-free runtime package. All fixtures are original synthetic data packaged in the wheel.

The normal fixture starts with 90% `SYN_ALPHA` and 10% `SYN_BETA`. The host finds concentration and volatility violations, then fully rechecks a 50/50 revision. The revised period returns are +0.05 and -0.05, sample volatility is approximately 0.0707106781, drawdown is 0.05, and terminal wealth is 0.9975 relative to initial wealth 1. These are fractional daily observations without annualization, costs, or execution.

| Fixture | Expected terminal result | Revision count |
| --- | --- | --- |
| `normal` | `completed_simulation` | 1 |
| `persistent` | `review_required`, volatility and drawdown remain excessive | 1 |
| `missing` | `review_required`, incomplete asset coverage | 0 |
| `stale` | `review_required`, stale histories | 0 |

To supply bounded structured input, use `--stdin` and the [normal fixture](src/financial_advisory/fixtures/normal.json) as the schema example:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --locked financial-advisory --stdin < src/financial_advisory/fixtures/normal.json
```

The process waits for stdin EOF or cancellation, and reads at most 65537 bytes to detect the 65536-byte limit. It accepts 2–8 declared synthetic assets and 0–64 daily observations per series. Fewer than three observations requires review. Freshness is measured against the supplied `as_of`, maximum three calendar days. Decimal weights must sum exactly to one, including every declared asset. A zero weight does not waive data coverage. Unknown fields, duplicate keys, unsupported dates, bool/nonfinite prices or weights, excess depth, large numeric tokens, and excessive price ratios are rejected. See the full limits and host table in [SPEC.md](SPEC.md).

A valid simulation, including review, exits 0. Invalid input exits 2 with bounded JSON. Input/output failure exits 74. Cancellation exits 130. Help and reports use controlled writes and explicit flushes; broken stdout cannot become a successful run or a deferred shutdown exit 120. A disconnected consumer or interruption during output may receive partial JSON, so the exit status remains authoritative. The host creates at most one revision and two complete metric evaluations, with no retries or persisted state.

## Source reading guide

- [Module entry point](src/financial_advisory/__main__.py) and [CLI](src/financial_advisory/cli.py): inspect named-fixture authority, bounded stdin, argument errors, cancellation, and controlled help/report writes.
- [Validation](src/financial_advisory/validation.py): inspect duplicate-key/depth/size controls, decimal allocation sums, required-asset coverage, daily timestamp order, positive bounded prices, and arithmetic ratio limits.
- [Domain](src/financial_advisory/domain.py): inspect immutable run inputs, data readiness, units, sample volatility, compounded drawdown, host policy, and the one-revision state machine. Constant-weight rebalancing means each daily period uses the same weights.
- [Tests](tests/test_advisory.py): compare the metrics with independent arithmetic expectations, then inspect invalid input, data review, persistence limits, and real subprocess I/O checks.
- [Qualification script](scripts/qualify.py): inspect case-only copying, offline wheel build, fresh isolated installation, installed import origin, and actual CLI fixture assertions.

## Verification

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --locked python -m unittest discover -s tests -v
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --locked python scripts/qualify.py
```

Verified on: 2026-10-23
Verification command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --locked python scripts/qualify.py`
Verification mode: fixture
Verification result: passed
Verified scope: Python 3.14.8 on macOS arm64; 31 tests passed in each of source, case-only temporary copy, and installed wheel environments. All four fixtures passed through source and copy module commands, installed module commands from an unrelated directory, and the installed console command. The installed import originated in the fresh environment. Test coverage includes independent expected metrics, one-revision behavior, missing/stale data, strict schema/arithmetic limits, cancellation and input I/O unit checks, and real buffered/unbuffered help/report closed-stdout subprocesses returning 74.

The direct unittest command also passed 31 tests. Qualification creates and deletes its temporary copy, wheel, and installation outside the repository. It does not require a sibling case or root runtime. No live-model, mocked-provider, market-data provider, professional service, deployment, or production validation was run. The parent owns independent review and final catalogue readiness.

## Limitations and references

The host thresholds are educational choices, not validated suitability criteria. Floating-point calculations describe only the supplied daily synthetic window. Input can select a fictional risk band but cannot replace its host policy. Equal weighting is a deterministic example revision, with no claim that it improves actual investments. No synthetic cash or missing-price fallback exists.

See the [source brief](../../agent-library-analysis/agents/26-financial-advisory.md) for source gaps, historical dependencies, and unsupported efficacy claims. This original implementation does not reproduce or validate those claims.
