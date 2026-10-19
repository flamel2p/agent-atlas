# Case instructions

Scope: `agents/03-memory-augmented/`.

Read root `AGENTS.md`, this file, `SPEC.md`, and README before changes. Keep implementation, dependencies, prompts, fixtures, tests, state, and artifacts here. Do not import sibling cases or create shared runtime code.

This is a synthetic study assistant. User IDs are operator-supplied namespaces, not authentication. Only explicit structured preference input may change remembered preferences. Model text and retrieved records never authorize writes, change identity, or become authoritative facts.

Use case-local SQLite for episodic memory and a packaged read-only FAQ for semantic knowledge. Never save generated answers as future factual evidence. Default commands are offline replay; live mode is explicit and must not silently fall back.

Setup: `uv sync --locked`. Run: `uv run --locked memory-agent --help`. Full checks, including SDK calls against mocked HTTP: `uv run --locked --offline --extra live pytest -q` (cache dependencies first with `uv sync --locked --extra live`). State belongs under ignored `private-data/`; use synthetic data only. Verification records must distinguish fixture, mocked-provider, live-model, and deployment evidence.
