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

Project role files live in `.codex/agents/`; each contains `name`, `description`, and `developer_instructions`. These definitions omit model and reasoning overrides and retain resolved parent/default settings. Permissions, provider, and MCP configuration inherit from the parent. Behavioral scopes such as “do not edit” are instructions, not separate filesystem enforcement. [Official subagent configuration documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents)

The active `.codex/config.toml` sets `agents.enabled = true` and `agents.max_concurrent_threads_per_session = 3`, permitting up to three concurrent spawned threads, excluding the parent. It does not require using all three roles. Preserve unrelated settings when extending the configuration. [Official subagent settings](https://learn.chatgpt.com/docs/agent-configuration/subagents)

The three skills are installed under the active root `.agents/skills/`. They retain normal implicit selection and can also be explicitly invoked as `$add-agent`, `$change-agent`, or `$verify-agent`. If a client does not show newly installed skills, restart it. [Official local skill discovery](https://learn.chatgpt.com/docs/build-skills)

Real enforcement belongs in CI and structural checks, configured environment permissions, and demo runtime code. Prompt text cannot prove directory isolation, safe tool execution, termination, or validation quality. Parent review must catch a local-policy conflict rather than treating it as authorized relaxation.

## Validation status

Initialized on 16 October 2026 in Agent Atlas. The original [bootstrap](../agent-library-bootstrap/README.md) and [analysis](../agent-library-analysis/README.md) remain reference snapshots; current governance is maintained in the active root files. The existing MIT license was preserved. No user-level Codex settings were changed.

Local environment: macOS, Python 3.9.6 for governance checks, Python 3.11 for TOML parsing, Ruby's YAML parser, and Codex CLI `0.162.0-alpha.17.2`.

| Check | Result and evidence boundary |
| --- | --- |
| `python3 scripts/check_structure.py` | Passed for the initialized repository, including both retained reference bundles. |
| `python3 -m unittest discover -s scripts -p 'test_*.py'` | 12 governance tests passed: valid scaffolds/records, retained bundles, root runtime resources, missing docs, unowned case resources, escaping symlinks, unsupported readiness, and blank metadata. Synthetic verification records test the checker only. |
| TOML parsing and field assertions | Four files passed; expected role names/fields, delegation settings, and absence of model/provider/permission overrides confirmed. |
| YAML parsing and manifest assertions | All three skill manifests and the GitHub workflow passed. |
| Local Markdown links | All local file/directory links and explicit heading fragments resolved, including the supplied bundles. |
| `codex debug prompt-input` from root and `agents/tool-using/` (the case path on 16 October 2026) | Root instructions and all three skill descriptions appeared in both contexts. Case instructions appeared only from the case directory, as expected. No model turn was submitted. |
| Local app-server `config/read` under `--strict-config` | Effective delegation was enabled with a three-child limit. |
| Local app-server `skills/list` with forced reload | All three project skills were enabled with `repo` scope at both working directories; no skill discovery errors. |

The prompt inspector initially failed inside the filesystem sandbox; the local inspection succeeded with the required filesystem access. `--strict-config` is unsupported by `codex debug`, so strict parsing was checked through the app-server instead.

The three custom role definitions passed syntax/field validation and match the current official format. Standalone custom-role discovery and spawning were not verified: the inspected prompt/config responses do not expose a role registry, and the current session's delegation interface has no custom-role selector. Independent review used ordinary development workers and does not establish custom-role activation.

The [governance workflow](../.github/workflows/structure.yml) is configured but has not run on GitHub. Its checkout action is pinned to the verified [v7.0.1 release commit](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1). These setup checks establish no hosted CI, Agent runtime, live-model, deployment, or publication result.

The Tool-Using case was separately implemented and checked on 16 October 2026. Its [verification record](../agents/07-tool-using/README.md#verification) covers runnable replay, strict tool/result validation, bounded execution, publication rollback, mocked-provider behavior, and both selected live requests against `gpt-6-luna`. It is `demo-ready`; the selected implementation and validation are complete. The [case CI workflow](../.github/workflows/tool-using.yml) runs its locked test suite without provider credentials; hosted execution and deployment remain unverified. Further cases or capabilities require a separate scope.
