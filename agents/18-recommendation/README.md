# Recommendation Agent

Slug: 18-recommendation
Status: demo-ready
Runtime: Python 3.14 (uv CLI, POSIX)

## Purpose and contract

Recommend synthetic learning exercises from explicit weighted interests and hard eligibility constraints. Every result explains topic contributions, rejected items, and terminal outcome. This is an independently designed content-based demo for reference 18, whose retained book analysis has no developed standalone implementation. See [SPEC.md](SPEC.md), [PLAN.md](PLAN.md), and [source evidence](SOURCES.md).

## Architecture and flow

The host validates a packaged catalogue and request, applies all constraints before ranking, computes integer topic overlap, orders results deterministically, and emits JSON. Private immutable records belong to one call. No profile, history, clock, or random state survives a call.

Weighted topic overlap sums the request weights for matching exercise tags. The host rejects excluded, over-duration, over-difficulty, and missing-skill items before scoring. Every applicable rejection reason remains visible. Positive scores sort by descending score, ascending duration, then ascending ID. The limit applies after ordering.

Empty interests produce a labeled baseline ordered by duration and ID with score zero. Stated interests with no eligible overlap produce no recommendations. Constraints never relax, and unrelated items never pad personalized results. Prerequisites are explicit skill IDs asserted by the caller, independent of interest topics.

## Source reading guide

Read these files in order.

1. [Public API](src/recommendation/__init__.py) exposes `recommend` and sanitized `InputError`.
2. [Domain engine](src/recommendation/domain.py) defines the private records, complete schema validation, all hard gates, terminal outcomes, scoring, and report construction.
3. [Documents](src/recommendation/documents.py) enforces UTF-8 JSON, document and nesting limits, duplicate-key rejection, cycle detection, and regular-file authority.
4. [CLI](src/recommendation/cli.py) selects fixed resources or one request file, sanitizes failures, and detects buffered output failures. [Module entry point](src/recommendation/__main__.py) invokes the same CLI.
5. [Original synthetic catalogue](src/recommendation/data/catalogue.json) declares topics, skills, and 16 exercises. [Normal request](src/recommendation/data/scenarios/normal.json) shows the six required input fields. Its sibling scenario files cover cold start, no match, constrained eligibility, and no eligible items.
6. [Domain checks](tests/test_recommendation.py) verify hand scores, gates, ordering, state isolation, and direct Python validation. [CLI checks](tests/test_cli.py) exercise actual subprocesses, packaged resources, input files, special files, sanitized errors, and closed pipes.
7. [Independent CLI verifier](scripts/verify_cli.py) derives expected topic vectors, eligibility, complete reports, and numeric types directly from fixture JSON. It also checks boundary and output-failure cases against a selectable installed command without importing runtime policy helpers.

The [behavior contract](SPEC.md) owns input bounds, tool authority, status precedence, and count semantics. [Source evidence](SOURCES.md) separates verified general guidance from independently selected policies.

## Setup and run

Requires uv, Python 3.14, and POSIX file flags `O_NOFOLLOW`, `O_NONBLOCK`, and `O_CLOEXEC`. Local checks ran on macOS with CPython 3.14.8. Windows is unqualified. The runtime has no third-party dependency, network call, environment variable, or credential requirement. Hatchling 1.32.4 is the pinned build dependency.

From this case directory, run the following commands. The cache override uses the repository's existing restricted-development cache. Remove `--offline` for an initial download when your cache is empty.

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline recommendation
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline recommendation --scenario cold-start
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline recommendation --scenario no-match
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline recommendation --scenario constrained
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline recommendation --scenario no-eligible
```

The default is `normal`. Normal recommendations are `unit-tests` with score 5, `safe-json` with score 5, and `read-files` with score 3. Cold start returns `cli-help`, `read-files`, and `write-guide` with score zero. The constrained scenario returns only `parse-records` with score 2. No-match and no-eligible scenarios return empty recommendation lists with distinct terminal statuses.

For a custom request, supply all six fields from the [normal request](src/recommendation/data/scenarios/normal.json) in one UTF-8 JSON regular file, then invoke `recommendation --request /path/to/request.json`. `--request` and `--scenario` are mutually exclusive. The CLI accepts no custom catalogue or output path. Shell redirection remains the caller's choice. Final-component symlinks, directories, and special files are rejected.

The direct Python API accepts a request and synthetic catalogue as plain JSON-shaped objects.

```python
from recommendation import InputError, recommend

report = recommend(request, catalogue)
```

`InputError` is a sanitized `ValueError` subclass. Each argument is bounded to 256 KiB of compact UTF-8 JSON and at most 32 nested containers. Duplicate list members, unknown fields or references, booleans in integer positions, non-finite values, custom Python objects, and cyclic containers are invalid. Inputs and returned objects share no retained state.

Reports go to stdout. Valid empty outcomes exit 0. Invalid inputs and arguments emit a sanitized JSON error on stderr with empty stdout and exit 2. Fixed-resource or output failures exit 1. This includes stdout closed before Python starts. Closed stderr cannot receive an error, but preserves the selected nonzero exit. Keyboard interruption exits 130. `--help` prints usage and loads no catalogue.

## Verification

Run the case checks from this directory.

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/verify_cli.py
```

Verified on: 2026-10-23
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v
Verification mode: fixture
Verification result: passed
Verified scope: 36 tests covering ranking, every hard constraint, deterministic ties, cold start, no match, input/API bounds, resource authority, state isolation, and buffered/unbuffered/startup-descriptor output failures.

All final evidence below ran on 2026-10-23, macOS with CPython 3.14.8 and fixture data. The original builder's 34 tests passed before review; final qualification includes two additional startup-descriptor regressions.

| Environment | Actual check | Result |
| --- | --- | --- |
| Working checkout | Locked offline setup, unittest command, and independent CLI verifier above | 36 tests and 87 verifier subprocesses passed |
| Standalone case copy at `/tmp/agent18-isolation/agents/18-recommendation` | Copied only this case without environment/build artifacts, ran locked offline setup and the same two checks | 36 tests and 87 verifier subprocesses passed without repository-root or sibling resources |
| Installed wheel | Installed into `artifacts/wheel-env`; ran tests with isolated Python from `artifacts/wheel-cwd` and verifier against the wheel console command | 36 tests and 87 verifier subprocesses passed; imports resolved to wheel site-packages |
| Packaging | `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv build --offline` | Source distribution and wheel built; archive inspection confirmed runtime/data bytes, source checks/docs, and preserved MIT license |
| Repository | `python3 scripts/check_structure.py` and `git diff --check` from root | Passed |
| Independent substantive review | Read-only contract/code/explanation review plus the final 36-test suite | No remaining actionable findings |

The verifier performed 261 CLI invocations across the three environments. It compares full reports with independent feature vectors and type-aware canonical JSON. Its malformed duplicate-key and oversized cases retain otherwise valid requests, with an exact-size positive control. Timeout handling kills and reaps closed-pipe child processes.

The wheel qualification used these commands from this case, after building. The unittest command used the absolute case and interpreter paths from an `artifacts/wheel-cwd` working directory.

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv venv --python 3.14 artifacts/wheel-env
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv pip install --offline --no-deps --python artifacts/wheel-env/bin/python dist/agent_atlas_recommendation-0.1.0-py3-none-any.whl
artifacts/wheel-env/bin/python scripts/verify_cli.py --command artifacts/wheel-env/bin/recommendation
```

After the output fix, the wheel was rebuilt and reinstalled with `--reinstall` before final checks. Installed `cli.py` bytes matched the repaired source. Isolated wheel unittest execution used `artifacts/wheel-env/bin/python -I -m unittest discover -s /absolute/case/tests -v` from outside the source directory.

Review found a legitimate startup state where CPython sets a closed standard stream to `None`. The focused command `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -p test_cli.py -k descriptor_closed -v` failed before the fix with `Traceback unexpectedly found` for stdout and `1 != 2` for the stderr exit code. It then passed both regression methods after guards at the CLI boundary. The final suite and verifier passed against the repaired code in all three environments.

`uv lock --offline`, locked offline sync, the default console command, and all five explicit scenarios also ran successfully. This readiness record establishes synthetic fixture behavior and local POSIX packaging only. No live-model, hosted-CI, deployment, Windows, or real learner-quality evidence is claimed.

## Limitations and references

This deterministic demo has no learned model, runtime network, feedback training, collaborative filtering, persistent learner profile, or external effects. Scores express the selected weighted overlap rule. They are not confidence or predicted learning benefit. Synthetic checks establish mechanical behavior only. See [SOURCES.md](SOURCES.md) for source attribution and the book source gap.
