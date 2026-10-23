# Case instructions

Scope: `agents/18-recommendation/`.

Read root AGENTS.md, CONTRIBUTING.md, this file, SPEC.md, and README before edits. Keep all runtime, dependencies, synthetic data, tests, qualification scripts, and artifacts inside this case. Preserve unrelated work and do not import sibling internals.

This is an independent extension with a documented book source gap. Never describe deterministic tag scoring as learned, collaborative, hybrid, calibrated confidence, or proven learner benefit. Use the [source evidence](SOURCES.md) and selected SPEC contract.

The host owns catalogue loading, validation, hard constraints, ranking, cold-start policy, explanations, and termination. No model, network, credentials, persistent learner profile, or external action is permitted. A request describes one run only.

Apply the root [code explanation standard](../../AGENTS.md#code-explanation-standard). Define weighted topic overlap, cold start, prerequisite semantics, and score limits near the code that owns them. Keep a linked README source reading guide.

Selected runtime is uv-managed Python 3.14 on POSIX with `O_NOFOLLOW`, `O_NONBLOCK`, and `O_CLOEXEC`. Use a case-local environment and lockfile. From this directory, run `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline`, then `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v`. The cache override is a restricted-development tooling setting, not runtime state. See README for the executed commands, evidence scope, and source reading guide.

Run `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/verify_cli.py` for the independent subprocess oracle. It accepts `--command PATH` for a wheel-installed console command. Keep it independent of runtime policy helpers.

Only mark demo-ready after normal and limit behavior, standalone installation, wheel execution, and independent substantive review have evidence. Record exact commands and mode limits in README.
