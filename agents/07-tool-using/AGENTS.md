# Tool-Using case instructions

Scope: `agents/07-tool-using/`.

Read root `AGENTS.md`, this file, `SPEC.md`, and README before work. Keep related tools, code, manifests, configuration, tests, fixtures, state, and artifacts within this case. Do not depend on sibling cases.

This case implements the contract in `SPEC.md`: Python 3.14 with uv, synthetic campaign totals by channel, default scripted replay, and opt-in OpenAI Responses with `gpt-6-luna`. The replay demo is verified; live-provider evidence is recorded separately in README.

The central learning objective is the boundary between selecting a tool call and executing a validated, permitted operation. Preserve that executable boundary. Keep input validation, stopping/error behavior, and execution evidence explicit.

Only `inspect_dataset`, `sum_by_channel`, and `render_bar_chart` are allowed. Preserve the fixed dataset, run-local handles/outputs, terminal failures, and execution limits. Do not widen tools, data sources, provider choices, or effects without updating the contract. Keep replay, mocked-provider, and live evidence distinct; valid execution does not prove natural-language task alignment.

From this directory, use `uv sync --locked`, `uv run --locked tool-using`, and `uv run --locked pytest -q`. Replay requires no key or network after installation. Live mode is explicit; load an ignored case-local `.env` with `uv run --locked --env-file .env` or export the key. Do not log secrets or auto-load credentials from other directories. See README for the two live acceptance commands and current verification limits.
