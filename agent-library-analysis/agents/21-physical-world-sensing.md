# 21 - Physical World Sensing agents

- **Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 11, "Multi-Modal Perception Agents."
- **Reference ID:** 21 from the official publisher repository inventory; exact PDF heading "Physical World Sensing agents." The implementation is named `SmartBuildingAgent`.
- **Page convention:** printed page / 1-based physical PDF page.
- **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose and contract

**Explicitly stated:** Fuse noisy, asynchronous environmental readings into a digital-twin-like state, detect relevant events, and derive control commands. Smart-building monitoring balances comfort and energy use across zones. Inputs include sensor readings, zone type, targets, and occupied hours; outputs are zone state, alerts, and actuator commands (pp. 320–326 / PDF 351–357).

**Inference:** Intended users are facility-system developers and operators. Success is stable, explainable state-to-command behavior rather than merely logging readings. **Not specified:** Measured energy savings, safety assurance level, calibration targets, real actuator protocol, or acceptable sensing/control latency. No book-reported deployment claim is independent validation.

## Architecture and documented flow

`ZoneConfig` holds static constraints; `ZoneState` holds dynamic temperature, CO2, occupancy probability, comfort, and anomalies. Named components are sensor buffers/fusion, event processor, control manager, and reporting. Figure 11.3 shows multiple zones feeding a fusion engine and parallel event/control/reporting paths (pp. 321–322 / PDF 352–353). It does not itself show the static/dynamic separation claimed in its caption; that separation is supported by the dataclasses.

1. Buffer readings per zone in a bounded collection.
2. Select readings newer than a five-minute cutoff.
3. Average temperature readings into current state; missing temperatures remain unavailable.
4. Retrieve zone configuration and evaluate declarative `EventPattern` predicates, including critical temperature and unexpected occupancy outside occupied hours.
5. Compute heating/cooling proportional to distance from the target midpoint, bounded at 100; separately compute ventilation when CO2 exceeds its configured maximum.
6. Return state, alerts, and commands. A subsequent observation would start another sense-model-plan-act cycle; actual hardware actuation and scheduling are not implemented (pp. 322–326 / PDF 353–357).

State/history consists of per-zone buffers and the current estimate. NumPy is in chapter requirements, while this example uses dataclasses, dates, enums, and bounded collections. No LLM is necessary for the displayed deterministic controller.

## Implementation evidence and constraints

The code illustrates configuration, state, event patterns, proportional control, and temperature averaging. It leaves `ActuatorCommand`, `EventProcessor`, reading types, zone registration, and some imports undeclared in these excerpts. Fusion does not populate CO2 or occupancy despite describing heterogeneous sensing (pp. 323–326 / PDF 354–357).

**Verified discrepancy:** Prose and comment say a two-degree deadband, while the printed condition is `abs(error) > 1.0`. This must be resolved explicitly rather than copied as a stable contract (p. 324 / PDF 355, visually checked). A deadband alone is not a fully specified stateful hysteresis controller. Sensor dropouts, model drift, occupancy errors, and operator overrides are discussed; logging explanations and recalibration are production suggestions, not complete recovery mechanisms (p. 326 / PDF 357).

## Proposed minimal learning demo - unexecuted

Build a synthetic building simulator with two zones, timestamped readings, explicit missing/stale data, deterministic events, and a command log. Simulated commands never reach hardware. Make the deadband value visible and use an injected clock.

- **Normal-path acceptance:** An above-target fixture produces the expected bounded simulated cooling command and an explanation showing the fused value and target.
- **Failure/limit acceptance:** When every temperature reading is stale, output unavailable temperature and no temperature command; emit a diagnostic instead of inventing a state.

**Missing decisions:** Units, real hysteresis/cycle timing, fusion weights/outlier rejection, timestamp trust, stale-data policy, sensor health, overrides, safe command limits, actuation acknowledgments, and audit persistence.
