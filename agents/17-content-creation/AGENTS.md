# Case instructions

Scope: `agents/17-content-creation/`.

Read root `AGENTS.md`, this file, [SPEC.md](SPEC.md), and [README.md](README.md) before changes. Keep all implementation resources within this case. Follow the root code explanation standard and maintain the README source reading guide.

This case is a deterministic fixture composer. Canonical fact sentences and curated copy are host-owned. Do not introduce free-form factual text, provider access, publishing, arbitrary output files, or sibling imports.

`validated` means the stated mechanical content checks passed. Human approval is not granted. Exhausted or impossible drafts remain visibly unapproved. Never weaken review checks or replace feedback-driven revisions with a scenario-specific trace.

Use Python 3.14 and uv. Local commands are `uv sync --locked`, `uv run --locked content-creation`, and `uv run --locked python -m unittest discover -s tests -v`. Update the README with actual execution evidence. In restricted environments, use `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache` when the default cache is unwritable.
