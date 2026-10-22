# Agent 12 implementation plan

## Selected design

Build a deterministic scheduling puzzle with constraint-directed local repair. Model the Domain shaped immutable task, candidate, violation, evaluation, attempt, and report records. One operation accepts document bytes and returns a complete report.

Two independent sketches compared whole designs.

| Design | Decision |
| --- | --- |
| Conflict-directed local repair | Selected for visible feedback and small run state. It can stop at local minima. |
| Violation-guided best-first frontier | Rejected for this scope. Frontier/visited management adds a broader search algorithm. Its pure boundary and tighter bounds informed the selected design. |
| External model or orchestration framework | Deferred. Adds provider and quality requirements without helping this constraint loop. |

The independent cross-judge preferred the frontier design's single interface and found the first sketch's public API ambiguous. The synthesis adopts one `solve_document(document: bytes) -> Report` API and one domain module for types, parsing, and evaluation. Internals are not re-exported. The parent retains local repair because frontier machinery is unnecessary for this objective. Local minima are explicit outcomes, including for solvable inputs. No selected contract remains contested.

## Throughput checkpoint

- Blocking work is source grounding, design comparison, and exact evaluator/budget semantics before implementation.
- Independent workstreams are grounding and design sketches. Runtime, fixtures, and tests have one builder after contract selection.
- Separate Before Serializing Shared State puts the builder in an isolated checkout. Parent integration, catalogue edits, and independent review follow release of that checkout.
- One builder is the smallest safe decomposition because parsing, scores, candidate indexing, counters, and history share invariants.

## Delivery sequence

1. Establish instructions, specification, plan, and initial documentation.
2. Implement immutable domain records, strict parsing, and independent evaluator checks.
3. Implement initial proposal, violation-directed repair, tie-breaking, counters, and honest stopping.
4. Add bounded regular-file CLI input and packaged examples with stable outputs/codes.
5. Run tests/commands, then verify a case-only copy and installed wheel outside source.
6. Obtain independent correctness/explanation review, resolve findings, and synchronize evidence/catalogue.

Prove It Works requires real CLI output and independently checked schedules. Structure metadata alone cannot qualify the case. This task creates a local plan and implementation. Commits, PR publication, live providers, deployment, and production certification are outside scope.

## Completion record

Completed on 22 October 2026. The builder implemented the selected contract in an isolated checkout, then the parent integrated the case and catalogue. Immutable domain records, strict parsing, per-tick evaluation, bounded local repair, the POSIX CLI, and seven packaged examples are present. No material design decision remains open.

All 35 fixture/CLI tests passed in the workspace and a case-only copy. A separately installed wheel passed 42 CLI invocations outside the checkout. Ten independently derived puzzles and a separate arithmetic oracle checked 424 schedule combinations, including a feasible puzzle that stops at a local minimum. The documented revision command returned a feasible schedule after two proposals and three evaluations. Exact commands, environment, and evidence limits are in the [verification record](README.md#verification).

Independent reviews covered correctness, isolation, authority, and source explanations. Review found buffered stdout errors that changed exit codes during interpreter shutdown, an overstated output-atomicity claim, and a race in the acceptance checker's pipe setup. Fix Root Causes placed write and flush handling at the output boundary. Both broken pipes and read-only descriptors now return exit 2 without shutdown tracebacks. The contract describes possible truncation, and the checker closes the reader before child launch. Fresh independent review found no actionable issues and reran the installed CLI tests and checker successfully.

Root structure checking passed. README, specification, and catalogue now mark the case `demo-ready`. The initial online dependency sync failed on sandbox DNS resolution; cached offline installation succeeded. No fresh dependency download, mocked provider, live model, hosted CI, deployment, or production qualification was validated.
