# Embodied Intelligence implementation plan

[SPEC.md](SPEC.md) owns the behavior contract. The parent selected the synthetic scope after independent design passes recorded in the [batch plan](../../docs/AGENTS_22_32_PLAN.md). Only this directory is implementation-owned. The parent owns catalogue changes and phased commits.

## Selected data and authority

Immutable CartState, Command, Event and Request records describe one finite scenario. Dispatcher is the single writer of run-local state, accepted-action receipts and effects. FixturePlanner iterates at most two supplied command lists. All arithmetic uses integer synthetic units. Position changes by commanded velocity; energy is one plus absolute velocity. Track is [0,100], maximum speed magnitude is three, and closed-segment guards include both obstacle endpoints.

The accepted receipt ledger gives exact replays no second effect, while a changed accepted ID faults before any mutation. It is intentionally run-local. Obstacle updates increment version and stale old proposals. Emergency stop latches before all same-tick work, including replay and success. A separately recorded host brake freezes terminal velocity without spending energy or moving position. This explicit simulator freeze has no physical safety meaning.

## Completed sequence

1. Finalized exact strict schemas, byte/depth/value bounds, integer dynamics, event ordering, replay identity, terminal labels and finite budgets in SPEC.md before implementation.
2. Implemented case-local stdlib package, original fixtures, JSON CLI, host dispatcher, observation/effect traces and a finite scripted planner.
3. Ran 43 meaningful tests. The independent trajectory oracle expects positions 3,6,7,7 and energy 4,4,2,1. Other tests cover crossing, rejection immutability, emergency precedence, replan/attempt bounds, parsing, regular-file authority and quiet closed stdout.
4. Ran the actual normal CLI and all fixture entry paths. `qualify.py` proves a copied case and an installed wheel run outside repository imports, with build-source removal before wheel execution. Each passes the same test suite and both entry points across six fixtures and help.
5. Updated code explanations and the README reading guide and exact fixture evidence. Independent review passed the source/copy/wheel checks, 22,725 dispatcher combinations and 3,000 seeded parsed-request scenarios. Status is demo-ready for the documented fixture contract.

## Tradeoffs and remaining work

A scripted fixture planner keeps the authority boundary inspectable without introducing model/network dependencies. Commands retain expected versions rather than silently refreshing them. Replanning replaces the old list and never resumes its tail. Every proposal attempt consumes a tick, including replay and rejection; environment and terminal freeze effects are separately traced. No automatic retry, in-run restart, persistent state or sibling runtime is present.

Independent review is complete; the parent owns catalogue integration and phased commits. There is no pending implementation decision or credential requirement. The documented evidence is fixture-only, not real-time, model, provider, hardware, deployment or production qualification.
