# Case instructions

Scope: `agents/08-chain-of-agents-orchestrator/`.

Read root `AGENTS.md`, this file, `SPEC.md`, and README before changing this case. Keep owned code, dependencies, configuration, fixtures, tests, state, and artifacts here. Do not edit sibling cases or introduce a common runtime.

Keep behavior and validation aligned with `SPEC.md`. Update relevant checks and README for behavior changes. Report actual checks and unresolved limits separately.

Follow the root [code explanation standard](../../AGENTS.md#code-explanation-standard): define the case's concepts and responsibilities in code, explain non-obvious decisions and authority boundaries, and maintain the README source reading guide.

Runtime: Python 3.14 with uv. Setup, run, and test commands are maintained in the README.

This case coordinates deterministic specialists over synthetic, structured release evidence. It uses no model, network service, shell tool, persistent memory, or release/deployment capability. Keep these limits explicit. Fixture agreement does not establish release readiness or source truth.

The manager alone owns run state and accepted results. Specialists receive immutable input snapshots and may return proposals only. Validate message identity, assigned role, source references, and result contents before acceptance. Unresolved evidence conflicts remain review items.
