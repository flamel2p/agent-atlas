# Agent 10 implementation plan

Date: 2026-10-21

## Selected result

Build one independent Data Analysis demo. A constrained question becomes an inspectable AnalysisPlan, calculation, quality report, and chart. The [SPEC](SPEC.md) defines the exact contract.

## Design comparison

Two independent sketches compared a complete product/quarter grid with incomplete-data refusal and an observed-value workflow with missingness disclosures. Independent review preferred the first sketch's deep analyze interface, immutable records, row provenance, and artifact authority. The second contributed the single-period trend fallback.

| Alternative | Decision |
| --- | --- |
| Bounded question interpreter and host typed plan | Selected. Demonstrates interpretation, computation, and presentation offline. |
| Caller submits only a typed plan | Rejected. Removes the question-to-plan lesson. |
| Generated Python/SQL or unrestricted LLM interpreter | Deferred. Needs provider and execution-isolation decisions beyond this case. |
| Declared complete product/quarter grid | Replaced by observed-record semantics for CSV. Entirely absent products cannot be detected, so no completeness claim is made. |

Revenue Decimal arithmetic and row-level descriptive statistics distinguish this case from Agent 07's tool-selection lesson. Rank, monthly trend, and describe share one vocabulary. The cross-review rejected a two-file rename claim of crash-atomic publication. The selected contract promises exclusive directory creation and caught-failure cleanup, with partial output possible after an uncatchable kill.

## Interfaces and responsibilities

```sh
uv run --locked data-analysis --question "top 3 products by revenue_rm from 2026-07-01 to 2026-09-30" --output artifacts/top-products
uv run --locked data-analysis --question "monthly units from 2026-07-01 to 2026-09-30"
uv run --locked data-analysis --question "describe revenue_rm from 2026-07-01 to 2026-09-30"
```

One deep `analyze(question, dataset_bytes, source_label)` operation owns question/schema/plan validation and calculation. Immutable ActivityRecord, Dataset, plan variants, result rows, quality metadata, and outcomes organize the domain. The CLI owns bounded reading/publication. Rendering consumes computed results. No sibling runtime is involved.

Model the Domain shaped typed plans and observations. Separate Before Serializing Shared State shaped single-owner development in an isolated checkout. Prove It Works requires actual CLI and installed-wheel execution before readiness.

## Sequence and throughput checkpoint

1. Ground retained source claims and current official library behavior. Completed.
2. Compare designs, review authority/missingness, and fix the contract. Completed before implementation.
3. Implement types, strict boundaries, calculations, rendering, CLI, packaged fixtures, and behavioral tests with one owner. Completed in an isolated checkout and integrated after handoff.
4. Execute normal/failure paths, inspect artifacts, and review substantive behavior and explanations. Fix accepted findings. Completed; interruption cleanup was corrected and independently re-reviewed.
5. Install a case-only copy and a built wheel. Check root structure and synchronize status with evidence. Completed.

Blocking first steps are source grounding and contract selection. Independent workstreams are research, alternative sketches, and later read-only review. A separate build checkout removes shared writes; parent integration waits for handoff. One builder is the smallest safe decomposition because parser, numeric semantics, provenance, and charts must share the same domain shapes.

## Completion evidence

Completed on 2026-10-21 against the selected [acceptance criteria](SPEC.md#acceptance-criteria). The [verification record](README.md#verification) records 33 passing tests in the working case and an isolated case-only copy, successful source/wheel builds, 14 installed-wheel CLI scenarios, independent numerical and code review, three SVG examples inspected in Safari, and root structure, whitespace, and local-link checks.

Review identified a real SIGINT gap immediately after directory/file creation and before ownership registration. The CLI now briefly defers SIGINT during acquisition and cleanup registration, restores the handler, and delivers cancellation inside the cleanup boundary. A real-signal regression covers all three acquisition points, cleanup, handler restoration, and successful retry. Fresh independent review passed. The public analysis interface and numeric behavior did not change.

No implementation decision or acceptance criterion remains open. Live model, external service, hosted CI, deployment, and production qualification were not performed. No commit, PR, or publication is part of the request.
