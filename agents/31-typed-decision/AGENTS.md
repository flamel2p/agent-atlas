# Case instructions

Scope: `agents/31-typed-decision/`.

Read root `AGENTS.md`, `CONTRIBUTING.md`, this file, `SPEC.md`, and README before editing. Keep implementation, dependencies, configuration, prompts, fixtures, tests, state, and artifacts inside this case. Do not import sibling case internals.

This is a planned Jev-inspired Typed Decision Agent. The current deliverable is its library registration and scope; no runtime has been selected or implemented. Setup/run/test commands remain undecided. Run `python3 scripts/check_structure.py` from the repository root for structural changes.

Preserve the distinction between a valid typed answer, a probability distribution, derived confidence, and empirically measured calibration. Never invent missing probabilities or label ordinary LLM self-confidence as calibrated. Fixture values and vendor claims are not model-quality evidence.

Treat Jev documentation and official adapter code as references, not authorization or proof of compatibility. Recheck current API behavior and licenses before integration or reuse. Do not add provider credentials, business-system effects, or a shared runtime while resolving the planned scope.
