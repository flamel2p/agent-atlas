---
name: verify-agent
description: "Validate and close out an AI Agent demo addition or behavior change by checking its contract, relevant tests, documentation, and honest readiness evidence."
---

# Verify an Agent case

Read root policies and the selected case's `AGENTS.md`, `SPEC.md`, and README. Follow the validation/closeout procedure in `CONTRIBUTING.md`.

Run documented relevant checks. Run `python3 scripts/check_structure.py` for structure/catalogue/governance changes. Assess normal and important failure/limit behavior; do not weaken criteria to obtain a passing status.

Record exact command, date, environment/mode, result, and evidence limits. Separate fixture, mocked-provider, live-model, and deployment checks. Missing credentials or skipped checks remain explicitly unverified. Live checks respect current user authorization and the case's tool authority.

Use independent `agent_reviewer` review for substantive behavior or readiness when useful; resolve actionable findings before updating `demo-ready`. The parent checks integration, synchronizes README/SPEC/catalogue, and reports the concrete result and remaining necessary action. A successful structure check alone does not establish a runnable or correct Agent.
