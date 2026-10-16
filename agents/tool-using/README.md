# Tool-Using Agent

Slug: tool-using
Status: planned
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

A CLI that summarizes synthetic campaign spend or revenue by channel and optionally creates a bar chart. The selected [behavior contract](SPEC.md) demonstrates how model-proposed calls pass through a validated execution boundary.

Decisions selected on 16 October 2026:

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

## Setup and run

Not implemented. No runtime command, dependency manifest, or fixture file exists yet. The planned entry point and example commands are specified in [SPEC.md](SPEC.md#cli-contract); they are not executable setup instructions.

Implementation will add local `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, `src/`, `tests/`, and `fixtures/`. Exact versions and working commands will be recorded after verification. Generated reports, traces, charts, and plotting cache stay under `artifacts/<run-id>/`.

## Verification

Not implemented or run. The [acceptance criteria](SPEC.md#acceptance-criteria) cover arithmetic/provenance, rejected calls, dataset/state failures, bounded execution, provider behavior, and case isolation. Replay and mocked-provider outcomes will be recorded separately from live-model results.

Contract-edit checks on 16 October 2026: `python3 scripts/check_structure.py` from the repository root and local Markdown link validation. These check documentation/metadata only and do not validate the selected runtime or backend.

## Limitations and references

Only sum-by-channel over the bundled synthetic dataset is in scope. No arbitrary CSVs, filtering, other aggregations, real client data, shell/network tools, database, or web UI. A task asking for unsupported behavior should be declined, but runtime validation cannot independently prove the model understood arbitrary text.

Live mode incurs provider charges and depends on model access/API stability. `store: false` does not guarantee zero provider retention. The [specification](SPEC.md#backend-and-execution-modes) records current primary references and the self-hosted alternative considered.

The existing repository [MIT license](../../LICENSE), copyright (c) 2026 Ekko, is preserved. Pattern reference: Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 7.
