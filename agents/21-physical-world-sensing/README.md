# Physical World Sensing Agent

Slug: 21-physical-world-sensing
Status: demo-ready
Runtime: Python 3.14 (uv CLI, POSIX)

## Purpose and contract

Replay synthetic building sensors into explained temperature, CO2, occupancy, alerts, and bounded simulated commands. [SPEC.md](SPEC.md) defines the contract. [PLAN.md](PLAN.md) records the design alternatives and build sequence. No model, runtime network, or physical actuation is used.

## Architecture and flow

Validate a complete bounded JSON scenario, consume readings at chronological ticks, select the latest fresh observation per sensor, and derive equal-weight estimates. Conflicting or missing readings hold the affected channel. Output records exact evidence and every simulated command. Run state ends with the process.

## Source reading guide

- [CLI](src/physical_world_sensing/cli.py) owns regular-file acquisition, scenario selection, output, and sanitized process failures. [Module entry point](src/physical_world_sensing/__main__.py) runs that CLI.
- [Domain records](src/physical_world_sensing/domain.py) define immutable configuration, observations, estimates, and decisions. Inspect observation time versus arrival time and the meaning of hold.
- [Schema boundary](src/physical_world_sensing/schema.py) validates the entire bounded document before replay, including identifiers, references, numerical limits, timestamps, and duplicate keys.
- [Replay](src/physical_world_sensing/replay.py) owns the latest-sample cache, exact arithmetic, freshness, conflict policy, events, and simulated channel decisions.
- [Independent CLI oracle](scripts/verify_cli.py) constructs its own inputs and checks public subprocess output against hand-calculated expectations without importing agent code.
- [Replay checks](tests/test_replay.py) verify numerical, temporal, event, and state-isolation behavior. [Schema checks](tests/test_schema.py) exercise contract limits. [CLI checks](tests/test_cli.py) cover descriptor cleanup, file replacement, resource corruption, output failures, and interruption handling. [Packaged scenarios](src/physical_world_sensing/scenarios/normal.json) are authored synthetic data.

## Setup and run

Use uv and CPython 3.14 on POSIX. No credentials or runtime dependencies are required. Run from this case directory.

```bash
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline physical-world-sensing --scenario normal
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline physical-world-sensing --scenario stale
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline physical-world-sensing --scenario conflict
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline physical-world-sensing --scenario late
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline physical-world-sensing --scenario boundary
```

An offline run requires an already cached Python interpreter and pinned build backend. When the cache is empty, omit `--offline` for initial setup.

The normal fixture reports office temperature 27 C and CO2 1200 ppm, with cooling at 100 percent and ventilation at 20 percent. The store reports 15 C, heating at 60 percent, and idle ventilation. These are desired simulated percentages. The two ticks produce eight commands with their exact source reading IDs.

The stale fixture demonstrates held controls. The conflict fixture retains critical individual-temperature alerts while holding thermal control. The late fixture prevents old arrivals from replacing newer measurements. The boundary fixture covers freshness, the neutral band, and UTC occupied hours.

To supply a custom scenario, use the [normal JSON](src/physical_world_sensing/scenarios/normal.json) as the schema example.

```bash
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m physical_world_sensing --input src/physical_world_sensing/scenarios/normal.json
```

Output is one JSON report. `quality` separates usable, unavailable, and conflicting estimates. `registered_count` and `eligible_count` disclose partial coverage. `decisions` explains each channel, and `command_log` records only usable-channel commands. A hold produces no command and cannot establish a physical shutdown.

Temperatures use Celsius, CO2 uses ppm, and occupancy is a binary observation aggregate. Each sensor contributes its latest received measurement if the measurement is at most 300 seconds old. Temperature and CO2 spreads above 4 C and 400 ppm suppress their respective channels. The 2 C-wide neutral band includes both endpoints. Display means round to six fractional places, while control comparisons remain exact. All thresholds are authored simulation policy.

Missing or conflicting evidence still completes with exit 0 and explicit quality. Invalid inputs and output failures exit 2, and interruption exits 130. Errors omit input paths and bytes. Both custom and packaged resources require bounded regular files. Direct ZIP import and other non-filesystem package resources are unsupported.

## Verification

Verified on: 2026-10-23
Verification command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -q && UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/verify_cli.py --package-dir src/physical_world_sensing`
Verification mode: fixture
Verification result: passed
Verified scope: 50 unit/CLI tests and 77 independent CLI invocations passed in each of the checkout, standalone case copy, and installed wheel on CPython 3.14.8. Coverage includes arithmetic, temporal eligibility, partial coverage, conflict holds, alerts, exact evidence, schema/resource limits, output failures, and cancellation handling. Independent review found no remaining runtime issue.

```bash
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -q
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/verify_cli.py --package-dir src/physical_world_sensing
```

The checker imports no agent code. It constructs independent input documents and checks hand-calculated control decisions, temporal provenance, partial coverage, conflict behavior, command-log consistency, and package acquisition failures in temporary cloned packages. Both stdout and stderr failures use pipes whose readers close before child launch.

Offline locked setup and both source-distribution and wheel builds passed. The installed module resolves inside the isolated wheel environment, and its 11 source/resource files match the checkout by SHA-256. The tests exercise the named console command as well as the module entry point. See [VERIFICATION.md](VERIFICATION.md) for the environment, review findings, and qualification commands.

No mocked provider, live-model, hardware, hosted-CI, deployment, or production validation ran. This case has no model or runtime network.

## Limitations and references

The [retained source brief](../../agent-library-analysis/agents/21-physical-world-sensing.md) cites Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 11. Sensor fusion, thresholds, and a 2 C-wide neutral band are selected demo policy. Hysteresis, calibration, actuator delivery, and real-world safety remain outside the contract.
