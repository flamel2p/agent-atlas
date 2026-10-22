# Agent 16 implementation plan

Status: demo-ready

## Selected design and interfaces

The caller sends one `TurnRequest(user_id, session_id, text)` and receives one typed terminal result. Frozen records describe preference, session variant, dialogue plan, and result. The host grammar and state machine own interpretation. A deterministic composer receives scoped facts and preferences. SQLite stores normalized current session state, bounded completed turns, and one explicit preference per user.

Parallel design exploration considered normalized snapshots and an append-only event journal. Both separate working context from explicit durable preferences. Normalized transactions avoid event replay and compaction and are the selected base. Preserve the event candidate's atomicity and explicit preference lineage, without adding a journal. The retained source was inspected, not the original book or its code.

The independent cross-judge confirmed normalized snapshots as the coherent choice for this bounded demo. Preference provenance retains only the current explicit save's session and turn. It does not retain superseded values. Recent canonical course history drives a bounded `recap` turn, while typed session state owns focus and clarification independently of history trimming.

## Throughput checkpoint

- Blocking first steps. Read governance, templates, inventory, foundations, and source brief. Establish SPEC and two design candidates before dependent implementation.
- Independent workstreams. Read-only source/design exploration runs independently. One builder owns all case implementation in a detached worktree. The parent owns catalogue integration and independent qualification after handoff.
- Shared mutable state. Development writes use a dedicated worktree. Runtime session/preference/history updates share a single SQLite transaction because their atomicity is a real invariant.
- Smallest safe decomposition. One implementation owner keeps coupled dialogue, persistence, fixture, CLI, and tests consistent. A separate reviewer checks authority, isolation, persistence, and evidence.

## Workflow checklist

- [x] `how` over the affected subsystem. Greenfield case with existing repository ownership rules inspected.
- [x] `architect` for parallel design exploration. Normalized snapshot and event-journal alternatives assessed.
- [x] Write the throughput checkpoint as four todo items. Recorded above.
- [x] Delegate code-writing to a subagent using your configured feature model. One builder owns this case in a dedicated detached worktree.
- [x] Verify on the matching surface. All 43 source tests and standalone 99-process oracle passed. A copied case and isolated installed wheel each passed 43 tests, 21 restart/failure invocations, and the same independent 99-process oracle. Independent review passed, including a 144-subprocess final output matrix.
- [x] Rebase into small, ordered commits. Skip: no commit or history rewrite requested.
- [x] If the design is contested, `interrogate` before shipping. Skip: cross-judge settled the design; independent substantive review and fix review passed.
- [x] Run Opening a PR. Skip: no PR or publication requested.

## Build checkpoints

1. Completed. Exact grammar, bounds, statuses, schema, and interfaces are recorded in SPEC.
2. Completed. Typed states, gate/parser, policy, recap, composer, and packaged facts are implemented.
3. Completed. Guarded transactional SQLite storage, expiry, caps, and forgetting are implemented.
4. Completed. CLI and 43 meaningful normal/failure/boundary tests pass.
5. Completed. Parent qualification passed copied-case and installed-wheel suites with 43 tests, 21 restart/failure invocations, and a separate 99-process public CLI oracle in each environment. Source tests, source oracle, README walkthrough, links, whitespace, and structural checks also passed.
6. Completed. Parent reconciled independent review's stdout findings for JSON/help and provenance question. Before fixes, regression failures were `120 != 1`, `0 != 1`, and `answered != storage_error`. All now pass, together with legitimate preference provenance after source-session expiry/reuse. Final independent review and readiness catalogue synchronization are complete.

## Implementation reconciliation

The parent selected numbered catalogue listing as an actionable choice, added a bounded functional recap, and kept preference updates free of superseded values. Review fixes preserve the input/output contract. One CLI boundary owns JSON/help flushing, and failed descriptors cannot cause a second interpreter teardown failure. The assumption that argparse propagates help write errors failed under unbuffered output. The host now writes formatted help directly so its error boundary receives those failures. Provenance validation checks retained evidence without equating a reused session label with its expired generation. The specification records the limited consistency guarantee and does not claim authenticated history.

Fix Root Causes shaped output handling at its owning CLI boundary. Attack the Premise replaced reliance on argparse's swallowed write errors with an observable host-owned write. Test Behavior, Not Implementation shaped literal public-CLI oracles and failing-before regressions.

Model the Domain shaped typed dialogue states and preference enums. Separate Before Serializing Shared State shaped the isolated builder worktree and atomic runtime store. Prove It Works requires actual restart, failure, and installed-wheel evidence before readiness.
