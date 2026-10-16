# Contributing

## Add a case

1. Select a distinct learning objective and a stable kebab-case slug. A directory represents an independently runnable scenario, not every tool or LLM role inside it.
2. Copy `templates/agent/` to `agents/<slug>/`. Replace placeholders and set metadata to `planned` until implementation begins.
3. Fill the specification with the problem, input/output contract, architecture, state, tool authority, execution and stopping rules, failure behavior, and observable acceptance criteria. Identify source facts, proposed choices, and selected decisions separately.
4. Choose the language, backend, and local dependencies required by that case. Add code/test/fixture directories and configuration examples when implementation needs them.
5. Implement and validate the smallest coherent demo. Keep all case-owned resources local. Review substantive behavior before declaring readiness.
6. Update the root catalogue and case README with actual commands, results, and limitations.

The `add-agent` skill packages this workflow; it does not authorize unrelated case changes or publication.

## Change an existing case

Read its instructions and contract first. Identify the affected behavior, update its specification where needed, and change only the owned implementation and supporting checks/docs. A bug fix should cover the actual regression or failed contract when a meaningful check is possible. Documentation-only edits do not require unrelated runtime tests.

If a change needs sibling internals or common runtime code, stop expanding the case and describe the ownership/API decision first. Do not create a shared framework as a shortcut.

## Validate and close out

Run the case's documented checks and the structure check when relevant. Record the command, date, environment/mode, result, and scope of evidence in the README. Redact secrets and avoid retaining private inputs. A skipped or unavailable check stays visibly unverified.

For `demo-ready`, include the latest qualifying verification record in the README using these exact field labels:

```text
Verified on: YYYY-MM-DD
Verification command: actual command executed
Verification mode: fixture | mocked-provider | live-model | deployment
Verification result: passed
Verified scope: behavior and acceptance criteria actually checked
```

Choose one mode value per qualifying record; list additional runs and limitations separately. A record is a report of evidence, not a substitute for running the checks. The structure checker validates the fields, while actual test runs and review establish their truth.

Use these catalogue statuses:

- `planned`: scope or implementation decisions remain; no runnable demo is claimed.
- `in-progress`: implementation exists or is being built; readiness criteria are incomplete.
- `demo-ready`: the documented run path and selected acceptance checks have actual evidence; limits remain explicit.
- `archived`: retained for reference, with maintenance status explained.

Each implemented case needs at least one observable normal-path criterion and one meaningful failure/limit criterion. Add checks for state, authorization, memory isolation, consensus, or physical invariants where the particular pattern requires them. Do not enforce arbitrary output wording as a substitute for behavioral evidence.

Before marking `demo-ready`, reconcile independent review findings and update README/SPEC/catalogue together. The parent Codex integrates work and owns this final assessment.

## Root governance

Root policies, templates, skills, development roles, and structure tooling can change as a separately stated governance task. Keep their rules consistent and concise. Existing user authorization takes precedence; routine reversible changes should not create repeated permission requests.

Language: English for repository documentation and prompts. Technology choices remain case-specific; commands must be reproducible from the relevant case directory.

License and copyright ownership must be selected before public release. Attribute book-inspired patterns and any reused official code under its applicable license. Keep purchased source files and raw extracted pages outside the repository.
