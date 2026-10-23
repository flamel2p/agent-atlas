# Embodied Intelligence Agent specification

Slug: 30-embodied-intelligence
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and evidence

An original, wholly synthetic one-dimensional cart demonstrates fixture motion proposals, current-state command guards, observations, and one bounded replan. The [source brief](../../agent-library-analysis/agents/30-embodied-intelligence.md) identifies the book pattern and listing defects. Its hardware and real-time claims are not this demo's evidence. The [local plan](PLAN.md) records implementation work. No hardware, ROS, network, model, physical safety, or deployment qualification is in scope.

## Strict request schema

The CLI accepts `--fixture NAME` or `--input PATH`, exclusively. The default is the packaged `normal` fixture. Output is one JSON report on stdout. There is no report-file option or runtime file write. Input paths must name regular files, opened without following a final symlink or blocking on a FIFO. Packaged fixtures are original trusted package resources selected by a fixed name table.

JSON input is UTF-8, at most 32,768 bytes, at most 12 nesting levels, and at most 2,048 values. Duplicate keys, unknown/missing fields, booleans in integer fields, floats, nonfinite numbers, invalid Unicode, and unsupported types are invalid. Every object has exactly the keys below. Bounds include endpoints.

| Object | Fields and bounds |
| --- | --- |
| Request | `state`, `goal` integer 0..100, `plans` one or two arrays of 0..20 commands each, `events` array of 0..20 events, `max_ticks` integer 1..20 |
| CartState | `position` integer 0..100, `velocity` integer -3..3, `battery` integer 0..100, `obstacles` sorted unique array of 0..20 integer points 0..100, `version` integer 0..1000, `emergency_stop` boolean |
| Command | `action_id` ASCII string matching `[A-Za-z0-9_-]{1,32}`, `expected_version` integer 0..2000, `velocity` integer -100..100 |
| Obstacle event | `tick` integer 0..19, `kind` equal to `obstacles`, `obstacles` as above |
| Emergency event | `tick` integer 0..19, `kind` equal to `emergency_stop` |

Events are sorted by tick, with at most one event of each kind at a tick. Initial position cannot be an obstacle. An initially latched emergency state must have velocity zero. A later obstacle event may mark the current position occupied, which makes every motion segment fail until revised. Events at ticks beyond termination remain unprocessed. No input grants restart authority. Input contains no persistent receipt ledger; each CLI invocation is a new synthetic world.

## Dynamics and state lifetime

All arithmetic is integer. The cart occupies a point on a closed track [0,100]. A command controls one abstract tick, with `position_after = position_before + command.velocity` and `velocity_after = command.velocity`. It spends `1 + abs(command.velocity)` battery units, including a zero-speed command. There is no acceleration, inertia, wall clock, sensor noise, coasting, or collision recovery. Velocity is the speed of the most recently simulated tick; time never advances without dispatch. An obstacle is a point. The whole closed segment from old to new position must avoid every obstacle, in both directions, including either endpoint.

Immutable typed records represent state, commands, events, receipts, and requests. One Dispatcher owns current state, an accepted-command receipt ledger, and an ordered effect trace for one run. FixturePlanner returns the next prevalidated plan as proposals only. Each accepted command atomically replaces state once, increments version by one, and appends exactly one receipt with before/after snapshots and energy cost. Rejected commands do not modify state, the accepted ledger, or the effect trace.

The host applies obstacle events before dispatch, replacing obstacles and incrementing version once even for an identical set. Emergency stop latches true and zeroes velocity with no displacement or energy cost, incrementing version once on its first activation. It precedes all other events at that tick, all success checks, replay checks, and pending commands. No event can clear it. Emergency activation suppresses same-tick obstacle events and terminates immediately.

Every terminal outcome has velocity zero. If necessary, a separate host `brake` effect sets velocity to zero and increments version once, with zero displacement and battery cost. It is an explicit simulator freeze, not a braking-distance or physical guarantee. A rejected command remains effect-free; a terminal brake is independently recorded. An already latched initial emergency state produces `halted` with no further effect.

## Dispatch authority and replay

Immediately before one mutation, the dispatcher checks its own current state. It rejects, in order, a latched emergency stop; a reused accepted action ID with changed command fields; an unseen action's stale expected version; speed magnitude above three; track-bound violation; any obstacle on the closed motion segment; and insufficient battery. The corresponding fixed reason is `emergency_stop`, `changed_action_id`, `stale_observation`, `excessive_speed`, `out_of_bounds`, `obstacle_crossing`, or `insufficient_battery`.

After the emergency gate, an exact replay of an accepted command returns its original receipt with `replayed: true` and no second effect. Its original version is intentionally allowed to be old because no motion is attempted. A changed replay is rejected even if otherwise safe. Rejected IDs are not reserved and may be corrected. Ledger lifetime ends with the run. The dispatcher cannot bypass emergency latching through a replay.

## Run flow and termination

1. Validate the complete request before simulation.
2. Check an initial emergency state. At each current tick process emergency events first, then obstacle events, then check whether position equals goal and velocity is zero.
3. Ask the fixture planner for a command from the active plan. A command attempt, including a rejection or replay, consumes one tick. Record its proposed command, observed pre-dispatch version, result, and receipt or fixed rejection reason.
4. An empty/exhausted plan or a rejected command requests a replacement plan. Exactly one replacement may be loaded, discarding the rest of the old plan. Replanning itself consumes no tick. If no replacement was supplied, halt with `fault` and the triggering reason. If the replacement has already been loaded, stop with `limit` and `replan_limit`. A rejected final command can still trigger replacement before the next tick-budget check.
5. At the next boundary process that tick's events and goal check, then stop with `limit` and `tick_limit` if `max_ticks` attempts have been consumed. Events have tick indices 0..19, so no tick-20 event exists. Success at the final allowed command boundary is permitted. Otherwise continue the finite plan.
6. Apply a separately traced terminal brake if velocity is nonzero and return once.

Reports have `schema_version: 1`, `mode: fixture`, terminal `outcome` of `complete`, `halted`, `fault`, or `limit`, fixed `reason`, `ticks`, `replans`, `goal`, `initial_state`, `final_state`, `attempts`, `effects`, `unprocessed_events`, and `limits` with max ticks and max replans. A successful report has reason `goal_reached`. Exhaustion uses `plan_exhausted`; emergency termination uses `emergency_stop`. `unprocessed_events` is a count, preserving explicit pending conditions. Attempt records contain tick, command, observed version, accepted, replayed, reason, and nullable receipt. Receipts contain action ID, complete command, before/after state, and energy. Effects contain kind (`command`, `obstacles`, `emergency_stop`, `brake`), before/after state, energy, and nullable action ID.

The CLI returns code 0 for complete/halted, 1 for fault/limit, 2 for invalid input/arguments/I/O. Invalid requests emit only `{"outcome":"invalid-input","error":"invalid_request"}` on stdout. Invalid command-line arguments use error `invalid_arguments`; unreadable/unsupported files use `input_unavailable`. No exception, supplied text, or path is echoed. Help and result writes explicitly flush within the broken-pipe guard. Closed stdout exits quietly with code 0 for buffered and unbuffered processes, including help. No input is read from stdin. SIGINT/KeyboardInterrupt returns a bounded `cancelled` JSON outcome and code 130 if output is writable; no further simulated command runs. This is a synchronous CLI, not a concurrent emergency input interface.

## Acceptance criteria

Independently calculated normal trajectory reaches position 7, rests, spends 11 battery, and records four command effects. Tests cover both crossing directions and endpoint obstacles, stale observations after world updates, speed, track, battery, replay and changed IDs, rejected-state immutability, event-first emergency ordering, no emergency restart, one replan, twenty attempts, terminal braking, full-input validation, strict schemas, bounded sanitized CLI errors, regular-file input, and buffered/unbuffered closed stdout. Actual CLI, case-only copy, and installed wheel must run outside repository imports. Tests and local simulations provide fixture evidence only. Independent substantive review passed; README records the fixture qualification evidence.

## Dependencies and limits

Python 3.14 and the standard library are the runtime. Hatchling 1.32.4 builds the package. There are no credentials, provider adapters, background workers, state files, real sensors, actuators, or external delivery. This original learning simulator does not establish book efficacy or physical correctness.
