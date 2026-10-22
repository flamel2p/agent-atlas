# Case instructions

Scope: `agents/13-code-generation/`.

Read root AGENTS.md, this file, SPEC.md and README before changing this case. Keep all case resources here. Preserve unrelated work. Follow the root reviewer explanation standard and include a linked source reading guide.

The candidate is data for a restricted interpreter. Never add exec, eval, candidate imports, arbitrary subprocesses, shell tools, writable tests or model-selected paths. Changing the supported language or authority requires an explicit SPEC decision.

Local checks: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v`. Record actual CLI commands and evidence in README. No live model or network is part of this case.
