# Implementation plan

Status: demo-ready for the selected fixture contract. Independent review and final fix review passed.

## Selected design before implementation

The public request is exactly `{request_id, state, question, labels}`. It is a
single categorical question with 2–16 distinct labels. State is untrusted data.
Python 3.14 and the standard library implement a library plus CLI. Hatchling
1.32.4 builds the isolated package; there are no runtime dependencies.

One fixed child-process fixture adapter replays an original synthetic response
bound to an exact request. Its envelope is exactly `{backend, mode, provenance,
selection, probabilities}`. The host validates that envelope before applying
policy. No live inference, training, calibration, business effects, or network.

Use decimal JSON numbers, converted to exact rational arithmetic for mass,
confidence, ties, and threshold comparison. Mass tolerance is absolute 1e-9,
inclusive. Confidence is `(pmax - 1/n)/(1 - 1/n)` with no clamp or probability
repair. Render nonterminating confidence as a 50-significant-digit decimal.
Threshold is host-owned, default 0.6 and bounded [0,1]. A tolerance-accepted
deficient near-uniform distribution can produce a tiny negative concentration;
retain that value and abstain. Probabilities retain their original decimal values.

Timeout defaults to 2 seconds, permitted range 0.05–10 seconds, plus at most
0.3 seconds of cleanup waits. Poll cancellation every 0.01 seconds while waiting.
Terminate then kill the fixed worker and reap it. At most one adapter attempt.
No background thread, retry, fallback, generated code, or persistent state.

JSON is UTF-8, at most 65,536 bytes, depth 8, without duplicate/unknown keys or
nonstandard numbers. Numeric tokens are at most 64 characters and adjusted
exponents within [-1000,1000]. Explicit files must be regular files and opened
without following symlinks in any path component.

## Throughput checkpoint

- Blocking first steps. Read governance, case contract, sources and workflow skills; select schemas, arithmetic and limits before coding.
- Independent workstreams. n/a; one tightly coupled library/CLI case has one owner, with a parent reviewer after implementation.
- Shared mutable state. Request-local immutable snapshots; fixed child per attempt, no state shared between invocations.
- Smallest safe decomposition. One case owner implements the JSON boundary, pure policy, worker lifecycle and actual CLI checks together.

## Feature playbook tracking

- [x] `how` over the affected subsystem. Sequential inspection; scaffold has no runtime.
- [x] `architect` for parallel design exploration. Parent supplied approved independent design; no nested workers allowed.
- [x] Write the throughput checkpoint as four todo items.
- [x] Delegate code-writing to a subagent using your configured feature model. This file-writing delegate owns the case; parent owns review.
- [x] Verify on the matching surface. Initial 32 local/copy/wheel checks passed on 2026-10-23. Independent review found precision/context/UTF-8 defects; final regression and qualification evidence is recorded in README.
- [x] Rebase into small, ordered commits. Parent delivers this reviewed case as a separate phase; no rebase needed.
- [x] If the design is contested, `interrogate` before shipping. Skipped: no remaining contract dispute after independent review.
- [x] Run **Opening a PR**. Skipped: user requested local phased commits.

## Acceptance work

- [x] Implement strict request/response contracts and exact decision arithmetic.
- [x] Implement finite child lifetime, timeout, cancellation, and sanitized CLI.
- [x] Add original fixtures and behavior/failure tests.
- [x] Run real-process CLI, isolated copy and installed-wheel checks.
- [x] Record actual commands and evidence, synchronize SPEC/README/AGENTS.
- [x] Parent independent review. Original findings and adjacent transport defects are resolved and independently rechecked.

## Independent review fixes

Three P2 findings were reproduced with failing-before tests. Terminating
confidence now uses exact Decimal tuple construction after checking denominator
factors 2 and 5. Repeating confidence uses an explicit host-owned Context with
ROUND_HALF_EVEN and precision 50. Caller traps, rounding and exponent settings
cannot affect either path. UTF-8 byte counts now match actual JSON transport,
including keys, request snapshots, fixtures, worker responses and CLI output.
Surrogates remain sanitized failures; true byte/depth limits remain enforced.
The transport audit also reproduced and fixed a Unicode result crash with
PYTHONIOENCODING=ascii by writing explicit UTF-8 result bytes.

A read-only stdout descriptor also reproduced an ordinary OSError followed by
Python shutdown-flush exit 120. The shared help/result guard now redirects
stdout and exits 3 for non-EPIPE errors while preserving exit 0 for broken pipes.
The actual-process regression covers both buffering modes.

Independent fix review reran 40 source, 40 copied-case and 40 installed-wheel
checks. Additional public-library and actual-CLI probes passed 60-digit exact
confidence, all Decimal traps enabled, Unicode under ASCII locale/output
settings, read-only/closed stdout, and actual SIGINT. No actionable findings
remain. The parent reconciled readiness and owns catalogue integration and
phased commits.
