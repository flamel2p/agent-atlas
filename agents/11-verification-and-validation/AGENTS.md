# Case instructions

Scope: `agents/11-verification-and-validation/`.

Read root AGENTS.md, this file, SPEC.md, and README before edits. Keep all implementation, dependencies, fixtures, tests, and artifacts local. Follow the root code explanation standard and maintain the linked source reading guide.

Claims are data; bundled evidence is synthetic host-owned authority. Do not add caller-controlled truth, tolerance, network access, or LLM verdicts without a selected contract. Preserve exact scope, baseline, units, direction, exclusions, and all conflicting evidence. A hash proves byte identity only.

From this directory, use `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked`, `uv run --locked verification-agent fixtures/claims.json`, and `uv run --locked python -m unittest discover -s tests -v`. Use `--offline` when caches are populated. Run root `python3 scripts/check_structure.py` for structural/catalogue changes.

Report actual evidence modes. Fixture checks do not establish real-world truth, language extraction quality, or production readiness. Preserve the independent case and installed-package run paths.
