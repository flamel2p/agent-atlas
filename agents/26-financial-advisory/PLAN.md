# Financial Advisory implementation plan

[SPEC.md](SPEC.md) owns the behavior contract. Parent selected this scope after two independent design passes recorded in the [batch plan](../../docs/AGENTS_22_32_PLAN.md).

## Data and ownership

The case owns a Python 3.14 standard-library domain core, strict JSON boundary, named packaged fixtures, tests, and local qualification script. `PriceSeries`, `SyntheticProfile`, `AllocationProposal`, `RiskReport`, `PolicyFinding`, and `AdvisoryResult` represent the typed flow. The parent alone updates the root catalogue, integrates independent review, and decides readiness.

## Sequence and results

1. Completed: finalized schemas, arithmetic, timestamps, host table, bounds, and terminal labels in SPEC before implementation.
2. Completed: implemented immutable run-local inputs, strict bounded JSON CLI, daily metrics, data readiness, and at most one equal-weight host revision. No cash, provider, persisted state, or professional authority exists.
3. Completed: 31 tests pass, including independent numerical expectations, normal/revision/review behavior, invalid schema and arithmetic, data completeness, cancellation/I/O unit checks, and real buffered/unbuffered help/report closed-stdout processes.
4. Completed: actual CLI and rerunnable qualification passed on 2026-10-23 with Python 3.14.8. Source, case-only temporary copy, and installed wheel each passed 31 tests. All four fixtures passed in those environments and through the installed console command. The fresh installed package ran from an unrelated directory.
5. Completed independent review with no actionable findings. Status is `demo-ready` for fixture scope; parent owns phased commits and catalogue integration.

## Selected decisions and tradeoffs

- The synthetic universe is declared explicitly. Allocation coverage is exact and all assets require fresh aligned histories, even at zero weight. Missing data produces review without numerical defaults or a revision.
- Observations use consecutive calendar days. Sample volatility is per-period and not annualized. Drawdown starts at initial wealth 1. Constant weights are reapplied each period with no cost or execution model.
- Decimal parsing enforces exact input sums, numeric bounds, and adjacent price ratio limits before finite binary64 calculation. At most eight assets and 64 observations keep arithmetic and report size bounded.
- The invented profile selects one of three fixed host tables. The host may revise once to equal weights, recomputes all metrics, then either completes the simulation or stops for review. Initial findings remain in evaluation evidence.
- CLI input is stdin or a closed enumeration of packaged fixture names. No caller path is opened. The process can wait for EOF until cancelled; byte, nesting, arithmetic, and evaluation bounds apply once input arrives.
- Help bypasses argparse's write handling. Both help and JSON use a controlled writer with an explicit flush and failed-descriptor silencing, preventing hidden unbuffered write failures and shutdown exit 120.
- Pure functions make calculations inspectable. A generic framework or real-model adapter would add no evidence for this learning objective.

## Reconciliation

No approved scope was weakened. The final schema uses only `completed_simulation` and `review_required` as valid domain outcomes, plus CLI `invalid_input`, `cancelled`, and nonzero I/O errors. These selected labels replace the scaffold's provisional list. Stale or missing data, unknown assets, invalid allocations, and persistent policy violations cannot release a simulated allocation.

Exact commands and evidence fields are recorded in [README.md](README.md). This evidence is exclusively local fixture/simulation evidence. No live provider, professional-service quality, deployment, or production claim is established.
