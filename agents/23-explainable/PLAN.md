# Build plan

Owned directory: `agents/23-explainable/`.

Approved contract: a deterministic synthetic task-priority classifier with actual evidence, rule, and final events, plus audience views derived from the same immutable trace. Release requires validated explanations. No external effects or model claims.

## Completed sequence

1. Selected frozen event types, the first-match policy, replay validation, and the all-audience release gate.
2. Implemented the typed core, strict CLI, original fixtures, meaningful failure checks, and standalone packaging.
3. Completed the verification below and reconciled the observed output failure.
4. Completed independent review and fix verification. The parent owns phased commits and catalogue integration.

## Throughput checkpoint

- [x] **Blocking first steps.** Read the source and policies, name immutable types, define the exact failure and release contract, then write code.
- [x] **Independent workstreams.** Parent parallelizes independent cases. Within this case, core, renderers, CLI, and checks share contracts and stay with one owner.
- [x] **Shared mutable state.** No cross-case state. A trace is one frozen tuple per run. Source files have one writer.
- [x] **Smallest safe decomposition.** One owner builds this small coherent policy and its release gate. Parent supplies independent review.

## Design sketch

`classify(request) -> Trace` records immutable evidence, rule, and final events. `explain(trace, renderer) -> Outcome` checks canonical trace replay, renders all audiences, checks exact claims and references, then releases a priority. `load_trace(json) -> Trace` reconstructs a typed trace only after the envelope matches the executable policy. `main() -> int` owns JSON and file boundaries.

Model the Domain shaped the frozen typed event union and policy registry. Prove It Works requires real process, copied-case, and installed-wheel checks. The source reading guide and in-code explanations follow repository policy and the technical-writing skill.

## Verification tasks

- [x] Unit behavior and adversarial tests. 33 methods passed, including 72 threshold scenarios.
- [x] Real CLI fixtures and malformed input checks. 29 checks passed.
- [x] Case-only copied directory execution. 33 unit tests and 30 CLI checks passed.
- [x] Installed wheel execution outside the source checkout. 33 unit tests and 30 CLI checks passed.
- [x] README evidence record with exact commands and limits.
- [x] Independent review and fix verification passed. The reviewer did not write implementation code.

## Review reconciliation

Independent review found help output outside the protected stdout path. A process regression failed before the fix with exit 120 instead of 2. The controlled writer now handles help and result output, with flush and quiet I/O failure. The parent reran 33 tests, 29 local CLI checks, and 33 tests plus 30 CLI checks in each isolated distribution. Independent fix review passed. Fixture qualification is complete.
