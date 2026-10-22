# Case instructions

Scope: `agents/14-security-and-compliance/`.

Read root `AGENTS.md`, this file, `SPEC.md`, and README before changing this case. Keep owned code, dependencies, configuration, fixtures, tests, state, and artifacts here. Do not edit sibling cases or introduce a common runtime.

Keep behavior and validation aligned with `SPEC.md`. Update relevant checks and README for behavior changes. Report actual checks and unresolved limits separately.

Follow the root [code explanation standard](../../AGENTS.md#code-explanation-standard): define the case's concepts and responsibilities in code, explain non-obvious decisions and authority boundaries, and maintain the README source reading guide.

Runtime: Python 3.14, managed with case-local `uv` metadata and a pinned Hatchling 1.32.4 build backend. Runtime dependencies use only the standard library. From this case directory, install with `uv sync --locked --python 3.14`, run `uv run --locked compliance-agent --scenario clean`, and check behavior with `uv run --locked python -m unittest discover -s tests -v`. Set `UV_CACHE_DIR=/tmp/agent14-uv-cache` if the normal development cache is unavailable. CLI blocked and review outcomes intentionally return nonzero exit codes.

This case implements the book's chapter compliance pattern. Preserve the naming discrepancy with the Security-Hardened reference-list alias. The policy is synthetic and local. Do not claim regulatory certification or general Python security analysis.

Never execute submitted source, apply suggested fixes, access network services, or let source comments or identifiers change policy authority. Unsupported analysis must not produce a pass. Reports and errors must omit source values and excerpts.

Keep the policy field values and supported AST subset synchronized with SPEC.md. Source origins are immutable and invocation-local. Unsupported statements commit no partial state or findings. Preserve the prior supported prefix, then stop. Parser diagnostics must not escape the source-free output boundary, including under caller warning filters.

Maintain actual process checks for CLI outcomes and meaningful semantic checks for authority, failure, and resource limits. Tests may launch subprocesses and use temporary directories to verify the application. The runtime may not do either. Mark the case `demo-ready` only after independent review and standalone package qualification have evidence.
