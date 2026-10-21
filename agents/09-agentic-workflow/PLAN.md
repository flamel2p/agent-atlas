# Agent 09 implementation plan

## Outcome and architecture

Build a standalone equipment-request workflow whose review checkpoint and bounded retries survive process restart. The selected contract is in [SPEC.md](SPEC.md).

Two independent design passes compared a transactional state machine with an event-sourced reducer. Both chose SQLite snapshot, audit, command receipts, and a unique simulated fulfillment in one transaction. The transactional design keeps the lesson on authority and recovery. Event sourcing adds replay and event-version maintenance without helping this fixed workflow. LangGraph or CrewAI would add another execution model without a demonstrated need.

The selected interface is `init`, `submit`, `advance`, `review`, `cancel`, `show`, and `audit`. One `advance` performs one transition or attempt. A host-owned catalogue prevents caller-supplied prices from changing review routing. Historical command receipts recover lost responses. A review decision uses the stored version so a stale operator cannot silently overwrite a later decision.

## Work sequence

- [x] Read repository governance, inventory, foundations, and Agent 09 source brief.
- [x] Compare independent architecture candidates and select the explicit state-machine shape.
- [x] Implement typed domain contracts, strict input parsing, and deterministic assessment.
- [x] Implement atomic SQLite commands, receipts, audit, and simulated fulfillment.
- [x] Implement CLI, synthetic fixtures, and behavioral/fault/restart tests.
- [x] Run documented routine, review, and retry CLI paths plus local locked install.
- [x] Run the case-only installation and installed wheel through independent checks.
- [x] Reconcile independent correctness and explanation review.
- [x] Update verification evidence, catalogue, and readiness together.

## Ownership and throughput

The contract is the blocking first step. Read-only source/design work runs independently. One builder owns all coupled case files in an isolated checkout. The parent owns catalogue integration and final verification. Shared SQLite state is intentional at runtime and serialized in short transactions; development work does not share write targets.

## Design controls

The Model the Domain principle selects one state enum and one transaction owner. Separate Before Serializing Shared State selects isolated development copies. Prove It Works requires CLI subprocess, restart, fault, and installed-artifact checks before readiness. These controls supplement the repository's case isolation and explanation rules.

## Evidence boundaries

On 2026-10-21, all 16 case tests passed locally and in a case-only installation. The installed wheel passed 46 CLI invocations covering six scenarios and input/path/replay checks. Independent review findings were fixed and independently rechecked. The normal run path and selected recovery/limit criteria support `demo-ready`; exact commands and scope are recorded in [README.md](README.md#verification).

Review tightened successful no-op receipts and expiry/version ordering, rejected unpaired Unicode surrogates, normalized SQLite paths, and exercised an actual COMMIT failure under reader contention. SQLite schema checks distinguish the literal internal `sqlite_` prefix from similarly named user objects. These changes preserve the selected transaction model.

The implementation is an original deterministic simulation informed by retained source analysis. The book is not revalidated, and no source code is copied. There is no live-model, authenticated-review, external-delivery, hosted-CI, deployment, or production evidence.
