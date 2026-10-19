# Build plan

Selected scope: a synthetic study assistant with scoped persistent preference/episode memory, a read-only FAQ, bounded working context, deterministic replay, and optional structured model evidence selection. [SPEC.md](SPEC.md) owns the contract.

1. **Contract:** define memory types, explicit-write authority, provenance, recall ranking, correction, expiry, forgetting, bounds, and failure semantics. Checkpoint: observable cross-session continuity and cross-user isolation criteria.
2. **Implementation:** add case-local packaging, SQLite storage, packaged FAQ, deterministic retrieval/rendering, optional provider adapter, CLI, and synthetic examples. Checkpoint: remember/recall/correct/forget and missing-knowledge paths work offline.
3. **Verification:** cover persistence across restarts, isolation, TTL/history limits, invalid state/input, atomic failure behavior, and mocked provider requests/results. Checkpoint: meaningful local tests and documented examples pass.
4. **Independent review:** review the implementation against its contract and resolve supported correctness findings with regression checks.
5. **Closeout:** exercise an isolated case-only copy, synchronize README/SPEC/catalogue, configure case-local CI checks, and run root structure validation. Mark demo-ready only for evidenced acceptance criteria; report live/hosted CI/deployment limits separately.

Recorded on 2026-10-19. This plan is not execution evidence.

## Completion evidence

Completed on 2026-10-19: isolated Python/SQLite implementation and locked dependencies; 108 passing fixture/CLI/mocked-provider checks, including the installed SDK against mock HTTP; separate-process memory/provenance/isolation/correction/forget checks; case-only installation with the same 108 passing checks; exact README setup and 11-command walkthrough; and independent review with the schema-trigger defect fixed and no remaining actionable findings. README, SPEC, root catalogue, and scoped CI configuration are synchronized. Root structure, local documentation links, and whitespace checks passed. See [README verification](README.md#verification) for exact commands, environment, scope, and unverified live-model/hosted-CI/deployment boundaries.
