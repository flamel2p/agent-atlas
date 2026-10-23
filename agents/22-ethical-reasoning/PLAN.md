# Ethical Reasoning build plan

Approved scope is one independently runnable synthetic policy checkpoint. Parent owns root integration and independent review.

## Completed sequence

1. Selected the source boundary, immutable request, policy authority, exact count arithmetic, and one-repair limit.
2. Implemented the domain, frozen policy registry, enforcing dispatcher, fixtures, and bounded CLI.
3. Qualified the behavior and actual console paths. After review fixes, 26 tests passed locally, in a case-only copy, and against an installed wheel.
4. Completed independent review and fix verification. The parent owns phased commits and catalogue integration.

## Sketch and chosen data shape

`Request` contains a frozen `Action` and tuple of `GroupCount`. A host mapping contains immutable named `Policy` records. Each rule returns structured `Finding` records. `SimulatedDispatcher.attempt(Request)` rechecks all rules and returns `Attempt` with no caller-supplied permission. `run(Request)` owns one redaction and terminal `RunResult`. Structured `Event` records and symbolic `Effect` records remain run-local.

Alternative considered is `evaluate -> permit object -> execute`. It requires authenticating the permit and preventing stale context. Re-evaluation at the only simulated effect boundary is smaller and makes bypass behavior directly testable.

Model the Domain shaped the frozen request and policy registry. Prove It Works shaped real CLI, isolated-copy, and installed-wheel checks. No production or provider verification is planned.

## Review reconciliation

Independent review found buffered stdout failure outside the protected write. A real-process regression failed before the fix with exit 120 instead of 2 and passed afterward for result/help output in buffered and unbuffered processes. The parent reran 26 tests locally and in both isolated distributions. Independent fix review passed. Fixture qualification is complete.
