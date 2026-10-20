# Tool-Using Agent

Slug: 07-tool-using
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

A CLI that summarizes synthetic campaign spend or revenue by channel and optionally creates a bar chart. The selected [behavior contract](SPEC.md) demonstrates how model-proposed calls pass through a validated execution boundary.

Implemented and validated on 16 October 2026. Replay, mocked-provider checks, and both selected live-provider examples passed.

Completed the [Agent 07 plan](SPEC.md#agent-07-completion-plan) on 20 October 2026 by aligning the directory name and adding reviewer explanations. The `tool-using` command and existing behavior remain unchanged. Fresh local verification is recorded below; the live-provider evidence remains dated 16 October.

| Area | Selected contract |
| --- | --- |
| Runtime | CPython 3.14, case-local uv project and lockfile. |
| Scenario | One bundled synthetic CSV; sum spend or revenue by channel; RM display. |
| Backend | OpenAI Responses API with `gpt-6-luna` via the official Python SDK. |
| Default mode | Named deterministic replay examples; live mode is explicit and requires `OPENAI_API_KEY`. |
| Tools | `inspect_dataset`, `sum_by_channel`, and `render_bar_chart`. |
| Effects | Read the bundled fixture; write only a fresh case-local run directory; live model transport is the only network integration. |
| Limits | 6 backend responses, 5 admitted tool attempts, 30 seconds per provider request, 120 seconds total execution, no retries. |

## Architecture and flow

CLI → validated input and fixture snapshot → backend proposal → dispatcher validation → tool execution → validated result → next decision → host-generated report.

Replay and live use the same dispatcher. A failed tool stops the run. The model cannot supply paths, executable code, chart data, or external operations. Authoritative totals and artifact references come from validated tool results. Successful execution does not prove that the model selected the metric intended by the natural-language request; live task alignment is checked separately.

The supplied [source brief](../../agent-library-analysis/agents/07-tool-using.md) records Chapter 7, printed pp.174-186 / physical PDF pp.205-217, and distinguishes the conceptual pattern from the rule-based book sample.

## Source reading guide

Read the [behavior contract](SPEC.md) alongside these modules:

| Source | Reviewer focus |
| --- | --- |
| [cli.py](src/tool_using/cli.py) | Entry point, mutually exclusive mode flags, credential loading, structured reports, and exit codes. |
| [contracts.py](src/tool_using/contracts.py) | Run configuration, untrusted tool proposals, backend decisions, execution limits, and sanitized terminal failures. |
| [backends.py](src/tool_using/backends.py) | Deterministic replay and live Responses history, original call-ID correlation, whole-response validation, and the boundary between proposals and execution. |
| [tools.py](src/tool_using/tools.py) | Immutable fixture snapshot, strict argument/result schemas, run-local handles, terminal dispatcher state, exact totals, and staged chart rendering. |
| [controller.py](src/tool_using/controller.py) | Trusted worker lifecycle, hard request/run deadlines, trace ownership, completion checks, and artifact publication/rollback. |
| [tests/](tests/) | Observable acceptance checks for permitted results, malformed proposals, state isolation, provider responses, deadlines, cancellation, and publication failures. |

## Setup and run

Prerequisite: [uv](https://docs.astral.sh/uv/getting-started/installation/). Run from this case directory:

```sh
cd agents/07-tool-using
uv sync --locked
uv run --locked tool-using --mode replay --example revenue-by-channel-bar
uv run --locked tool-using --mode replay --example spend-by-channel-table
uv run --locked tool-using --mode replay --example invalid-tool-call
```

The first two examples exit 0. The intentional invalid-tool example exits 2 with `invalid_tool_call` and no chart. Default invocation `uv run --locked tool-using` runs the revenue/bar replay. After installation, add `--offline` to `uv run` to prevent dependency-network access; the replay application itself makes no network calls.

Expected totals, in alphabetical channel order:

| Metric | Email | Search | Social |
| --- | --- | --- | --- |
| Revenue | RM 300.00 | RM 750.00 | RM 400.00 |
| Spend | RM 50.00 | RM 250.00 | RM 200.00 |

Each run prints its report as JSON and writes `artifacts/<run-id>/report.json` and `trace.jsonl`. Successful bar runs also publish `chart.png` at 960×540. Failed/cancelled runs have null summary/chart fields and no published chart. Artifacts and plotting caches are ignored by Git. A pre-run input/credential error produces JSON without creating a run directory.

Python is pinned to 3.14.8 in [.python-version](.python-version). Direct dependencies are OpenAI 3.31.0, Pydantic 2.14.1, and Matplotlib 3.11.2; development uses pytest 9.1.1. [pyproject.toml](pyproject.toml) and [uv.lock](uv.lock) own the exact environment. No sibling case or root runtime installation is required.

The supported run path is this source checkout with uv's editable project install. The application locates the case relative to `src/tool_using/`, and the wheel configuration includes only that package. A standalone wheel installation does not include the required fixture or preserve the case layout.

### Live mode

Copy `.env.example` to `.env` if you do not already have one, then set `OPENAI_API_KEY` locally. Do not paste the key into chat or commit it. The application reads the process environment; `uv --env-file` loads the case-local file explicitly:

```sh
uv run --locked --env-file .env tool-using --mode live --task "Compare total revenue by channel" --format bar
uv run --locked --env-file .env tool-using --mode live --task "Compare total spend by channel" --format table
```

An exported `OPENAI_API_KEY` also works without `--env-file`. Live calls use the selected model only, with no retries or fallback. Reports include provider response count, reported model, and aggregate token usage when returned; traces retain sanitized request IDs. Free-form model text, raw errors, credentials, and task text are not logged. Unsupported task meaning relies on the model declining it; `completed` does not establish task alignment.

## Verification

### Agent 07 completion checks

Verified on: 2026-10-20
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline pytest -q
Verification mode: fixture
Verification result: passed
Verified scope: all 133 existing fixture and mocked-provider tests passed from `agents/07-tool-using/`, including exact totals, strict calls/results, state isolation, deadlines, cancellation, and publication rollback. No live model calls were made.

Environment: macOS, CPython 3.14.8, uv 0.12.23. The renamed case received a fresh environment through `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked`. The first offline installation attempt lacked cached dependencies, and the restricted-network attempt failed DNS resolution. Installation then passed with network access and the unchanged lockfile.

| Check | Actual result on 20 October |
| --- | --- |
| Executable preservation | All seven Python modules have identical executable ASTs after removing docstrings. All eight Pydantic schemas, both tool-schema sets, and provider instructions match the pre-rename version. Tests, fixture, manifest, and lockfile are byte-for-byte unchanged. |
| Default CLI | `uv run --locked --offline tool-using` exited 0 with revenue totals of 30000, 75000, and 40000 sen. The 960×540 PNG was inspected visually; its summary reference and report file matched the emitted result. |
| Table CLI | `uv run --locked --offline tool-using --mode replay --example spend-by-channel-table` exited 0 with totals of 5000, 25000, and 20000 sen and no chart. |
| Rejection CLI | `uv run --locked --offline tool-using --mode replay --example invalid-tool-call` exited 2 with `invalid_tool_call`, null summary/chart, and no published chart. |
| Independent case checkout | Copied only case source, configuration, fixtures, and tests to a temporary directory. Excluded credentials, environments, caches, and artifacts. With `OPENAI_API_KEY` and `PYTHONPATH` unset, `uv sync --locked --offline` and all three named replay commands passed with their expected exits. Imports resolved inside the copy. The offline installation used the populated dependency cache. |
| Independent review | No actionable findings. The reviewer separately compared executable ASTs, generated schemas, provider instructions, unchanged data/tests/dependencies, active paths, and explanation accuracy. The reviewer relied on the recorded parent runs for runtime evidence. |

The directory move retained existing ignored files and local artifacts. The case-local `.gitignore` also excludes credentials and generated files when the directory is copied into its own repository; those rules were checked in the isolated copy. Historical run IDs below still refer to their preserved local artifacts.

The repository structure check, active Markdown links and anchors, and whitespace checks passed. Live-provider calls were not repeated. Hosted CI, deployment, and production reliability remain unverified.

### Live-provider acceptance

Verified on: 2026-10-16
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline --env-file .env tool-using --mode live --task "Compare total revenue by channel" --format bar
Verification mode: live-model
Verification result: passed
Verified scope: real gpt-6-luna Responses calls; completed revenue summary with exact totals, matching dataset/chart provenance, valid 960×540 PNG, and provider token usage.

Verified on: 2026-10-16
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline --env-file .env tool-using --mode live --task "Compare total spend by channel" --format table
Verification mode: live-model
Verification result: passed
Verified scope: real gpt-6-luna Responses calls; completed spend summary with exact totals, matching dataset provenance, no chart, and provider token usage.

Both commands exited 0 and reported model `gpt-6-luna`. Here `--offline` applies only to uv dependency resolution; the application made live HTTPS provider calls.

| Request | Run ID | Responses | Input tokens | Output tokens | Total tokens |
| --- | --- | --- | --- | --- | --- |
| Revenue/bar | `6409e77bc80a463a878c42b90b091364` | 4 | 2640 | 147 | 2787 |
| Spend/table | `738839725e054f509ca90bc843301077` | 3 | 1590 | 92 | 1682 |

Reports and traces remain locally under `artifacts/<run-id>/`; the revenue run also contains `chart.png`, which was inspected visually. Tool sequences were inspect → sum → chart → finish and inspect → sum → finish respectively. Aggregate usage reconciled with the individual response metadata in each trace. Independent review checked both runs with no findings. The selected metrics match these two prompts; runtime reports still correctly declare `intent_validation: not_performed` because they do not perform independent language-understanding validation.

The first revenue attempt inside the restricted filesystem/network sandbox returned `provider_error`, zero received responses, no usage, and no published result (run `29d7fb5931b043799faa13619fdadaaf`). The successful runs above used authorized network access. No model substitution or application retry was used.

### Fixture and mocked-provider checks

Verified on: 2026-10-16
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline pytest -q
Verification mode: fixture
Verification result: passed
Verified scope: exact totals and provenance, offline replay, malformed input/data/calls, state isolation, output boundaries, deadline termination, cancellation, and artifact publication/rollback.

Local environment: macOS, Python 3.14.8, uv 0.12.23. The complete case suite passed **133 tests**, including mocked-provider checks; none of these tests calls a live model. The temporary `UV_CACHE_DIR` only routes uv's dependency cache within the development sandbox and is not required by the application. Routine checks:

```sh
uv run --locked pytest -q
```

| Evidence | Result |
| --- | --- |
| Replay CLI | All three documented examples executed with credentials absent: revenue/bar and spend/table completed with exact totals; invalid-tool-call rejected with exit 2. |
| Chart | Generated PNG inspected visually: readable channel/value labels, correct RM totals, zero baseline, 960×540 output. |
| Offline behavior | Both successful replays passed with outbound socket connections blocked and no SDK imported. |
| Failure boundaries | Tests cover strict arguments/results, unsafe fixture/output locations, stale or invented handles, failed-response calls, loop limits, blocked provider/renderer deadlines, and cancellation during execution/publication. |
| Mocked provider | Verified exact request options, original call IDs/history, refusal/incomplete/error rejection before dispatch, usage retention, no SDK retries, and safe diagnostic fields. This does not establish provider compatibility. |
| Case isolation | Copied only this case to a temporary directory, excluding credentials, environment, artifacts, and caches. With `OPENAI_API_KEY` and `PYTHONPATH` unset, `uv sync --locked --offline`, both successful replay examples, and `uv run --locked --offline pytest -q` passed there (133 tests). The offline install used a populated uv cache; imports resolved within the copied case. |
| Independent review | Two publication defects were reproduced, fixed, and covered by regressions; follow-up review found no remaining concrete issue in those paths. |
| Live-provider | Both selected acceptance requests passed against `gpt-6-luna`; commands, run IDs, and usage are recorded above. Missing-credential rejection was also checked separately before a key was supplied. |
| Hosted CI/deployment | CI is configured for local runtime checks; no GitHub run or deployment was performed. |

These two live examples establish the selected requests and provider integration on this date. They do not establish general task alignment, production reliability, or hosted deployment. Revalidate them after provider-facing changes and retain separate fixture, mocked-provider, and live evidence.

## Limitations and references

Only sum-by-channel over the bundled synthetic dataset is in scope. No arbitrary CSVs, filtering, other aggregations, real client data, shell/network tools, database, or web UI. A task asking for unsupported behavior should be declined, but runtime validation cannot independently prove the model understood arbitrary text.

Live mode incurs provider charges and depends on model access/API stability. `store: false` does not guarantee zero provider retention. The [specification](SPEC.md#backend-and-execution-modes) records current primary references and the self-hosted alternative considered.

The existing repository [MIT license](../../LICENSE), copyright (c) 2026 Ekko, is preserved. Pattern reference: Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 7.
