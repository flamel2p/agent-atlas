# Tool-Using Agent specification

Slug: tool-using
Status: planned
Runtime: Python 3.14 (uv CLI)

## Problem and scope

Build a developer-facing CLI that turns a request about synthetic campaign spend or revenue into validated local tool calls, a totals table, and optionally one bar chart. The learning objective is the boundary between model-proposed actions and executable authority.

Contract selected on 16 October 2026 at the user's request. This document selects behavior for implementation; no runtime, dependencies, fixtures, or model calls have been implemented or validated yet.

Included: one bundled dataset, sum by channel, inspectable calls, deterministic replay, and opt-in live tool selection. Excluded: arbitrary file uploads, other aggregations/groupings, filtering, business recommendations, web UI, database, persistent memory, multiple providers, and external business actions.

## Evidence and decisions

**Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 7, printed pp.174-186 / physical PDF pp.205-217, as recorded in the supplied [source brief](../../agent-library-analysis/agents/07-tool-using.md). Its conceptual responsibilities are reasoning, registry, execution, and tools. The brief reports that the concrete sample uses rules rather than LLM selection, can preserve stale data after failed aggregation, and can silently default unsupported aggregation to sum. These findings were not independently reproduced here.

**Selected design:** use the brief's synthetic reporting scenario, implement real function calling only in live mode, and give both modes the same dispatcher and validators. Neither mode may continue after failed tool execution. The source is inspiration, not a runtime contract or test result.

| Decision | Selection and reason | Main alternative considered |
| --- | --- | --- |
| Runtime | CPython 3.14, synchronous CLI, case-local `uv` project. A maintained Python branch fits the source and CSV/chart tooling. | TypeScript remains viable but offers no clear advantage for this first data-focused case. |
| Dependencies | Standard-library CSV/integer arithmetic; Pydantic 2 for schemas; Matplotlib with the noninteractive Agg backend; official `openai` SDK; pytest for tests. | pandas and an agent framework add unnecessary surface for six rows and three tools. |
| Backend | OpenAI Responses API, model `gpt-6-luna`, direct SDK calls. | Self-hosted inference would add hardware, model packaging, and tool-calling compatibility work before demonstrating the execution boundary. |
| Default mode | Explicit scripted `replay`; `live` requires deliberate selection and `OPENAI_API_KEY`. | A keyword parser would blur simulation with model selection. |
| Authority | Three fixed local tools; one synthetic dataset; host-generated output locations. | Arbitrary files, shell tools, and internet tools are outside this learning objective. |

Python 3.14 is a maintained branch in the [Python status table](https://devguide.python.org/versions/). A case-local `.python-version`, `pyproject.toml`, and committed `uv.lock` will make the selected environment reproducible; see [uv project conventions](https://docs.astral.sh/uv/guides/projects/) and [locked synchronization](https://docs.astral.sh/uv/concepts/projects/sync/). Exact Python patch and package versions will be resolved, locked, and compatibility-tested during implementation, without changing this selected scope.

## Inputs and outputs

### CLI contract

- `--mode replay|live`, default `replay`.
- Replay accepts only `--example revenue-by-channel-bar|spend-by-channel-table|invalid-tool-call`, default `revenue-by-channel-bar`. Each example declares its task, output format, and scripted proposals; reject live-only flags rather than ignore them.
- Live requires `--task` that trims to a nonempty string of at most 500 Unicode characters and accepts `--format table|bar`, default `table`. Reject replay-only flags. The explicit format controls chart authority even if the task asks for a different format.
- Dataset is fixed to `campaign-demo-v1`; no user/model paths, URLs, output-directory argument, or model override in v1.
- Supported task meaning: total spend or total revenue by channel over the entire fixture. No free-form calculations or silent conversion of an unsupported operation to sum. Instruct the live model to decline unsupported tasks; runtime schemas cannot independently prove that it understood the request.

Planned entry point: `tool-using` from inside this case. Example commands are design targets, not currently runnable:

```sh
uv run --locked tool-using --mode replay --example revenue-by-channel-bar
uv run --locked tool-using --mode live --task "Compare total revenue by channel" --format bar
```

### Dataset contract

Owned path: `fixtures/campaigns.csv`, resolved by application code from the case directory. Read once per run into an immutable snapshot. Reject symlinks, missing/extra columns, duplicate `(date, channel)` pairs, blank cells, malformed dates, or invalid amounts. No coercion of missing values to zero.

Required columns and the six selected synthetic rows:

| date | channel | spend_sen | revenue_sen |
| --- | --- | --- | --- |
| 2026-09-01 | Search | 10000 | 30000 |
| 2026-09-01 | Social | 8000 | 16000 |
| 2026-09-01 | Email | 2000 | 12000 |
| 2026-09-02 | Search | 15000 | 45000 |
| 2026-09-02 | Social | 12000 | 24000 |
| 2026-09-02 | Email | 3000 | 18000 |

Dates use `YYYY-MM-DD`; channels are `Email|Search|Social`; amounts are base-10 integer sen in `0..100000000`. Cap the file at 64 KiB and 100 rows. Fixtures use MYR; display currency as RM with two decimals. Calculate with integers; convert to floating point only for chart coordinates. Capture the dataset ID and SHA-256 of its bytes in results.

### Output contract

Create one host-generated `artifacts/<run-id>/` directory per run. Produce `report.json`, `trace.jsonl`, and, only on a successful bar run, `chart.png`. Emit the same final report JSON to stdout; diagnostics go to stderr. An input/configuration error before run creation may return a structured error without files. Never overwrite an earlier run.

The report contains `run_id`, `mode`, `status`, `dataset_id`, `dataset_sha256` when loaded, `requested_format`, `summary` or null, `chart` or null, and `error` or null. Include the requested/reported provider model and token usage when available in live mode. Summary records include metric, `group_by: channel`, `operation: sum`, `unit: sen`, sorted channel totals, and RM display strings. Chart records include an artifact ID, case-relative path, and originating summary ID.

Statuses: `completed`, `rejected`, `failed`, `limit_reached`, or `cancelled`. Exit 0 only for `completed`, 2 for input/configuration or rejected proposals, 1 for operational failures/limits, and 130 for interruption. The intentional `invalid-tool-call` replay therefore exits 2.

`completed` means the selected tool operations and requested output format passed executable checks. It does **not** prove that the selected metric matches the natural-language task. Report `intent_validation: not_performed`; always show the selected metric. Acceptance tests evaluate task alignment separately. Model prose is not authoritative report data and is not copied into the report.

## Architecture and state

Use ordinary modules inside `src/tool_using/`: CLI/run controller, one small decision-backend interface with replay/OpenAI implementations, a fixed registry/dispatcher, validators, and local reporting tools. Do not add a generic plugin framework or shared provider package.

Flow: CLI → validated run configuration and dataset snapshot → backend proposal → dispatcher validation → local tool → validated result → next backend decision → host-generated report.

Run state holds the immutable dataset, response history, counters, a single validated summary, an optional chart reference, and terminal status. Handles are allocated by the host and valid only in that run. Only validated success results enter usable state; a failure makes the run terminal and prevents any later tool use. Previous intermediate results may appear in diagnostics but are never promoted to a successful report after failure.

## Tools and authority

All argument objects reject extra keys and coercion, including booleans as integers. Validate result schemas and provenance before publishing results to the backend. Pydantic strict validation supports this boundary; [strict mode documentation](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/) does not replace case-specific checks.

| Tool | Arguments | Validated result | Permitted effect |
| --- | --- | --- | --- |
| `inspect_dataset` | `{}` | Dataset ID/hash, row count, columns, supported metrics, channel values, currency/unit. | Read the already validated in-memory snapshot; no additional file access. |
| `sum_by_channel` | `metric`: `spend_sen` or `revenue_sen` | Host-generated `summary_id`, dataset provenance, selected metric, sorted `{channel, total_sen}` rows. | Compute one summary from the snapshot. No file/network effect. |
| `render_bar_chart` | `summary_id: string` | Host-generated `artifact_id`, originating summary ID, path, PNG dimensions. | Render that run's validated summary to a staged PNG, only when format is `bar`. |

`sum_by_channel` has no aggregation argument: it explicitly sums. Unknown tools such as `average_by_channel` and extra arguments such as `operation: average` are rejected. Allow at most one successful summary and one chart per run; reject replacements or duplicates as invalid state.

The chart tool accepts no data array, title, code, filename, or path from the model. Derive labels and title from the validated summary. Render a 960×540 PNG using Matplotlib Agg, with channels alphabetically ordered, RM labels, and a zero baseline. Test values/provenance and dimensions; do not demand identical PNG bytes across platforms. See [Matplotlib backends](https://matplotlib.org/stable/users/explain/figure/backends.html).

Application code owns output paths and creates them exclusively inside the physical case-local artifacts directory. Reject escaping paths and symlinked fixture/output locations. Keep plotting cache/config inside that run directory. Publish the staged chart only after successful completion; failure/cancellation leaves no published chart or successful summary in the report.

No model-selected shell, Python execution, HTTP requests, database access, installation, messaging, or file deletion. The live backend's fixed HTTPS connection to `https://api.openai.com/v1` is the sole network integration; do not honor arbitrary API-base overrides. This is an application capability boundary, not an OS network sandbox. No human checkpoint is required for these fixed local effects. Adding external or destructive effects changes the contract.

## Backend and execution modes

**Replay:** use predetermined proposals and terminal responses for named examples, sending them through the same dispatcher. After dependencies are installed, replay needs no credentials, SDK client, model download, or network. Do not label it AI reasoning or live-model evidence.

**Live:** use the official Python SDK with `gpt-6-luna`, reasoning effort `none`, foreground Responses requests, explicit `strict: true` function schemas, `tool_choice: auto`, `parallel_tool_calls: false`, `store: false`, and `max_output_tokens: 1200`. All object schemas have `additionalProperties: false`, with required fields. These capabilities are documented for [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) and [function calling](https://developers.openai.com/api/docs/guides/function-calling).

Maintain conversation history in memory, preserve required response output items, and correlate each `function_call_output` with the original `call_id`. Never dispatch plain text as a call. Reject multiple calls in one response before executing any; disable hosted tools and automatic provider/model fallback. Expose the chart tool only in bar mode and enforce that rule again in the dispatcher.

Only the task, fixed instructions/schemas, and bounded synthetic metadata/results go to the provider. Read `OPENAI_API_KEY` from the process environment in live mode only; a later `.env.example` contains variable names and harmless placeholders. Do not log keys, headers, environment contents, raw provider exceptions, full prompt/response bodies, or model reasoning. Traces contain validated call arguments, result/error codes, provenance, timings, and usage; malformed proposal payloads are omitted.

Paid API access, account availability, rate limits, model drift, and API changes remain external dependencies. `store: false` does not mean zero retention; provider abuse-monitoring controls still apply. Do not send real client data. See [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data). Keep the narrow backend interface local; self-hosted inference is a later case-scoped decision.

## Execution and termination

1. Validate CLI/configuration before model calls; require credentials only for live mode. Allocate a run directory, load/validate the bounded fixture, and initialize empty state.
2. Request one backend decision. Parse the entire response and validate its status before dispatch. Refusal, failure, truncation/incompleteness, or an unsupported response shape ends with non-success, even if the response also contains a valid-looking function call. Reject unknown tools, malformed JSON, extra/incorrect arguments, multiple calls, or invalid state without executing the proposal.
3. Execute one permitted tool and validate its result before making it available to subsequent decisions. Record a bounded trace event. Any failed tool or invalid result ends the run; no automatic correction, tool retry, or silent fallback.
4. Continue within the limits below; do not infer completion from partial output.
5. A completed backend response with no function call requests termination. Success requires one valid summary, plus a valid chart referencing it for bar mode, and no prior failure. Missing artifacts/results produce `incomplete_result`; free-form text cannot bypass this predicate.
6. Build the final report from validated state, publish the chart on success, and close the trace. On failure, keep `summary` and `chart` null in the final report and report the failing phase/code.

Limits are application decisions: at most **6 backend responses**, **5 admitted tool attempts**, **30 seconds per provider request**, and **120 seconds total execution time**. Reject a further proposal before dispatch. Configure SDK `max_retries=0`; no tool retries in v1. The [SDK documents timeouts and retries](https://developers.openai.com/api/reference/python), but its transport timeout is not a total-run deadline.

Enforce both elapsed-time deadlines using a controller capable of terminating its trusted run worker: each provider request ends by the earlier of 30 seconds from request start or the overall 120-second deadline. The overall deadline also interrupts a blocked renderer; checking elapsed time only between calls is insufficient. The surviving controller owns final status/report writing and artifact publication, publishing only after successful worker completion. Cancellation stops further effects and prevents publication. Dependency installation is outside this execution clock. This trusted implementation worker is not a model-callable process-execution tool.

Use stable error codes for `invalid_input`, `missing_credentials`, `invalid_dataset`, `invalid_tool_call`, `invalid_tool_result`, `invalid_state`, `provider_error`, `provider_refusal`, `provider_timeout`, `incomplete_result`, `limit_reached`, `artifact_error`, and `cancelled`. Preserve sanitized status/request IDs when useful; never convert failures into empty successful results.

## Acceptance criteria

All criteria below are selected and **unexecuted**:

| Mode | Criterion |
| --- | --- |
| Fixture/replay | Revenue bar example computes Email 30000, Search 75000, Social 40000 sen; chart points to that exact summary and displays RM 300.00, RM 750.00, RM 400.00. |
| Fixture/replay | Spend table example computes Email 5000, Search 25000, Social 20000 sen; emits no chart and works with credentials absent and outbound network blocked. |
| Fixture | Unknown tools, extra keys, invalid enums/types, multiple-call responses, and chart requests in table mode produce rejection before the forbidden effect. The invalid-tool replay exposes this behavior. |
| Fixture | Missing columns, malformed/blank amounts, duplicate rows, oversized data, or symlinked fixture paths stop the run before usable results; a forced aggregation failure blocks rendering and prevents stale-summary success. |
| Fixture | Invented/cross-run summary IDs, duplicate summaries/charts, and escaping/symlinked output locations are rejected. A chart uses stored computed totals, never model-supplied numbers. |
| Fixture/mocked-provider | Premature final output, refusal, truncation, provider errors, response/tool limits, a blocked operation, and cancellation terminate with the defined non-success result and no published chart. Refusal/failed/incomplete responses containing a valid-looking call cause no dispatch. Verify both per-request and total hard deadlines. |
| Mocked-provider | Verify exact request options, call-ID/history handling, response/result validation, no SDK retries, and no raw secrets/provider bodies/reasoning in reports or traces. This is not live-provider evidence. |
| Live-model | Explicitly run the revenue/bar and spend/table requests against the selected model; verify selected metrics, exact totals, chart presence/provenance, terminal result, and token usage. Report actual pass/fail and account/model errors without substituting replay. |
| Isolation | From the case directory alone, locked setup, replay, and local checks work without sibling cases, root runtime packages, shared credentials, or root application configuration. |

Fixture and mocked-provider success may qualify the documented replay demo as `demo-ready`, with live validation explicitly unverified. Claim live-mode verification only after its listed checks actually run. Two examples demonstrate those requests, not general language understanding or production reliability.

## Dependencies and open decisions

Runtime, scenario, backend, output modes, tool authority, limits, and acceptance contracts are selected. No further product-scope decision blocks implementation.

Implementation work remains: create case-local packaging/lockfile and fixtures, implement the contract, select compatible exact package/patch versions, and record verified setup/run/test commands. Recheck provider/model availability before a live run. Keep status `planned` until implementation starts; do not create successful verification records from this specification.

The existing repository [MIT license](../../LICENSE), copyright (c) 2026 Ekko, is preserved. Source bundles remain historical references. Next step: implement this case and its fixture/mock checks, then separately report any live-model validation.
