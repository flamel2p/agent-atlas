# Healthcare Intelligence implementation plan

[SPEC.md](SPEC.md) owns behavior. The parent selected this scope after two independent design passes in the [batch plan](../../docs/AGENTS_22_32_PLAN.md).

## Data and ownership

Immutable observations, knowledge records, beliefs, evidence events, issues, review results, requests, and reports belong to one run. The host owns validation and evidence/review transitions. The case directory owns every runtime, fixture, test, dependency, and qualification file. The parent owns root catalogue changes and independent review.

## Implementation reconciliation

1. Completed schema and policy selection in SPEC before the acceptance run. Fixed three wholly fictional pattern labels and two fictional signals. Selected exact decimal input and rational arithmetic, 24-hour observation freshness, 30-day knowledge freshness, and inclusive boundaries.
2. Completed the standard-library package, CLI, original fixture, local pyproject and lock. Input byte/depth/node/numerical/cardinality bounds run before domain work. There are no providers, environment secrets, external effects, persistence, retries, or repair loops.
3. Completed 43 behavioral tests with independent expected weights and posterior arithmetic. Checked unit and order normalization, provenance, duplicate evidence, every evidence/review gate, probability and timestamp validity, strict JSON and resource bounds, FIFO/symlink/directory rejection, interruption, help, and broken output pipes.
4. Completed actual CLI, isolated case-copy qualification, and installed-wheel qualification outside the checkout on Python 3.14.8. The rerunnable case-local `scripts/qualify.py` passed 43 tests in each isolated mode plus real console entry points. README records exact commands, date, modes, results, and limits.
5. Completed substantive independent review and fix verification. Status is demo-ready for the selected fixture scope. The parent owns phased commits and catalogue integration.

## Selected tradeoffs

Exact fractions make positive posterior mass and the authored arithmetic inspectable. Float fields are output approximations only. The toy likelihoods are conditionally independent assumptions, without clinical meaning or calibration evidence. Matching identical source rows adds provenance without double-counting evidence. A conflict at any supplied matching version remains unresolved, even when one row is older or stale. All evidence gates withhold the entire posterior to avoid publishing partial inference as a conclusive result.

A simulated review acknowledgement never overrides unresolved evidence and never grants real approval. Input is structured JSON with no arbitrary instructions. Console output is the sole runtime report effect. A generic agent framework and real-model adapter are outside the selected contract.

## Review reconciliation

Independent review found argparse help could hide a failed write or flush at shutdown. Added real-process buffered/unbuffered result/help regression, observed the intended pre-fix mismatch, and routed help through the controlled output boundary. Parent local suite now passes 43 tests. Qualification passed 43 tests in both isolated distributions, and independent fix review passed.
