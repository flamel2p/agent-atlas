# Build plan

Selected scope: an independently runnable six-task synthetic documentation release. [SPEC.md](SPEC.md) owns the contract and records source facts separately from implementation choices.

1. **Contract:** select task vocabulary, dependency invariants, worker capabilities, evidence, replan triggers, deadlines, and permitted effects. Checkpoint: observable normal, adaptation, blocked, invalid-plan, and bounded-termination criteria.
2. **Implementation:** create case-local Python/uv packaging, strict schemas/graph validation, replay planner, optional structured-output planner, event-driven simulator, packaged scenarios, and stdout CLI. Checkpoint: normal and reviewer-departure examples run offline with trace/evidence.
3. **Verification:** cover dependency and capacity invariants, completed-work preservation, invalid plans, failures/limits/cancellation, run isolation, provider request/error contract, and CLI behavior. Checkpoint: meaningful fixture and mocked-provider checks pass without credentials/network.
4. **Independent review:** review implementation against SPEC and reproduce actionable findings. Checkpoint: material findings are resolved with appropriate regression checks.
5. **Closeout:** exercise documented examples, install and test a case-only copy, update README/SPEC/catalogue with actual evidence, and run root structure validation. Checkpoint: declare `demo-ready` only for selected verified scope; live-model, hosted CI, and deployment remain explicit.

Recorded on 2026-10-18. Completion evidence belongs in README and is not implied by this plan.

## Completion evidence

Completed on 2026-10-18: isolated implementation and lockfile, five replay examples, 98 passing fixture/CLI/mocked-provider checks, capacity/dependency/evidence assertions on all CLI outcomes, case-only offline installation with the same 98 passing checks, scoped CI configuration, independent review with no remaining findings, and root structural validation. See [README verification](README.md#verification) for commands, counts, environment, and evidence limits. Optional live planning is implemented; live model, hosted CI, and deployment remain unverified.
