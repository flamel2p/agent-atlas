# Financial Advisory Agent specification

Slug: 26-financial-advisory
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and evidence

This original fictional simulation demonstrates deterministic portfolio metrics, host-owned policy, one simulated revision, and review. It provides no real prices, financial advice, trade, broker, account, network, model, or regulatory compliance claim. The [source brief](../../agent-library-analysis/agents/26-financial-advisory.md), [inventory](../../agent-library-analysis/agent-inventory.md), and [foundations](../../agent-library-analysis/foundations.md) inform the learning objective. Their historical examples and efficacy claims are not runtime evidence. [PLAN.md](PLAN.md) records selected implementation decisions.

## Input contract

The CLI accepts one packaged fixture through `--fixture normal|stale|persistent|missing`, default `normal`, or one UTF-8 JSON object through `--stdin`. No caller-controlled file path is opened. All object keys below are required unless explicitly optional. Unknown fields and duplicate JSON keys are rejected at every level.

- Root: `fictional: true`, `as_of: YYYY-MM-DD`, `profile`, `required_assets`, `series`, `proposal`.
- `profile`: `id` matching `invented_[a-z]{1,20}`, `risk_band: cautious|moderate|exploratory`.
- `required_assets`: 2–8 unique strings matching `SYN_[A-Z]{1,12}`. These declare the complete synthetic universe, not real instruments.
- `series`: 0–8 objects with `asset`, `unit: synthetic_price_units`, `observations`. Assets must be unique members of `required_assets`. Omitted series or fewer than three observations produce review, never zero risk.
- `observations`: 0–64 objects with `date: YYYY-MM-DD` and `price`. Dates must strictly increase by exactly one calendar day, with no date after `as_of`. Prices are finite numbers from 0.000001 through 1000000 inclusive. Adjacent price ratios must lie in [0.5, 2], bounding arithmetic growth. The series must share an identical date grid for portfolio calculations; a mismatch produces review.
- `proposal`: `weights` object with exactly one numeric weight for every required asset. Each weight is in [0, 1], including zero. Decimal weights must sum exactly to one. A zero-weight asset still requires complete fresh observations.

All numbers reject booleans, NaN, Infinity, tokens longer than 32 characters, and decimal exponents outside [-12, 6]. Decimal parsing verifies the sum without binary floating-point tolerance. Input is at most 65536 bytes and 12 container levels. Strings and arrays are bounded by those transport limits and their field-specific constraints. Trailing JSON, wrong types, malformed UTF-8, excessive nesting, and unsupported dates are invalid input. In-memory request values are immutable and last for one run. Runtime calculations use finite binary64 floats after boundary validation.

## Metrics and host policy

Observations are daily calendar observations, not market sessions. Freshness is the calendar-day difference between `as_of` and the final observation, inclusive maximum 3. The host first checks coverage, minimum history, identical grids, and freshness. Any data finding terminates with `review_required`, empty evaluations, no revision, and no released allocation.

For each asset, per-period return is `price[t] / price[t-1] - 1`. For a proposal, portfolio return is the weighted sum of asset returns in each period. This represents constant weights rebalanced every period, with no costs or execution. Wealth starts at 1 and compounds by `1 + portfolio_return`. Maximum drawdown is the maximum fractional fall from the running wealth peak, including initial wealth. Volatility is the sample standard deviation of portfolio period returns, using denominator `n - 1`. Neither returns nor volatility are annualized. Concentration is the largest asset weight. Metrics include asset returns, portfolio returns, terminal wealth, volatility, drawdown, concentration, period count, date range, freshness ages, and units. These are descriptive observations, not calibrated risk scores or forecasts.

Each metric must be less than or equal to the selected host threshold:

| Fictional band | Concentration | Per-period volatility | Maximum drawdown |
| --- | --- | --- | --- |
| cautious | 0.5 | 0.03 | 0.10 |
| moderate | 0.6 | 0.08 | 0.25 |
| exploratory | 0.8 | 0.20 | 0.50 |

The immutable host table owns these educational thresholds. Input can select a band but cannot override thresholds. No synthetic cash is added. Missing data cannot trigger a cash or zero-return fallback.

## Flow and output

1. Validate the bounded JSON into `PriceSeries`, `SyntheticProfile`, and `AllocationProposal` in an immutable request.
2. Check data readiness. Return review immediately if incomplete or stale.
3. Compute `RiskReport` and `PolicyFinding` values for the initial allocation.
4. If all host checks pass, return `completed_simulation` with that allocation.
5. Otherwise the host creates exactly one equal-weight allocation across the declared universe. Recompute every metric and recheck every policy. Return `completed_simulation` only if this full check passes, else `review_required`.

An `AdvisoryResult` JSON report contains `status`, `mode: fixture`, `as_of`, `profile_id`, `risk_band`, host `policy`, `evaluations`, `revision_count`, terminal `findings`, `simulated_allocation`, `trace`, and `authority`. Every evaluation contains its weights, metrics, and findings, so initial violations remain inspectable after a successful revision. Only completion contains `simulated_allocation`; review contains null. `authority` always says `orders_authorized: false`, `professional_approval: false`. Completion means a synthetic report passed this table, never real approval.

There are at most two evaluations and one revision. No retry, persistence, provider fallback, background work, external calls, or order execution exists. The only effects are reading stdin or packaged original fixtures and writing stdout/stderr. The CLI emits deterministic JSON with no wall-clock dependency.

## Failure and termination

Domain completion and review exit 0 because both are valid simulation outcomes. Invalid transport/schema/arithmetic input emits `status: invalid_input` and a bounded host-authored error, exit 2. Keyboard interrupt emits `status: cancelled`, exit 130, with no further calculation or simulated allocation. Input/output failures exit 74 with a generic diagnostic if writable. Help and reports explicitly flush inside controlled I/O handling. A failed stdout descriptor is redirected to the null device to prevent a second interpreter-shutdown flush failure. A consumer may receive a partial report if it disconnects during output; nonzero exit is the failure signal. Unexpected programming errors are not reported as success.

## Acceptance criteria

Independent expected-value tests check per-asset and portfolio returns, sample volatility, wealth, drawdown including the initial peak, and concentration. Tests cover initial success, successful revision, persistent violation, missing data including zero-weight coverage, stale data, grid/date errors, allocation errors, unknown/duplicate keys, nonfinite/bool numbers, arithmetic and transport limits, invalid UTF-8, and cancellation/I/O handling. Real subprocess tests exercise buffered and unbuffered closed stdout for help and report output.

Qualification must execute actual fixture CLI commands, tests, a standalone case-only copy outside the repository, and an installed wheel outside the repository. Local fixture evidence cannot establish model quality, professional suitability, live services, deployment, or production behavior. Independent review remains required before the parent selects `demo-ready`.
