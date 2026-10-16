# Repository Bootstrap Handoff

This English package defines the repository structure and development conventions requested before implementing the first Tool-Using Agent demo.

## Use this package

1. Open the intended repository or directory in Codex.
2. Provide [INITIALIZE_WITH_CODEX.md](INITIALIZE_WITH_CODEX.md) and the `repository-template/` folder.
3. Ask Codex to apply the initialization task, preserve existing work, and verify discovery in that target environment.
4. Select the Tool-Using language and concrete contract before implementing its runtime.

The template is a staged deliverable. It has not been applied to a Git repository, installed into user settings, activated in Codex, or published.

## Boundaries

- One independently runnable case per `agents/<slug>/`.
- Related components stay inside that case; unrelated cases remain independent.
- Local implementation, dependency manifests, configuration, tests, fixtures, and artifacts.
- Root governance, catalogue, templates, and development checks.
- No shared application runtime or sibling-case imports initially.
- Specification, implementation, meaningful checks, and documentation move together.
- Evidence modes remain distinct; readiness records never replace actual checks.

## Development customization

Three project skills: `add-agent`, `change-agent`, `verify-agent`.

Three development roles: `source_researcher`, `agent_builder`, `agent_reviewer`. The main Codex chooses useful roles, owns integration, and closes out. These role files describe behavior and inherit parent permissions; they do not create independent hard security boundaries.

Current paths and configuration conventions were verified using official documentation:

- [Instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Skills](https://learn.chatgpt.com/docs/build-skills)
- [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)

## Validation performed

On 14 October 2026:

- Four TOML files parsed successfully; role names and required fields checked.
- Three skill manifests passed the bundled skill-creator validator.
- The template passed its structure checker.
- Local Markdown links resolved.
- Eight structure-check fixtures passed, covering a valid recorded-metadata example plus missing specification, root runtime resource, unowned `agents/` file, hidden unowned directory, unsupported readiness/status mismatch, absent verification record, and an escaping symlink.
- Independent static review identified two checker gaps; both were repaired and exercised by failure fixtures.

The validation is for this scaffold and its checker. Codex role/skill loading, target CI execution, runtime Agent behavior, live provider calls, and deployment remain unverified. Tool-Using stays `planned`.

Pending implementation decisions: runtime, scenario, backend, exact contracts/limits, and license/copyright ownership.
