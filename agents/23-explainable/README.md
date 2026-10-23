# Explainable agent

Slug: 23-explainable
Status: demo-ready
Runtime: Python 3.14, standard-library runtime

## Purpose and contract

Classify a synthetic task as `urgent`, `high`, or `routine`, then explain the actual evidence and rules for users, engineers, and auditors. All views derive from one frozen trace. The host releases a priority only after every view passes its claim and reference checks. Missing evidence, inconsistent traces, and renderer failures require review.

The [specification](SPEC.md) defines thresholds, schema, failure behavior, authority, and acceptance criteria. This demo has no model, external service, calibration, medical use, or production qualification.

## Architecture and flow

The CLI parses bounded JSON and validates a typed request. The rule core records evidence, all policy evaluations, and the final selection. Three deterministic renderers consume that same trace. A release gate checks the views before returning a decision. The trace lives for one invocation and leaves the process only on stdout. The CLI reads explicit inputs and has no write or network capabilities.

## Source reading guide

- [CLI entry point](src/explainable/cli.py) owns strict JSON, input limits, file authority, errors, and process exit codes.
- [Immutable contracts](src/explainable/contracts.py) define event ownership, claims, and release outcomes.
- [Decision policy](src/explainable/decision.py) owns evidence validation, first-match rule selection, trace integrity, and replay.
- [Explanation gate](src/explainable/explanation.py) renders all audiences and withholds release when any view fails validation.
- [Behavior checks](tests/test_explainable.py) cover rules, evidence, replay, tampering, and renderer failures.
- [CLI checks](scripts/verify_cli.py) exercise the real process and malformed-input boundaries.
- [Isolation checks](scripts/verify_isolation.py) rerun behavior checks in a case-only copy and a fresh installed-wheel environment.

## Setup and run

Run these commands from `agents/23-explainable/`. No credentials or environment file is required.

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --offline
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline explainable classify fixtures/urgent.json
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline explainable classify fixtures/missing-evidence.json
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline python -m unittest discover -s tests -v
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline python scripts/verify_cli.py
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline python scripts/verify_isolation.py
```

The urgent fixture must exit 0 with priority `urgent`, seven trace events, and three complete audience views. The missing-evidence fixture must exit 2 with a null decision and incomplete explanations. Extract a result's `trace` value into a JSON file to use `explainable explain TRACE.json`. The CLI never writes that file.

## Verification

Verified on: 2026-10-23
Verification command: `.venv/bin/python scripts/verify_isolation.py`
Verification mode: fixture
Verification result: passed
Verified scope: Case-only copy and fresh installed wheel each passed 33 unit tests and 30 CLI checks, including explicit imported-package location checks. Python 3.14.8 on macOS arm64. No repository-root or sibling runtime files were copied.

Additional local checks passed on the same date and interpreter.

| Command from this directory | Actual result |
| --- | --- |
| `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv lock --offline` | Resolved the local package with no runtime dependencies |
| `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --offline` | Built and installed this case |
| `.venv/bin/python -m unittest discover -s tests` | 33 test methods passed, including 72 threshold scenarios, missing evidence, rehashed inconsistent traces, renderer faults, and cancellation |
| `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline python scripts/verify_cli.py` | 29 real process checks passed for fixtures, replay, malformed JSON, size and depth limits, unsafe file types, and stable failures |

The isolation command creates a temporary case-only copy, runs its documented tests and CLI checks, builds its wheel offline, installs that wheel into a fresh environment, and repeats the tests outside the source tree. Its CLI checks add one package-location assertion per environment, for 30 checks each. Temporary environments and wheels are removed after the run.

Independent review and fix verification passed. Status is `demo-ready` for this fixture scope. Root structural validation belongs to that integration step. No live model, mocked provider, hosted CI, deployment, or production check has run for this case.

## Limitations and references

The policy and fixtures are synthetic. Evidence has no external authenticity check. The SHA-256 digest detects corruption, and policy replay detects inconsistent events. A coherent rewrite of evidence and its derived trace can pass. Frozen data prevents application-level mutation during normal execution, not a hostile process or signed-storage attack.

Templates give exact claim fidelity for this narrow policy. They do not measure explanation usefulness, fairness, causal attribution, calibration, or agreement with reality. Audiences have different wording, not access controls. No trace retention or redaction service exists because the schema excludes free text and accepts synthetic data only.

Inspired by Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 12, printed pp. 346-358, physical PDF pp. 377-389. The [source brief](../../agent-library-analysis/agents/23-explainable.md) records the source gaps. Implementation is original under the repository's [MIT license](LICENSE).

Independent review found that help output bypassed the broken-pipe handler. A real-process regression reproduced exit 120 and an unbuffered traceback before the fix. Both output paths now use the controlled writer. The parent reran 33 tests, 29 local CLI checks, and the copy/wheel checks after the fix. Independent fix review passed.
