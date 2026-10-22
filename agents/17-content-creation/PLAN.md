# Agent 17 implementation plan

## Outcome

Build a standalone synthetic campaign composer with an observable draft, review, and revision loop. The selected contract is [SPEC.md](SPEC.md). Keep host validation distinct from human approval and publication.

## Design and caller usage

```python
result = create_content(brief)
```

```sh
uv run --locked content-creation
uv run --locked content-creation --scenario exhausted
uv run --locked content-creation --brief src/content_creation/data/briefs/launch.json
```

One call hides fixture loading, planning, provenance, review, repair, and stopping. Callers supply constrained requirements and receive immutable reports. The CLI emits JSON and never writes artifact files itself.

Immutable `Brief`, draft block, evidence, violation, attempt, artifact, and run result types describe the domain. The controller owns plan transitions. Rendering and review are pure. Exact factual sentences and permitted copy form the closed content vocabulary. The README reading guide will link their final modules.

## Alternatives and synthesis

Two independent design sketches converged on structured content plans and actual reviewer feedback. The alternatives were free-form prose with source IDs and enumeration of complete candidate combinations.

| Design | Decision |
| --- | --- |
| Structured facts and copy, with local review-driven repairs | Selected. Exact text and bidirectional provenance are testable. Typed failures determine the next plan. |
| Free-form prose plus citations | Rejected. Citation presence cannot establish factual entailment. A semantic verifier would add an unvalidated second problem. |
| Enumerate every candidate combination | Rejected. Search cost grows with content choices and obscures the bounded revision lesson. |

Use design A as the base for structured briefs, stdout-only reports, and exact character-offset evidence. Adopt design B's explicit prohibition on unchanged retries and pure reviewer boundary. Use `validated` rather than `approved` for passing machine checks, with `approval: not_granted` in every report. An independent design judge selected A, scoring it 14/15 against B at 13/15 for fact integrity, adaptation, stopping, API size, and standalone verification. The judge supported the same grafts and rejected arbitrary output-path authority. These are design judgments, not runtime measurements.

The Model the Domain principle leads to typed attempts and terminal states. Separate Before Serializing Shared State leads to one implementation owner in an isolated checkout. Prove It Works leads to direct CLI execution, independent output checks, and installed-package verification.

## Throughput checkpoint

- Blocking first steps. Read governance and source analysis, compare designs, and select input/evidence/retry contracts before implementation.
- Independent workstreams. Designers own separate ignored artifacts. One builder owns case code and tests. Parent owns root catalogue and final verification/docs.
- Shared mutable state. Builder works on a private branch in an isolated checkout. Integration occurs after handoff. Reviewers are read-only.
- Smallest safe decomposition. One builder keeps the content grammar, reviewer, and repair loop coherent. Independent reviewers check correctness without sharing implementation ownership.

## Build and verification sequence

1. Write SPEC, local AGENTS, source references, and this plan. Initialize metadata as in-progress.
2. Build immutable data contracts, bounded input loading, packaged synthetic sources, rendering, review, and repair. Add CLI, lockfile, and tests.
3. Run the documented suite and CLI success/failure examples. Independently verify actual output facts, offsets, terminal status, revision differences, and limits.
4. Copy the case alone, install locked dependencies, and run its suite. Build a wheel, install into a separate environment, and run from another working directory.
5. Obtain independent substantive review and review code explanations against root requirements. Fix supported findings and rerun affected checks.
6. Record exact verification evidence. Update README/SPEC/catalogue to demo-ready only when selected criteria pass.

Commit history changes, PR publication, provider calls, and deployment are outside this local build task.

## Implementation reconciliation

The implementation must preserve all selected inputs, outputs, authority, and failure contracts. Routine module/file naming and synthetic fixture copy can be settled by the builder. Record any accepted behavior changes here before final verification.

Implemented the selected immutable `Brief -> RunResult` boundary in `src/content_creation/domain.py`, strict data reads in `boundary.py`, and stdout-only reporting in `cli.py`. Canonical packaged content and six briefs live under `src/content_creation/data/`; no fixture copies are maintained elsewhere.

Routine decisions are now explicit in SPEC. Required facts retain caller order, optional facts use rank then ID, brand repair may remove an optional fact, and copy shortening maximizes the saved word count. Integrity failures stop the affected artifact, while the other channel still completes. Final-file symlinks are rejected; directory aliases such as macOS `/tmp` remain allowed. POSIX descriptor checks and nonblocking reads protect the selected regular file. Normalized duplicate phrases, JSON depth/item limits, and bounded package reads are executable checks.

The builder ran locked offline setup, the unittest suite, all six actual console scenarios, and buffered/unbuffered closed-pipe checks. Exact evidence is in README. Parent integration subsequently completed copied-case, wheel, root structure, independent review, and catalogue qualification as recorded below.

Parent integration accepts these routine refinements within the selected contract. Integrity failures are terminal for the affected artifact rather than attempting to repair an impossible renderer state. Explanation review found and corrected an unbounded resource read and inaccurate run-wide stopping wording.

## Integration verification

The final substantive review found that the reviewer trusted proposed fact order. This violated required caller order and audience priority despite valid source spans. The parent fixed the reviewer to derive the expected sequence independently, added adversarial reflow/controller checks, and extended the separate CLI oracle to cover both audience rankings and required-fact permutations. The repaired implementation passed 44 tests and 82 oracle subprocesses in each of the working checkout, standalone case copy, and installed wheel. Final independent recheck passed. The reviewer independently checked valid order/subset combinations, reversed evidence-record order, and invalid textual reorderings, then reran the 44 tests and 82-invocation oracle. No actionable findings remain.

The source distribution includes the independent verifier, tests, local instructions, packaged data, and the preserved MIT license. The wheel contains the runtime and its data. Offline source and wheel builds passed. No provider, CI, deployment, commit, or publication action occurred.

All planned build and qualification gates are complete. README, SPEC, and the root catalogue are demo-ready for fixture mode. No live-model or deployment evidence is claimed.
