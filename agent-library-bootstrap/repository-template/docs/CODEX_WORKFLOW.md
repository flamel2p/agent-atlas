# Codex development workflow

This configuration defines coding assistants used to develop the library. The runtime agents demonstrated by `agents/<slug>/` are separate application code. They do not load these Codex roles as their architecture.

## Ownership and autonomy

Each demo owns its implementation, dependencies, tests, fixtures, README, and specification inside `agents/<slug>/`. Root files contain governance, catalog, templates, and development tooling. Initially, demos have no cross-case imports or shared Agent runtime.

The parent Codex session owns scope and integration. It supplies each worker a self-contained task with the objective, case slug, approved contract, source/reference paths, owned write paths, expected outputs, and relevant checks. It collects findings, resolves scope decisions, checks the final diff, runs relevant final validation, and reports remaining gaps.

Proceed autonomously with routine authorized local work. Clarify material contract changes, cross-case/root scope changes, essential missing inputs, or secret/external-action authority. A local implementation task does not implicitly authorize publication, live business operations, or disclosure of credentials.

## Instructions and discovery

Before acting on a case, the parent explicitly reads its `agents/<slug>/AGENTS.md` and `SPEC.md`, plus root guidance and referenced policies. It passes the applicable paths and constraints to workers, which also read them. For a new case, read the designated templates before creating the local files.

Codex's automatic instruction discovery follows project-root-to-current-directory ancestry, so a session started at root does not automatically load every descendant case file. More deeply discovered instructions override earlier conflicting guidance. This library's convention is that local policy adds case details and cannot weaken root governance; keep files consistent rather than relying on root text to have special platform precedence. [Official AGENTS.md discovery documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md)

## Roles and skills

| Role | Use when | Expected result |
| --- | --- | --- |
| `source_researcher` | Book evidence or current API behavior needs checking | Cited facts, source gaps, discrepancies, and compatibility decisions |
| `agent_builder` | One approved case needs implementation or a bounded change | Scoped artifacts, checks, and accurate local documentation |
| `agent_reviewer` | Independent assessment of a meaningful diff is useful | Actionable file/line findings and validation limits |

The reusable workflows live in `.agents/skills/add-agent/`, `.agents/skills/change-agent/`, and `.agents/skills/verify-agent/`. Use the matching skill for adding, changing, or verifying a case. Roles define responsibilities and reporting boundaries; skills hold the procedural workflow.

Use workers when they improve speed or independent scrutiny. A trivial change does not need three ceremonial agents. Keep research and non-overlapping work parallel where useful; review a stable diff after edits. Avoid simultaneous edits to the same file. The parent coordinates workers directly; workers do not create nested teams.

## Applying the configuration

Project role files live in `.codex/agents/`; each contains `name`, `description`, and `developer_instructions`. These templates omit model and reasoning overrides and retain resolved parent/default settings. Permissions, provider, and MCP configuration inherit from the parent. Behavioral scopes such as “do not edit” are instructions, not separate filesystem enforcement. [Official subagent configuration documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents)

Merge the two `[agents]` settings from `.codex/config.toml` into an existing project config, preserving unrelated settings and reconciling any legacy `max_threads` alias. `enabled = true` permits delegation; `max_concurrent_threads_per_session = 3` caps concurrent spawned threads, excluding the parent. It does not require using all three roles. [Official subagent settings](https://learn.chatgpt.com/docs/agent-configuration/subagents)

Real enforcement belongs in CI and structural checks, configured environment permissions, and demo runtime code. Prompt text cannot prove directory isolation, safe tool execution, termination, or validation quality. Parent review must catch a local-policy conflict rather than treating it as authorized relaxation.

## Validation status

Prepared as staged templates. The four TOML files were parsed and statically checked for required fields, role names, omitted override settings, and the three-child limit. The documentation was checked against the linked official pages. No Codex loading, role spawning, skill activation, project initialization, dependency installation, runtime demo test, or publication has been performed. After applying the scaffold, verify effective instructions and role discovery in the target Codex client before relying on the configuration.
