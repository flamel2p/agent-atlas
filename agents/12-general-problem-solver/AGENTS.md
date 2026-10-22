# Case instructions

Scope: `agents/12-general-problem-solver/`.

Read root `AGENTS.md`, this file, `SPEC.md`, and `README.md` before changes. Follow repository isolation and code explanation standards. This case owns its implementation, dependencies, fixtures, tests, and artifacts. No sibling imports or private environments.

This deterministic scheduling puzzle teaches feedback-driven strategy revision. The evaluator alone establishes feasibility. Analogy cards are illustrative heuristic descriptions. Do not add confidence scores, external models, runtime network, persistent learning, code execution, real dispatch, or infeasibility claims.

`solve_document(document: bytes) -> Report` is the public operation. Preserve strict parsing, immutable records, positive constraint excesses, both budgets, deterministic ties, and explicit local minima. Keep explanations aligned with executable controls.

Run from this directory with Python 3.14 and uv:

```sh
uv sync --locked
uv run --locked general-problem-solver --example revision
uv run --locked python -m unittest discover -s tests -v
```

For this sandbox, prefix uv commands with `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache`. Record only checks actually run. Parent Codex owns catalogue changes and final readiness.
