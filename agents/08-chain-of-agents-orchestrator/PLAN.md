# Agent 08 implementation plan

Selected on: 2026-10-21

## Learning objective and boundary

Make typed specialist coordination and manager authority visible in a small local release-evidence simulation. The [SPEC](SPEC.md) owns behavior. The [source brief](../../agent-library-analysis/agents/08-chain-of-agents-orchestrator.md) informs the pattern and records the source's incomplete arbitration.

## Design alternatives and decision

| Choice | Benefit | Cost | Decision |
| --- | --- | --- | --- |
| Fixed release prerequisite, then test/feedback fan-out | Direct dependency flow, one state owner, small interface | Fixed topology; cooperative deadlines | Selected |
| Private task DAG with subprocess specialists | Graph-driven scheduling; can terminate stuck processes | Process protocol, graph validation, platform cleanup | Deferred; not needed for bounded deterministic functions |

Two independent design candidates and a separate cross-review favored the fixed workflow. The parent selected it for the smaller public interface and precise synthetic evidence semantics. Adopt the alternative's explicit preservation of review items alongside partial failures. A separate incomplete status adds no distinction needed here; failed/timed_out already carry partial findings. A claim-basis field adds no value while all claims are direct structured assertions. No confidence scoring, source voting, or inferred release readiness.

The Model the Domain principle led to immutable evidence/envelope/report types and explicit task states. Separate Before Serializing Shared State led to per-run manager memory, immutable specialist inputs, and a separate builder checkout. Prove It Works requires CLI and installed-wheel execution as well as unit checks.

## Intended interface and ownership

```python
report = await analyze_release("consistent")
review = await analyze_release("contradictory")
```

One asynchronous operation owns fixture loading, delegation, acceptance, cleanup, and reconciliation. `contracts.py` defines domain types. `evidence.py` validates packaged resources. `specialists.py` contains the bounded transformation used by the three role-scoped specialists. `manager.py` owns run memory and lifecycle. `cli.py` owns arguments, JSON output, and exits. The README links the source in review order.

## Throughput checkpoint

- Blocking first steps. Read governance/brief, compare designs, and settle the behavior contract before code.
- Independent workstreams. Source/API evidence and independent design candidates run in parallel. One builder owns coupled case implementation and tests. Review and standalone execution can run independently after handoff.
- Shared mutable state. Builder uses an isolated checkout. Parent integrates after builder handoff and alone edits the root catalogue. Runtime specialists never share mutable memory.
- Smallest safe decomposition. One code owner keeps schemas, lifecycle, fixtures, and tests synchronized. Splitting these interfaces among concurrent writers would add coordination without independent deliverables.

## Build and verification sequence

1. Establish case instructions, SPEC, and this plan. Record source facts separately from choices.
2. Implement strict fixture contracts, provenance, and deterministic specialists. Include reviewer explanations of authority and invariants.
3. Implement fixed manager flow, validation, review synthesis, timeouts, cancellation, and CLI.
4. Exercise normal, contradiction, negative, missing-evidence, execution-failure, and timeout behavior. Test forged/omitted evidence, concurrency, cancellation, and isolation.
5. Run independent correctness/explanation review. Resolve actionable findings without weakening acceptance criteria.
6. Copy only the case into a temporary directory, install/test independently, build a wheel, and run it outside the checkout. Validate packaged resources and entry points.
7. Reconcile README/SPEC/catalogue status with actual evidence. Run the root structure checker. Record limitations and exact commands.

## Evidence and completion

Completed on 21 October 2026. Immutable contracts, strict packaged evidence, three role-scoped specialists, manager-owned lifecycle/reconciliation, and the fixture CLI are implemented. All 104 checks passed in the builder checkout and again in a case-only installation. The sdist/wheel build and all eight scenarios in a fresh installed-wheel environment passed. Independent review closed both findings after regression checks and separate probes. The [README](README.md#verification) records exact commands and evidence. Status is `demo-ready` for the fixture contract. No commit, push, PR, or deployment was performed.

## Review resolutions

The original per-specialist timeout context could cancel asynchronous cleanup a second time. The final manager owns all deadline decisions and sends at most one cancellation to each unfinished child. Cleanup can finish after a deadline. This preserves the selected contract rather than weakening it. Independent probes verified external/repeated cancellation, sibling failure, timeout crossing the run deadline, and already-cancelling children.

Timeout range validation now rejects enormous integers before converting them for a finiteness check. Both deadline fields have regression coverage. No material behavior-contract deviation or unresolved review finding remains.
