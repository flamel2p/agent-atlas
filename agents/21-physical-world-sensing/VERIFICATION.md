# Agent 21 qualification record

Verified on: 2026-10-23
Mode: fixture
Environment: macOS arm64 POSIX, uv 0.12.23, CPython 3.14.8

## Results

| Environment | Unit and CLI tests | Independent CLI invocations | Result |
| --- | --- | --- | --- |
| Checkout | 50 | 77 | Passed |
| Standalone copy with its own locked installation and no PYTHONPATH | 50 | 77 | Passed |
| Fresh environment installed from the built wheel | 50 | 77 | Passed |

The standalone copy excludes `.venv`, build artifacts, and caches. Its own installation was built offline. The wheel environment runs outside the checkout with PYTHONPATH removed, using the copied tests and checker. The imported module resolves to that environment's `site-packages`. All 11 installed Python and scenario files match source by SHA-256.

## Commands executed

From the checkout and standalone copied case:

```bash
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -q
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/verify_cli.py --package-dir src/physical_world_sensing
```

From the checkout, source-distribution and wheel builds passed with:

```bash
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv build --offline
```

The qualification workspace was `/tmp/agent21-qualification-7fscaoi7`. The following commands created the fresh wheel environment and ran its checks. Installation ran from the checkout. Tests ran from the qualification workspace with no source-package directory on the import path.

```bash
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv venv --offline --python 3.14 /tmp/agent21-qualification-7fscaoi7/wheel
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv pip install --offline --python /tmp/agent21-qualification-7fscaoi7/wheel/bin/python dist/physical_world_sensing-0.1.0-py3-none-any.whl
env -u PYTHONPATH /tmp/agent21-qualification-7fscaoi7/wheel/bin/python -m unittest discover -s /tmp/agent21-qualification-7fscaoi7/case/tests -q
env -u PYTHONPATH /tmp/agent21-qualification-7fscaoi7/wheel/bin/python /tmp/agent21-qualification-7fscaoi7/case/scripts/verify_cli.py --package-dir /tmp/agent21-qualification-7fscaoi7/wheel/lib/python3.14/site-packages/physical_world_sensing
```

The structure and whitespace checks run from the repository root:

```bash
python3 scripts/check_structure.py
git diff --check
```

## Behavioral evidence

The 50 tests cover latest-sample weighting, delayed observations, received-time causality, 300-second equality, stale and missing values, partial coverage, conflict equality/excess, per-channel independence, individual critical alerts, UTC occupancy hours, deadband endpoints, saturation, exact rational decisions, half-even display, and caller Decimal context isolation. They also cover schema/reference/identity limits, malformed input, filesystem replacement with a FIFO, descriptor cleanup during errors and interruption, package resource faults, unsupported non-filesystem resources, and output/exit behavior. Cancellation checks include injected interruption at the file boundary.

The independent checker imports no runtime internals. It sends authored documents through real CLI subprocesses and checks independently calculated results. It reconciles each command with the corresponding tick decision and reading provenance. Invalid-key and oversized documents are otherwise valid scenarios, so those probes distinguish actual boundary enforcement from unrelated schema rejection. Broken stdout and stderr pipes have no reader before process launch. Package faults modify temporary clones, including when qualifying the installed package.

## Independent review and fixes

Contract review resolved repeating-fraction display and latest-only critical-alert semantics before implementation closeout. The selected snapshot design passed source, causality, bounded-state, and authority review.

CLI-checker review strengthened duplicate-key and byte-limit probes, command-log reconciliation, symmetric CO2 conflict coverage, mixed/all-zero occupancy, and the 23.15 C decimal-flooring case. Its hand arithmetic and closed-pipe setup were confirmed.

Runtime review and parent probes found and corrected these defects:

- Packaged scenario acquisition bypassed regular-file and size controls. The original cloned-package symlink probe returned exit 0 instead of 2. Both input paths now use the same bounded, nonblocking reader, and all package-fault probes pass.
- Failed stderr delivery left a buffered flush pending and changed exit 2 to 120 at shutdown. Failed real stdout or stderr descriptors now redirect to the null device. Regression checks preserve failure exit 2 and interruption exit 130.
- Formatting inherited Decimal traps and exponent limits from a library caller. Repeating means raised Inexact, and a restricted caller exponent range caused Overflow. A fresh local Context now isolates display arithmetic. Regressions preserve the caller's settings and the report.

Final independent runtime review found no remaining actionable issue. The reviewer separately checked 160 exact-arithmetic assertions across 80 seeded scenarios, all five packaged CLI scenarios, SIGINT during blocked stdout delivery, and error delivery to a closed stderr reader.

## Evidence limits

All sensor values, occupancy events, thresholds, and command effects are synthetic. No mocked-provider, live-model, hardware, hosted-CI, deployment, energy-savings, calibration, or production qualification ran. Omitted commands do not imply a stopped actuator. No hardware adapter or model exists in this case.
