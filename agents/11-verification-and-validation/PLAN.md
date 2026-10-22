# Agent 11 implementation plan

## Selected design

Build a deterministic verifier of structured synthetic release claims. Model the Domain shaped explicit Scope, Quantity, Claim, MetricRule, Evidence, Result, and Report records. One public operation accepts document bytes and returns an immutable report. Host-owned rules decide eligibility and comparison.

Two independent design sketches and a third cross-review considered these alternatives.

| Alternative | Decision |
| --- | --- |
| Structured claims with entity, metric, target and baseline | Selected. Every assertion exposes its comparison scope. |
| Release/metric-only claims and snapshot-wide expiry | Rejected. Cannot distinguish baselines or per-record eligibility. |
| Constrained text grammar | Deferred. Extraction correctness is a separate learning objective. |
| LLM or NLI extraction/evaluation | Deferred. Adds provider and semantic evaluation requirements. |

The first design is the base. The second contributed explicit serialized claim/evidence values and units. Cross-review favored baseline matching, per-record validity, equal-value corroboration, and conflicts before tolerance. Keep derived `review_required`; downstream publication approval is outside scope.

## Throughput checkpoint

- Blocking work is source grounding, design selection, and the exact schema and verdict precedence in SPEC.
- Independent workstreams are read-only research and design comparison. One builder owns coupled runtime, fixture, and test files after contract selection.
- Separate Before Serializing Shared State puts implementation in an isolated checkout. The parent owns final docs and root catalogue, then integrates completed code. Review follows integration.
- One implementation owner is the smallest safe decomposition because parsing, evidence schema, verdicts, and fixtures share invariants.

## Delivery sequence

1. Define SPEC and exact synthetic evidence schema with closed fields, scopes, domains, dates, and bounds.
2. Implement immutable records and `verify_document(document: bytes) -> Report`, with authority behind a fixed package resource.
3. Implement bounded file input, typed failures, atomic report construction, stable CLI exit codes, and no file writes.
4. Add exact, tolerance, reversed-direction, unit, missing-scope, stale/future, and conflict fixtures plus adversarial checks.
5. Package evidence and run tests/CLI, then repeat from a case-only copy and installed wheel.
6. Obtain independent correctness and explanation review, resolve findings, and synchronize README/SPEC/catalogue evidence.

Prove It Works requires actual CLI output and installed-package execution. Structure metadata alone cannot qualify the demo. No commit, PR, live-provider run, deployment, or production certification is part of this task.

## Completion record

Completed on 21 October 2026. SPEC, runtime, fixtures, tests, package data, reading guide, and catalogue are synchronized. All 61 fixture/CLI tests passed in the workspace and a case-only copy. The built wheel passed 30 CLI invocations across 16 independently specified scenarios from outside the checkout. Evidence bytes, repeatability, and unchanged inputs were checked.

Independent review identified mutable Decimal defaults leaking into a partially configured private context. The implementation now specifies every arithmetic setting. A regression covers altered defaults with overflow trapping enabled and disabled, finite exact results, and unchanged caller/default contexts. Independent follow-up confirmed the fix. The help-exit documentation mismatch was corrected. No actionable findings or selected acceptance gaps remain.

The README records commands, results, and evidence limits. Status is `demo-ready` for this synthetic fixture contract. Live models, external sources, hosted CI, deployment, and production qualification remain outside the validated scope.
