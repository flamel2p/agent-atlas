# Initialize the AI Agent Demo Library

Use this task in the target repository or directory you have opened in Codex. Attach the accompanying `repository-template` files and, when useful, the separate book-analysis bundle.

## Initialization task

Initialize this repository as an open-source AI Agent learning-demo collection using the supplied template. Preserve existing files and configuration; reconcile conflicts rather than overwriting unrelated work.

The first selected case is **Tool-Using Agent**. This task initializes repository structure, governance, development workflows, and case documentation. The implementation language and concrete demo scenario remain undecided, so leave the case status **planned** and record those decisions in its specification.

### Repository boundaries

- One independently runnable demo per `agents/<kebab-case-slug>/` directory.
- Keep each case's implementation, dependencies, configuration example, tests, fixtures, prompts, state, generated artifacts, README, and specification within that directory.
- Related roles, tools, and modules belonging to the same demo stay inside its directory. A runtime team or orchestration scenario can be one demo containing local specialists.
- Independently runnable cases get separate directories. Do not import sibling case internals or depend on another case's private files, environment, database, or installation.
- The root contains common governance, the catalogue, templates, and development checks. Do not add an application runtime, central provider client, shared agent framework, root dependency workspace, global credentials, or application database.
- A future shared package or cross-case integration is a separate architecture decision with explicit ownership and consumers; it is not part of this initialization.

### Files to initialize

Use the supplied `repository-template` as the starting point:

```text
README.md
AGENTS.md
CONTRIBUTING.md
.gitignore
.agents/skills/
  add-agent/SKILL.md
  change-agent/SKILL.md
  verify-agent/SKILL.md
.codex/
  config.toml
  agents/
    source_researcher.toml
    agent_builder.toml
    agent_reviewer.toml
docs/CODEX_WORKFLOW.md
scripts/check_structure.py
templates/agent/
  README.md
  AGENTS.md
  SPEC.md
agents/tool-using/
  README.md
  AGENTS.md
  SPEC.md
```

When implementation begins, add `src/`, `tests/`, `fixtures/`, a local dependency manifest/lockfile, and `.env.example` only where applicable. Do not create 30 empty case directories, install a runtime framework, or fill the repository with speculative abstractions.

### Rules and development workflows

Keep root `AGENTS.md` concise and authoritative for repository conventions. Each case's `AGENTS.md` records its scope, local commands, and additional constraints. Local rules supplement the root convention and must not silently relax isolation, evidence, or validation requirements.

Because automatic instruction discovery follows working-directory ancestry, explicitly read the target case's `AGENTS.md`, `SPEC.md`, and README before changing it, even when the main Codex task starts at the root.

Keep `SPEC.md` as the behavior contract. Update it, the implementation, relevant checks, and README together when behavior changes. Distinguish source facts, design proposals, selected decisions, and actual validation evidence. Use original public documentation and source attribution; do not add the purchased PDF or raw extracted book pages to the repository.

Initialize three repo-local skills:

- `add-agent`: add a case from the template, resolve material scope decisions, and update the catalogue.
- `change-agent`: change one case within its specification and synchronize affected implementation, checks, and docs.
- `verify-agent`: run the relevant checks, assess results, update evidence, and close out honestly.

Allow normal implicit skill selection. Users may also invoke `$add-agent`, `$change-agent`, or `$verify-agent` explicitly. Keep workflows in skills and `CONTRIBUTING.md`; avoid duplicating long procedures in every instruction file.

Initialize three development subagent roles:

- `source_researcher`: verify source material and current primary API documentation when evidence is missing or uncertain.
- `agent_builder`: implement one explicitly assigned case with clear owned paths and contracts.
- `agent_reviewer`: independently review substantive behavior changes or a case proposed as `demo-ready`.

The parent Codex selects roles when useful, gives self-contained tasks, prevents overlapping edits, integrates findings, performs final validation, and reports the outcome. Role instructions are behavioral scopes, not hard permission boundaries. Preserve existing permission, approval, model, provider, and MCP configuration. Do not modify user-level Codex settings.

### Enforceable checks

Run `python3 scripts/check_structure.py` using Python 3.9 or later. It checks repository layout, required case documents, case metadata, catalogue links, and required readiness-record fields. It does not prove that recorded commands ran, runtime independence, model quality, credential safety, or correctness.

If this repository is being initialized with GitHub CI, add or reconcile a small CI job that runs the structure checker. Verify the chosen official action versions or immutable revisions before writing the workflow; use minimal permissions and preserve existing jobs. Runtime jobs belong to implemented cases and should run their documented local checks. The template does not include an activated CI workflow.

For later implementations, default automated checks to fixtures and local behavior. A mocked or simulated result is not a live-model result. Live API checks must be explicitly selected, respect the user's existing authorization, and never hide failures or missing credentials. Runtime code must enforce tool contracts, authorization boundaries, stopping limits, and error handling; prompts alone are not enforcement.

### Completion and reporting

Validate TOML and skill manifests, check all local document links, and run the structure checker. Where the installed Codex supports it, confirm project roles and skills are discoverable and that the target case instructions are loaded. Report unsupported or unverified loading separately from syntax checks.

Keep Tool-Using status `planned`; do not claim an implemented or tested demo. Record pending decisions: language/runtime, smallest scenario, model backend, permitted tool effects, and license owner/license selection. Do not fabricate a license or copyright holder, publish, push, or implement other cases as part of this task.

Finish with the resulting structure, checks actually run, remaining decisions, and the single next step: select the Tool-Using implementation contract.

## Official configuration references

Template configuration was checked against current official documentation on 14 October 2026. Recheck compatibility with the installed Codex during initialization.

- [AGENTS.md instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Repo-local skills](https://learn.chatgpt.com/docs/build-skills)
- [Custom subagent definitions](https://learn.chatgpt.com/docs/agent-configuration/subagents)
