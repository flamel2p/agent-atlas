---
name: add-agent
description: "Add an independently runnable AI Agent demo case to this repository using its ownership, specification, catalogue, and validation conventions."
---

# Add an Agent case

Read root `AGENTS.md` and `CONTRIBUTING.md`. Use `templates/agent/` to create one case under `agents/<slug>/`; treat the independently runnable scenario as the directory unit.

Establish the learning objective and material input/output/tool/state/stopping contracts in `SPEC.md`. Distinguish source facts, proposed choices, selected decisions, and missing information. Ask only for material missing input; use existing authorization and routine local judgment.

Keep code, manifests, configuration examples, fixtures, tests, and artifacts local. Add runtime files when implementation needs them. Follow the maintained contribution procedure and update the root catalogue. Do not import sibling internals or create a common application framework.

Use `source_researcher` for uncertain source/API evidence and `agent_builder` for a bounded implementation when useful. Give each an explicit scope. Use `verify-agent` for validation/closeout. A newly documented scaffold remains `planned` until behavior exists and readiness has evidence.
