# Agent Atlas

Independently runnable learning demos with explicit architecture, tool boundaries, execution flow, and validation evidence.

## Catalogue

| Case | Pattern | Status | Runtime | Evidence |
| --- | --- | --- | --- | --- |
| [Autonomous Decision-Making Agent](agents/01-autonomous-decision-making/README.md) | Contextual autonomy routing with host policy | demo-ready | Python 3.14 (uv CLI) | 11 replay examples, 123 fixture/mocked-provider checks, isolated install, and independent review passed; live model unverified |
| [Tool-Using Agent](agents/tool-using/README.md) | Tool selection and guarded execution | demo-ready | Python 3.14 (uv CLI) | Replay, mocked-provider checks, and two live gpt-6-luna examples passed |

## Use a demo

Open its directory and follow its README. Each case owns its dependencies, configuration, fixtures, tests, and artifacts. There is no shared application runtime or global credential configuration.

## Development

Read [repository rules](AGENTS.md), [contribution workflow](CONTRIBUTING.md), and [Codex workflow](docs/CODEX_WORKFLOW.md). Use the [case template](templates/agent/) for additions. Run the common structure check with `python3 scripts/check_structure.py` (Python 3.9+; no packages required).

Project-local workflows: `$add-agent`, `$change-agent`, and `$verify-agent`. Development roles: `source_researcher`, `agent_builder`, and `agent_reviewer`.

Patterns may be inspired by *30 Agents Every AI Engineer Must Build* by Imran Ahmad, Packt, March 2026. Source facts and implementation choices remain distinct. The collection can grow beyond the book; it does not need to preserve book numbering in directory names.

## Source references

- [Analysis bundle](agent-library-analysis/README.md): [inventory](agent-library-analysis/agent-inventory.md), [foundations](agent-library-analysis/foundations.md), case briefs, and a proposed [roadmap](agent-library-analysis/implementation-roadmap.md).
- [Bootstrap handoff](agent-library-bootstrap/README.md): the original initialization instructions and repository template.

Both supplied bundles are retained as reference snapshots. Their historical setup-status statements describe the handoff; current project status lives here and in the active case specifications. Maintain governance in the root files, `.agents/`, `.codex/`, `docs/`, `scripts/`, and `templates/`. Maintain demos in `agents/`.

The inventory preserves the Security-Hardened/Compliance-Driven naming difference, Recommendation Agent's missing developed source coverage, and the supplemental Domain-Transforming Integration pattern. Source analysis is not executed-demo evidence. Purchased source files and raw extracted book pages do not belong in this repository.

## Status and next step

Initialized on 16 October 2026 with governance and a runnable Tool-Using case. Its replay, mocked-provider checks, and two selected live requests passed; see [Tool-Using verification](agents/tool-using/README.md#verification).

Added Autonomous Decision-Making on 18 October 2026: synthetic support triage with deterministic policy, one read-only status observation, and autonomous/guided/handoff outcomes. Its 11 replay examples, 123 fixture/mocked-provider checks, independent review, and case-only installation passed. Optional OpenAI mode is implemented; live compatibility remains unverified. See [Autonomous Decision-Making verification](agents/01-autonomous-decision-making/README.md#verification) and [setup validation](docs/CODEX_WORKFLOW.md#validation-status). Both cases are complete for their selected acceptance criteria; further capabilities need their own scope.

## License

The existing [MIT license](LICENSE), copyright (c) 2026 Ekko, is preserved. Attribute any reused third-party code under its applicable license; the repository license does not grant rights to the source book.
