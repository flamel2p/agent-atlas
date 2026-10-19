# Planning case instructions

Scope: `agents/02-planning/`.

Read root `AGENTS.md`, `CONTRIBUTING.md`, this file, `SPEC.md`, and README before edits. Keep implementation, dependencies, fixtures, prompts, checks, and state local. No sibling runtime imports or root provider configuration.

Use `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked` for installation, `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked planning-agent --example normal` to run, and `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked pytest -q` to test from this directory. Live mode requires the local `live` extra and an explicitly invoked `--mode live`.

Workers and time are simulated. Preserve executable validation of the domain task graph, assignments, resource capacity, completed work on revision, terminal states, and bounded replanning. No shell execution, arbitrary file access, external publication, or actual specialist agents. Output is stdout JSON only; never echo credentials, provider exception payloads, or unvalidated model text.
