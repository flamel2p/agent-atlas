# Case instructions

Scope: `agents/15-self-improving/`.

Read root `AGENTS.md`, this file, [SPEC.md](SPEC.md), and [README.md](README.md) before changes. Keep all runtime files, fixtures, checks, and documentation in this case. Follow the root code explanation standard and maintain the linked reading guide.

This is one deterministic, fixture-only learning experiment. The only adaptation is a revision tie-breaker for one supported topic. Preserve the baseline, stdout-only reports, strict fixture bounds, curator authority boundary, selection/holdout separation, and one-candidate stopping rule. There is no approval, activation, deployment, model, provider, or network capability.

Use Python 3.14 and `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache`. From this directory, run `uv run --locked --offline python -m unittest discover -s tests -v` and the documented CLI scenarios. Root owns catalogue integration and readiness after independent review.
