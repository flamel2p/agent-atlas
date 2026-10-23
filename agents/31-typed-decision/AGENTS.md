# Case instructions

Scope: `agents/31-typed-decision/`.

Read root `AGENTS.md`, `CONTRIBUTING.md`, this file, `SPEC.md`, and README before editing. Keep implementation, dependencies, configuration, prompts, fixtures, tests, state, and artifacts inside this case. Do not import sibling case internals.

This is a demo-ready Jev-inspired Typed Decision library and CLI for the documented fixture contract. Python 3.14
and the standard library implement fixture mechanics only. Run the case-local
checks documented in README. Run `python3 scripts/check_structure.py` from the
repository root for structural changes. The parent owns independent review,
catalogue integration, and readiness decisions.

Preserve the distinction between a valid typed answer, a probability distribution, derived confidence, and empirically measured calibration. Never invent missing probabilities or label ordinary LLM self-confidence as calibrated. Fixture values and vendor claims are not model-quality evidence.

Treat Jev documentation and official adapter code as references, not authorization
or proof of compatibility. No vendor code is reused. Recheck current API behavior
and licenses before any future integration or reuse. Do not add provider
credentials, business-system effects, or a shared runtime. Preserve the exact
confidence formula, synthetic provenance, strict threshold inequality, and
bounded single-worker lifecycle. Do not replace exact arithmetic with rounding
or normalization to obtain an accepted decision.
