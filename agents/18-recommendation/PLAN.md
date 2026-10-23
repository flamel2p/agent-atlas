# Agent 18 implementation plan

## Outcome

Build an independent, deterministic recommendation demo for synthetic learning exercises. Preserve the source gap documented in [reference 18](../../agent-library-analysis/agents/18-recommendation.md). The behavior contract will live in SPEC.md.

## Work checklist

- [x] `how` over the affected subsystem.
- [x] `architect` for parallel design exploration.
- [x] Write the throughput checkpoint as four todo items.
- [x] Delegate code-writing to a subagent.
- [x] Verify on the matching surface.
- [x] Rebase into small, ordered commits. Stack follow-ups. skip: This task delivers local files; history rewriting and commits are outside scope.
- [x] If the design is contested, `interrogate` before shipping. skip: No unresolved design disagreement remained after design review.
- [x] Run **Opening a PR**. skip: PR publication is outside this local plan and build request.

Architecture phases are Ground, Sketch, Agree, Implement, Scrap. Ground, Sketch, Agree, and Implement are complete. Agree proceeded without a human checkpoint. Scrap was unnecessary because no repeated structural mismatch emerged.

Design exploration phases are Frame, Fan out, Cross-judge, Pick, Graft, Verify. The rubric is constraint correctness, honest explanations/provenance, deterministic and bounded behavior, API size, and standalone verification. Each criterion uses a 0 to 3 judgment scale, not a runtime measurement.

## Design and caller usage

```python
report = recommend(request, catalogue)
```

The single public function accepts raw JSON-shaped objects, validates both, and returns a serializable report. Private immutable catalogue, exercise, request, and evaluation records keep assumptions local. The CLI fixes the catalogue to packaged synthetic data, selects a packaged scenario or one caller-supplied request file, and writes one JSON report. It has no output-path or catalogue-override capability.

Two independent sketches considered a caller-supplied catalogue in one request and a fixed packaged catalogue behind one validated boundary. Select design B's fixed CLI catalogue, explicit vocabularies, private types, and direct Python validation. An independent cross-judge scored B 15/15 and A 13/15 for the declared rubric and selected B. These scores express review judgments only.

| Alternative | Selected decision |
| --- | --- |
| One pure validated boundary and fixed CLI catalogue | Base B. It concentrates invariants and packages reproducible data without lifecycle state. |
| Caller supplies catalogue inside every CLI request | Reject. It adds input bulk and catalogue authority without helping the selected learning objective. The Python boundary still accepts a catalogue for direct use and tests. |
| Persistent strategy/retrieval/storage objects or collaborative learning | Reject. No history, second strategy, provider, or outcome dataset justifies these interfaces. |

Graft A's unmatched eligible IDs and simpler score/duration/ID ordering. Reject B's extra difficulty tie-break because eligibility already bounds difficulty and no user requirement prioritizes it among otherwise tied candidates. The judge suggested separate empty-catalogue and all-filtered statuses. Keep B's single `empty` status and explicit catalogue count, since both mean no eligible recommendation and the count preserves their distinction without another terminal state. All positive-preference outputs remain unpadded. Cold start has score zero and an explicit non-personalized reason.

The chosen interface, gate order, bounds, status precedence, and count semantics are recorded in SPEC before implementation. Routine file names may vary, but behavior deviations must be reconciled there before verification.

## Throughput checkpoint

- Blocking first steps. Read governance and source evidence, compare two designs, and select the request/ranking/fallback contracts before implementation.
- Independent workstreams. Source research and convention inspection are read-only. Design candidates own separate temporary artifacts. A single builder owns case implementation and tests.
- Shared mutable state. Use a separate builder checkout. Parent integration begins after builder handoff. Reviewers are read-only.
- Smallest safe decomposition. One implementation owner keeps schema, ranking policy, explanations, packaged fixtures, and tests coherent. Parent owns integration, catalogue, qualification, and closeout.

## Principles applied

Model the Domain selects immutable request, exercise, ranking-evidence, and terminal-report types. Separate Before Serializing Shared State selects an isolated builder checkout and stateless runtime. Prove It Works selects actual CLI, standalone-copy, wheel, and independent output checks. Sequence Work into Verifiable Units selects contract, local behavior, isolation, and independent review gates in that order.

## Verification sequence

1. Finalize SPEC, local instructions, source references, and design rationale.
2. Implement and run normal, cold-start, no-match, constrained, and invalid-input checks.
3. Independently compare CLI output with a separate ranking and constraint oracle.
4. Run the case alone, build and install its wheel, and execute from an unrelated directory.
5. Resolve independent substantive review findings and check explanations and links.
6. Record exact evidence in README and update SPEC and catalogue readiness together.

No provider calls, external writes, deployment, or publication are required.

## Implementation reconciliation and closeout

The isolated builder implemented the selected boundary in `src/recommendation/domain.py`, strict documents in `documents.py`, and a thin `cli.py`. Immutable records own one call. The catalogue and five scenarios are canonical package resources. Selected routine details now appear in SPEC, including a 32-container nesting maximum, version text bounds, exact report fields, and POSIX assumptions.

Parent integration added an independent CLI verifier. Separate review found three verifier weaknesses and corrected them before qualification. Canonical JSON distinguishes integer/float/boolean output, duplicate-key and oversized tests otherwise retain a valid request, and closed-pipe timeouts kill and reap child processes.

Independent substantive review reproduced one runtime defect. Closed inherited descriptors can make CPython's standard streams `None`. The focused regression failed before the fix with stdout tracebacks and stderr exit `1 != 2`. The parent added guards at the CLI boundary before argument parsing or error emission. Fix Root Causes led to handling this legitimate process state where stream authority enters the CLI. The focused tests passed afterward, and independent review reran all 36 tests with no remaining actionable finding.

Final qualification passed 36 tests and 87 independent CLI invocations in each of the working checkout, standalone case copy, and installed wheel. The wheel was rebuilt and reinstalled after the fix; isolated imports resolved to site-packages and installed CLI bytes matched the repaired source. Source/wheel builds, archive integrity/license inspection, repository structure, links, and whitespace checks passed. README records the exact commands, environment, fixture scope, and limits.

The case is demo-ready for synthetic fixture behavior on local POSIX Python 3.14. No model, hosted-CI, deployment, real learner-quality, commit, or publication result is claimed. No implementation decision remains open.
