# Tool-Using case instructions

Scope: `agents/tool-using/`.

Read root `AGENTS.md`, this file, `SPEC.md`, and README before work. Keep related tools, code, manifests, configuration, tests, fixtures, state, and artifacts within this case. Do not depend on sibling cases.

This case is planned with its implementation contract selected in `SPEC.md`: Python 3.14 with uv, synthetic campaign totals by channel, default scripted replay, and opt-in OpenAI Responses with `gpt-6-luna`. Implementation has not started.

The central learning objective is the boundary between selecting a tool call and executing a validated, permitted operation. Implement that boundary in code when development begins. Keep input validation, stopping/error behavior, and execution evidence explicit.

Only `inspect_dataset`, `sum_by_channel`, and `render_bar_chart` are allowed. Preserve the fixed dataset, run-local handles/outputs, terminal failures, and execution limits. Do not widen tools, data sources, provider choices, or effects without updating the contract. Keep replay, mocked-provider, and live evidence distinct; valid execution does not prove natural-language task alignment.

Local setup/run/test commands: not established. Implement the selected contract, then update this file and README with verified commands. Planned commands in `SPEC.md` are not execution evidence.
