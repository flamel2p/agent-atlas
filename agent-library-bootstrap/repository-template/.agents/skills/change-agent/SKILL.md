---
name: change-agent
description: "Modify or fix one existing AI Agent demo while preserving its local behavior contract, case isolation, and synchronized implementation, checks, and documentation."
---

# Change an Agent case

Read root `AGENTS.md`, `CONTRIBUTING.md`, and the target case's `AGENTS.md`, `SPEC.md`, and README. Identify the affected behavior and owned files before edits.

Preserve unrelated work and sibling cases. Update selected behavior contracts and relevant implementation/checks/docs together. For bugs, diagnose the actual failed contract and add a meaningful regression check where appropriate. Documentation-only changes do not require unrelated runtime tests.

Resolve material contract ambiguities before dependent edits. Do not treat a need for cross-case coupling as permission to expand scope or build a shared runtime. Select routine local details without repeated approval requests.

Use `agent_builder` for scoped work and `agent_reviewer` for substantive independent review when useful. The parent integrates changes and uses `verify-agent` to record actual evidence and close out.
