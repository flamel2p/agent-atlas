# Build plan

Selected scope: one independently runnable synthetic support-triage case. [SPEC.md](SPEC.md) owns behavior; source claims and implementation choices remain separate.

1. **Contract:** define the three routes, strict schemas, trusted input boundary, read-only tool, policy precedence, thresholds, and bounded termination. Checkpoint: each important normal/failure outcome has observable acceptance criteria.
2. **Implementation:** create a local Python/uv CLI, fixtures, validated status tool, deterministic baseline, optional structured-output provider, host policy, sanitized trace, and response renderer. Checkpoint: routine outage runs offline; hard gates cannot be overridden by a proposal.
3. **Behavior checks:** cover route thresholds, human availability, restricted effects, malformed inputs/proposals/evidence, provider failure/refusal/timeout/cancellation, redaction, and run isolation. Checkpoint: complete case suite passes; provider checks are explicitly mocked.
4. **Independent review:** trace code against the specification and reproduce material findings. Checkpoint: actionable findings are fixed and regression checks pass.
5. **Closeout:** exercise documented CLI examples, install/run the case in isolation, update README/SPEC/catalogue with actual results, add a scoped runtime CI job, and run repository structure validation. Checkpoint: `demo-ready` only for the evidence actually obtained; live-model/hosted CI/deployment remain separately stated.

Plan recorded on 2026-10-18. Implementation status and verification results are maintained in README, not inferred from this checklist.

## Completion evidence

Completed on 2026-10-18: the case-local implementation, lockfile, 11 synthetic examples, 123 passing checks (96 fixture/27 mocked-provider), and runtime CI configuration are present. Independent review's missing-SDK preflight finding was fixed and regression-tested. All 11 CLI examples passed; a separate copy installed and passed the same 123 checks without sibling resources or credentials, using a populated dependency cache. See [README verification](README.md#verification) for exact commands and evidence limits. Live-model, hosted CI, and deployment validation remain unverified and are not required by the selected acceptance criteria.
