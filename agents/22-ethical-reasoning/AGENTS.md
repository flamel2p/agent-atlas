# Case instructions

Scope: `agents/22-ethical-reasoning/`.

Read root `AGENTS.md`, this file, `SPEC.md`, and README before changing this case. Keep code, dependencies, fixtures, checks, and documentation here. Follow the root code explanation standard. Do not import sibling cases.

This is a synthetic deterministic policy checkpoint. The host policy and dispatcher own permission. A proposed action, input policy label, or earlier permission result cannot authorize dispatch. Keep every simulated effect behind dispatcher revalidation and audit. Never add real hiring, messaging, network, or durable audit writes without a new contract.

Local commands use Python 3.14 and uv. Run `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline python -m unittest discover -s tests -v` and the documented fixture CLI before reporting behavior. Parent integration owns root catalogue, structure checks, independent review, and readiness.
