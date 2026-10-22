# Agent 15 implementation plan

Status: demo-ready

## Selected design

Build one bounded pure experiment on frozen dataclasses, tuples, and explicit terminal report variants. Two substantive modules keep retrieval, proposal, and gate ownership together while isolating JSON schema knowledge. Candidate selection never receives holdout input.

The parent completed parallel design exploration and a cross-judge. Design A is the base. Accepted graft from B is topic-scoped adaptation. The chosen rank order is overlap, optional topic revision, and document ID. Additive scoring, a durable version registry, report-file publication, approval commands, and deployment are outside this contract. Baseline retention is not deployed rollback.

## Interfaces and ownership

- `load_scenario(ScenarioName) -> ScenarioData` validates and loads allowlisted bundled fixtures.
- `run_experiment(ScenarioData) -> ExperimentReport` returns one immutable terminal report.
- `report.to_json() -> str` renders canonical JSON and a deterministic report digest.
- `experiment.py` owns domain types and pure policies. `scenarios.py` owns boundary validation. `__main__.py` owns CLI parsing and output.
- `src/self_improving/fixtures/` owns selection, host curator, and holdout records. `tests/` owns fixture, mutation, and CLI acceptance checks. `scripts/qualify.py` owns standalone-copy and installed-wheel qualification.
- `scripts/verify_independent.py` derives ranking choices for enumerated queries and recomputes lineage through the public experiment interface. Qualification also runs it against the installed wheel with an isolated Python process.

## Throughput checkpoint

- Blocking first steps. Read selected contract, governance, templates, both design artifacts, and source analysis. Write SPEC and this plan before dependent logic.
- Independent workstreams. The parent owns source/design/review/qualification artifacts outside this implementation worktree. This worker owns the complete case only.
- Shared mutable state. The worker has an exclusive worktree and case path. The application has no shared mutable state or runtime writes.
- Smallest safe decomposition. One implementation owner keeps the tightly coupled frozen input, proposal, and report contracts synchronized. Parent independent review provides separation.

## Build checkpoints

1. Establish SPEC, case instructions, README, package metadata, and exact runtime bounds. Inspect the new contract before logic.
2. Define frozen domain shapes and implement deterministic retrieval, feedback eligibility, proposal lineage, development gate, heldout gate, and canonical report serialization.
3. Implement bounded decoding and three-file fixture schema. Add improvement, regression, insufficient, poisoned, development-rejection, and no-gain fixtures.
4. Verify acceptance and failure paths with independent expected choices, query deduplication, split checks, malformed inputs, determinism, and CLI exits.
5. Run real CLI scenarios, copied-case checks, and installed-wheel checks. Record exact evidence. Hand off with status in-progress for independent review and parent integration.

## Workflow checklist

- [x] `how` over the affected subsystem. Parent completed design investigation; no existing case implementation.
- [x] `architect` for parallel design exploration. Parent supplied both artifacts and selected synthesis.
- [x] Write the throughput checkpoint as four todo items. Recorded above.
- [x] Delegate code-writing to a subagent using your configured feature model. One case builder implemented the approved contract in an isolated worktree.
- [x] Verify on the matching surface. The local suite, all six CLI scenarios, copied-case suite, and installed-wheel qualification passed.
- [x] Rebase into small, ordered commits. Skip: parent requested no commits and owns integration.
- [x] If the design is contested, `interrogate` before shipping. Skip: parent cross-judge settled the design; parent owns review.
- [x] Run Opening a PR. Skip: no PR or publication requested.

Implementation checkpoints 1-5 and parent closeout are complete. Independent review found no actionable issues. The parent passed the 28-test suite, standalone-copy and installed-wheel qualification, 372 independent oracle queries, and repository structure checks. The chosen stdout I/O failure contract is nonzero, because interpreter finalization may determine the exact code after a broken pipe.

## Implementation reconciliation

The parent accepted the selected relevance-first revision tie-breaker before implementation. The final proposal includes complete supporting feedback, trace, and curator records so its evidence digest can be recomputed. This refines report representation without adding adaptation authority. The parent added independent qualification after builder handoff and kept the runtime contract unchanged. All current source paths use `src/self_improving/`.

Model the Domain guided frozen inputs and explicit report variants. Test Behavior, Not Implementation guided before/after answer checks. Prove It Works guided actual CLI, copied-case, and installed-wheel qualification.

## Evidence limits

Fixture counts are exact-ID retrieval outcomes on synthetic public examples. They establish this deterministic policy and its gates. They do not establish semantic FAQ quality, statistical generalization, curator authentication, deployed activation, model learning, provider behavior, or production safety. Immutable snapshots and hashes provide logical lineage, not tamper-proof files. Public heldout reuse is not a statistically fresh partition.
