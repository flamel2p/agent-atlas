# Case instructions

Scope: `agents/21-physical-world-sensing/`.

Read root `AGENTS.md`, this file, `SPEC.md`, and README before changing this case. Keep code, dependencies, fixtures, checks, and artifacts local. Preserve sibling cases and root governance.

This is deterministic synthetic sensor replay. No network, LLM, hardware adapter, or real actuator authority exists. Missing observations never establish a safe physical condition. A held decision does not mean a physical actuator stopped.

Follow the root code explanation standard. Define freshness, fusion, coverage, conflict, and simulation in code and maintain the README reading guide.

Local setup uses `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline`. Run `uv run --locked --offline python -m unittest discover -s tests -q` and the independent CLI checker documented in README. Use the same cache variable for uv commands in restricted environments.
