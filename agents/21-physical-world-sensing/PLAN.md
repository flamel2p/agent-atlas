# Agent 21 implementation plan

## Goal and design

Build an isolated smart-building replay that turns bounded timestamped observations into explained zone estimates, alerts, and simulated commands. The retained [source brief](../../agent-library-analysis/agents/21-physical-world-sensing.md) informs the pattern. [SPEC.md](SPEC.md) owns selected behavior.

| Candidate | Benefit | Cost | Decision |
| --- | --- | --- | --- |
| Stateless evaluation at chronological replay ticks | Small interface, reproducible decisions, explicit observation provenance | No hysteresis or physical feedback | Selected |
| Stateful on/off hysteresis with retained actuator state | Demonstrates anti-cycling and state-dependent transitions | Requires start state, dwell policy, and recovery semantics beyond the source example | Deferred |

Two independent design investigations covered these alternatives. The selected design retains a latest-observation cache during replay, but each controller decision depends only on that tick's eligible evidence. Graft the second candidate's one-sample-per-sensor rule, full prevalidation, and boundary tests. Reject its forced-off behavior on missing data because no hardware acknowledgment exists in this case.

The Model the Domain principle changes the implementation choice to immutable scenario, reading, estimate, and command records plus one replay-owned cache. The Prove It Works principle requires actual subprocess output and independent arithmetic in addition to unit checks.

## Work checklist

- [x] `how` over the affected subsystem.
- [x] `architect` for parallel design exploration.
- [x] Write the throughput checkpoint as four todo items.
  - Blocking first steps. Fix the schema, temporal eligibility, channel authority, and numerical rules before code.
  - Independent workstreams. One builder owns implementation, packaging, fixtures, and unit checks. The parent owns the contract, catalogue, and independent CLI checker.
  - Shared mutable state. The replay invocation exclusively owns its cache. Development workers own disjoint files.
  - Smallest safe decomposition. One implementation owner keeps parsing and control semantics coherent. Independent review checks the whole result.
- [x] Delegate code-writing to a subagent using the selected contract.
- [x] Verify on the matching surface.
- [x] Rebase into small, ordered commits. skip: no commit or branch publication requested; leave a reviewable working-tree change.
- [x] If the design is contested, `interrogate` before shipping. skip: no unresolved design dispute; independent correctness review completed.
- [x] Run **Opening a PR**. skip: no PR requested for this local demo build.

## Qualification sequence

1. Complete the specification and fixture expectations.
2. Build local runtime and behavior checks.
3. Run independent CLI probes, isolated case-copy checks, and installed-wheel checks.
4. Resolve independent review findings. Record actual evidence and update readiness together.

Architect phases Ground, Sketch, Agree, and Implement are complete. Scrap was unnecessary because no repeated structural friction arose. No material product decisions remain open. All four qualification steps passed on 2026-10-23. See [VERIFICATION.md](VERIFICATION.md).

The builder identified that equal-weight means can be repeating fractions. Accepted contract correction uses exact rational arithmetic for decisions and rounds only display strings to six fractional places with ROUND_HALF_EVEN. The earlier promise of universally exact decimal output was mathematically impossible.

Independent contract review confirmed the snapshot design after that correction and a clarification that critical alerts use selected latest samples. The review found no remaining actionable contract issue. It supplied no runtime evidence. Implementation and CLI-checker reviews are separate qualification steps.

Implementation review accepted three concrete corrections. Packaged scenarios now share the bounded nonblocking regular-file reader with external input. Failed stderr delivery preserves the promised exit status. Display formatting uses a fresh Decimal context so caller traps and exponent limits cannot change valid replay. Checker review also strengthened otherwise-valid duplicate/size rejection probes, command-log reconciliation, multi-sensor CO2 and occupancy cases, and the decimal-flooring boundary. Final unit, independent CLI, isolation, wheel, and independent runtime review evidence passed.
