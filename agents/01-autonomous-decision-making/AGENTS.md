# Case instructions

Scope: `agents/01-autonomous-decision-making/`.

Read root `AGENTS.md`, `CONTRIBUTING.md`, this file, `SPEC.md`, and README before editing. Keep implementation, dependencies, fixtures, prompts, and tests here. Do not import sibling case internals or read their credentials.

This is a synthetic support-triage learning demo. The model proposes a route; host policy owns authority and renders all customer-facing text. There are no business mutations, real support integrations, message delivery, persistent sessions, or learning updates. Human handoffs are local records only.

Use case-local Python 3.14.8 and uv. Commands from this directory: `uv sync --locked`, `uv run --locked autonomous-decision-making --example routine-outage`, and `uv run --locked pytest -q`. In this restricted workspace, prefix tooling with `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache`; `--offline` uses the populated dependency cache. Optional live setup is documented separately in README. Record commands actually executed and evidence limits there. Never include ticket messages, provider response bodies, raw exceptions, or credentials in traces/errors.
