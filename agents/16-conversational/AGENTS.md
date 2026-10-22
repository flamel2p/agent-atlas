# Case instructions

Scope: `agents/16-conversational/`.

Read root `AGENTS.md`, `CONTRIBUTING.md`, this file, [SPEC.md](SPEC.md), and [README.md](README.md) before changes. Keep all code, fixtures, dependencies, tests, private state, and artifacts local. Follow the root code explanation standard and maintain a linked source reading guide.

This synthetic course-navigation demo uses deterministic dialogue policy and responses. Preserve host-owned persona, the gate before storage/composition, exact user/session namespaces, explicit typed preferences, bounded transactional SQLite persistence, and truthful limits. User labels are not authenticated identities. No LLM, network, arbitrary tools, or clinical scenario is in scope.

Use Python 3.14.8 and `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache`. Run `uv run --locked --offline python -m unittest discover -s tests -v` and `uv run --locked --offline python scripts/qualify.py` from this directory. The latter repeats tests, restart dialogues, and the independent CLI oracle in a copied case and an installed wheel. The parent owns the catalogue and readiness decision following independent review.
