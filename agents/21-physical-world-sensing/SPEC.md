# Physical World Sensing Agent specification

Slug: 21-physical-world-sensing
Status: demo-ready
Runtime: Python 3.14 (uv CLI, POSIX)

## Problem and scope

Facility developers need to inspect how asynchronous sensor evidence becomes a zone estimate and a bounded control decision. This deterministic demo replays synthetic temperature, CO2, and binary occupancy observations for configured zones. It returns provenance, quality diagnostics, alerts, and simulated commands. It has no model, network, real sensor, physical actuator, or persistent state.

## Evidence and decisions

Source facts come from the [retained brief](../../agent-library-analysis/agents/21-physical-world-sensing.md), Chapter 11, printed pp.320-326, physical PDF pp.351-357. The example uses bounded buffers, a five-minute window, temperature averaging, event patterns, and proportional control. CO2 and occupancy fusion are incomplete in the excerpts. The prose describes a two-degree deadband while the condition is `abs(error) > 1.0`, printed p.324, PDF p.355.

Selected decisions are independent implementation choices. Use a 300-second inclusive freshness window and the latest observed sample per registered sensor. Use an explicit symmetric neutral band of plus or minus 1 C around the target midpoint. This is a 2 C-wide deadband, without hysteresis, dwell times, or calibration guarantees. Use equal sensor weights and conflict rejection. Permit partial coverage with diagnostics. All thresholds are synthetic demonstration policy, not building or health standards.

## Inputs and outputs

The CLI `physical-world-sensing` accepts exactly one of `--scenario NAME` or `--input PATH`. With neither, run packaged `normal`. Packaged scenarios are `normal`, `stale`, `conflict`, `late`, and `boundary`. Input is a UTF-8 JSON regular file, at most 262144 bytes. Reject symlinks, directories, FIFOs, devices, and acquisition failures without blocking on special files. Packaged scenarios pass the same schema validation. No implicit network or fallback input exists.

The top-level object has exactly `zones`, `sensors`, `readings`, and `ticks`. Reject unknown or missing fields, duplicate object keys, nonfinite numbers, booleans as numbers, malformed JSON, and JSON nesting deeper than 16 containers. Identifiers match `[a-z][a-z0-9_-]{0,31}`. Limits are 1-8 zones, 1-64 sensors, 0-512 readings, and 1-64 strictly increasing ticks. The span between first and last tick is at most 86400 seconds. Timestamps are exact UTC seconds `YYYY-MM-DDTHH:MM:SSZ` within years 2000-2100.

Each zone has exactly `id`, `target_min_c`, `target_max_c`, `co2_limit_ppm`, `occupied_start_hour`, and `occupied_end_hour`. Temperature targets are numbers within 10-35 C with min < max. CO2 limits are 400-2000 ppm. Schedule hours are integers with 0 <= start < end <= 24 and use UTC. Start is inclusive, end exclusive. Overnight schedules are unsupported.

Each sensor has exactly `id`, `zone_id`, and `kind`. Kinds are `temperature`, `co2`, and `occupancy`. Bindings reference a configured zone. Each zone has at least one sensor of each kind. Each reading has exactly `id`, `sensor_id`, `observed_at`, `received_at`, and `value`. IDs are unique within their collections. Repeated `(sensor_id, observed_at)` pairs are rejected. Observed time must be <= received time. Temperature values are -40 to 85 C, CO2 values 250-10000 ppm, occupancy values numeric 0 or 1. Each number has at most 12 significant digits and at most 3 fractional digits. Full validation precedes any replay or output.

Output is one JSON object with `mode: simulation`, `status: completed`, a `ticks` array, and a `command_log`. Each tick records its evaluation time and zones in stable ID order. Each zone records all three metric estimates with quality `ok`, `unavailable`, or `conflict`, registered/eligible sensor counts, selected reading provenance, diagnostics, alerts, and channel decisions. Provenance includes reading ID, sensor ID, observed time, received time, value, and age seconds. Missing estimates are null, never fabricated zero. Numeric estimate values are decimal strings rounded to at most six fractional places with ROUND_HALF_EVEN and trailing zeros removed. Means and all policy comparisons use exact rational arithmetic before display rounding. Reading values preserve their exact finite decimal value. Command percentages are integers. Output contains no raw input path or input bytes.

## Architecture and state

Immutable domain records represent scenario, zones, sensor bindings, readings, estimates, and simulated decisions. Parsing is the trust boundary. One replay invocation owns a bounded latest-reading cache and command log. Nothing survives exit. The public workflow is parse a scenario, run replay, render JSON. The CLI owns file acquisition, sanitized failures, and process exit behavior.

For each tick, consume readings with received_at <= tick in deterministic received-time/ID order. A sensor's cache keeps the greatest observed_at among received readings, so delayed old observations cannot replace newer measurements. Only cached readings with `0 <= tick - observed_at <= 300 seconds` contribute. Future received readings cannot affect earlier ticks. Readings after the last tick remain unused. File order does not change results.

Each temperature and CO2 estimate is the equal-weight arithmetic mean of the latest eligible readings per sensor. If the eligible temperature spread exceeds 4 C, or CO2 spread exceeds 400 ppm, quality is conflict and the estimate is null. Equality remains usable. Occupancy is 1 if any eligible occupancy sensor reports 1, otherwise 0. It is an observed binary aggregate, not a probability. No eligible reading yields unavailable. Missing or stale configured sensors produce diagnostics even when partial evidence yields an estimate.

## Tools and authority

Controls are pure simulation output. No provider, plugin, tool dispatcher, executable model proposal, or hardware adapter exists. Thermal and ventilation decisions are independent. An unavailable or conflicting metric holds that channel and emits no command for it. Hold means no simulated command, not physical shutdown or safety assurance.

For usable temperature T, midpoint M=(min+max)/2, and error E=T-M, use idle at abs(E)<=1 C. Otherwise cool when E>1 and heat when E< -1. Percentage is min(100, floor(abs(E)*20)). Idle produces a zero-percent simulated thermal command. For usable CO2 C, idle at C<=limit. Otherwise ventilate with min(100, floor((C-limit)/10)). A positive excess that rounds to zero produces a zero-percent ventilation command; the mode still records ventilate. All commands carry tick, zone ID, channel, mode, percentage, simulation marker, reason, and source reading IDs. Emit one command per usable channel at each tick, including repeated decisions. This is a desired command log without delivery or acknowledgment semantics.

Alerts include critical_temperature for any selected latest fresh temperature reading <=5 C or >=35 C, even when fusion conflicts. Superseded samples do not trigger current alerts; this snapshot controller is not an incident-history detector. Include high_co2 only when the CO2 estimate is usable and exceeds its limit. Include unexpected_occupancy when the observed occupancy aggregate is 1 outside the configured schedule. Alerts carry their triggering reading IDs. Diagnostic and alert codes are stable machine values. Diagnostic reasons explain missing, stale, and conflicting evidence without asserting calibrated sensor health.

## Execution and termination

1. Acquire bounded input and validate the full document.
2. Replay at most 64 ticks over at most 512 readings and 64 sensor cache entries.
3. Derive estimates, diagnostics, events, and independent channel decisions.
4. Emit a single complete JSON report to stdout and exit 0. Degraded evidence still completes with explicit quality.

There are no retries, sleep, background tasks, or continuous polling. Invalid input, inaccessible resources, and output failures exit 2 with a short generic error on stderr and no traceback. Keyboard interruption exits 130. Output may be truncated if stdout fails during delivery, and a failed exit never establishes a complete report. File descriptors close on failures and cancellation. Help output observes the same output-failure behavior.

## Acceptance criteria

All criteria require fixture evidence.

- A two-zone normal replay produces independently recomputed equal-weight means, cooling or heating toward the midpoint, bounded ventilation, and exact selected reading IDs.
- All-stale temperature yields unavailable and no thermal command. Usable CO2 remains independently controllable.
- Multiple readings from one sensor never overweight it. A delayed old reading cannot replace a newer received reading. Reordering input does not alter output.
- Samples exactly 300 seconds old qualify. Samples 301 seconds old and unreceived future data do not. At exactly plus or minus 1 C, thermal control is idle.
- Conflicting fresh values suppress only the affected channel. A critical individual reading remains alertable during conflict.
- UTC schedule boundaries and occupancy events are deterministic. All emitted commands remain 0-100 percent and explicitly simulated.
- Invalid schemas, duplicate identities/keys, nonfinite data, unknown bindings, wrong timestamps, limits, and unsafe file types fail cleanly without successful output.
- The documented CLI, standalone copied case, and installed wheel work without sibling files or credentials. Independent review resolves substantive findings.

## Dependencies and open decisions

Python 3.14 and a case-local uv project use no runtime dependencies. Packaging uses the repository's existing pinned Hatchling baseline. No new third-party API or version-sensitive runtime feature is selected. Real hardware integration, hysteresis, actuator feedback, calibration, auth, durable audit, and deployment require separately scoped decisions. No material decision remains open for this demo.
