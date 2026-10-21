# Agent Atlas

Independently runnable learning demos with explicit architecture, tool boundaries, execution flow, and validation evidence.

## Catalogue

| Case | Pattern | Status | Runtime | Evidence |
| --- | --- | --- | --- | --- |
| [Autonomous Decision-Making Agent](agents/01-autonomous-decision-making/README.md) | Contextual autonomy routing with host policy | demo-ready | Python 3.14 (uv CLI) | 11 replay examples, 123 fixture/mocked-provider checks, isolated install, and independent review passed; live model unverified |
| [Planning Agent](agents/02-planning/README.md) | Validated task DAG, resource scheduling, and adaptive replanning | demo-ready | Python 3.14 (uv CLI) | 5 replay scenarios, 98 fixture/CLI/mocked-provider checks, isolated install, and independent review passed; live model unverified |
| [Memory-Augmented Agent](agents/03-memory-augmented/README.md) | Scoped persistent memory, explicit preference correction, and grounded FAQ recall | demo-ready | Python 3.14 (uv CLI) | 108 fixture/CLI/mocked-provider checks, cross-process recall, isolated install, and independent review passed; live model unverified |
| [Knowledge Retrieval Agent](agents/04-knowledge-retrieval/README.md) | Filtered lexical retrieval and exact evidence citations | demo-ready | Python 3.14 (uv CLI) | 181 fixture/CLI/mocked-provider checks, 12 CLI scenarios, case-only install/wheel, and independent review passed; live model unverified |
| [Document Intelligence Agent](agents/05-document-intelligence/README.md) | Invoice field extraction with spatial evidence and explicit review | demo-ready | Python 3.14 (uv CLI, POSIX) | 110 fixture/CLI/mocked OCR checks, case-only install/wheel, and independent review passed; real OCR unverified |
| [Scientific Research Agent](agents/06-scientific-research/README.md) | Bounded lexical literature mapping with exact abstract evidence | demo-ready | Python 3.14 (uv CLI, POSIX) | 36 fixture/CLI checks, 10 CLI scenarios, case-only install/wheel, and independent review passed; synthetic corpus only |
| [Tool-Using Agent](agents/07-tool-using/README.md) | Tool selection and guarded execution | demo-ready | Python 3.14 (uv CLI) | 133 fixture/mocked-provider checks, 3 replay paths, isolated checkout, and independent review passed on 20 Oct; two live examples passed on 16 Oct |
| [Chain-of-Agents Orchestrator](agents/08-chain-of-agents-orchestrator/README.md) | Typed specialist handoffs, manager-owned context, and explicit evidence conflict review | demo-ready | Python 3.14 (uv CLI) | 104 fixture/CLI/fault checks, 8 installed-wheel scenarios, case-only install, and independent review passed; no LLM or runtime network |
| [Typed Decision Agent (#31)](agents/31-typed-decision/README.md) | Jev-inspired typed predictions with explicit uncertainty | planned | undecided | Source research and scope only; no runnable implementation or model validation |
| [MCP Server Builder Agent (#32)](agents/32-mcp-server-builder/README.md) | OpenAPI-guided tool design and standalone MCP server generation | planned | Python (uv CLI; planned) | Contract and implementation plan only; no builder or generated-server validation |

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

Initialized on 16 October 2026 with governance and a runnable Tool-Using case. Its replay, mocked-provider checks, and two selected live requests passed; see [Tool-Using verification](agents/07-tool-using/README.md#verification).

Completed Agent 07 alignment on 20 October 2026. The existing Tool-Using case now lives at `agents/07-tool-using/`, with its original command, behavior, and live evidence preserved. Added reviewer explanations, a source reading guide, and case-local ignore rules. Its 133 fixture/mocked-provider tests, three replay paths, and isolated checkout passed again. See the [completion plan](agents/07-tool-using/SPEC.md#agent-07-completion-plan) and [current checks](agents/07-tool-using/README.md#agent-07-completion-checks).

Added Autonomous Decision-Making on 18 October 2026: synthetic support triage with deterministic policy, one read-only status observation, and autonomous/guided/handoff outcomes. Its 11 replay examples, 123 fixture/mocked-provider checks, independent review, and case-only installation passed. Optional OpenAI mode is implemented; live compatibility remains unverified. See [Autonomous Decision-Making verification](agents/01-autonomous-decision-making/README.md#verification) and [setup validation](docs/CODEX_WORKFLOW.md#validation-status).

Added [Planning Agent](agents/02-planning/README.md) on 18 October 2026: a synthetic documentation-release DAG with parallel work, capacity enforcement, resource-change observations, and validated replanning. Its five replay scenarios, 98 fixture/CLI/mocked-provider checks, case-only installation, and independent review passed. Optional OpenAI planning is implemented; live model behavior remains unverified. See [Planning verification](agents/02-planning/README.md#verification).

Added [Memory-Augmented Agent](agents/03-memory-augmented/README.md) on 19 October 2026: a synthetic study assistant with SQLite preference and episode memory, read-only FAQ evidence, correction, retention, and scoped forgetting. Its 108 fixture/CLI/mocked-provider checks, separate-process recall, case-only installation, documented walkthrough, and independent review passed. Optional OpenAI evidence selection is implemented; live model behavior remains unverified. See [Memory-Augmented verification](agents/03-memory-augmented/README.md#verification).

Added [Knowledge Retrieval Agent](agents/04-knowledge-retrieval/README.md) on 19 October 2026: a synthetic support corpus with access/version/freshness filters, overlapping paragraph chunks, BM25 retrieval, explicit evidence gaps and exact source citations. Its 181 fixture/CLI/mocked-provider checks, 12 independent CLI scenarios, case-only suite, installed-wheel execution and independent review passed. Optional OpenAI passage selection is implemented; live model behavior remains unverified. See [Knowledge Retrieval verification](agents/04-knowledge-retrieval/README.md#verification).

Added [Document Intelligence Agent](agents/05-document-intelligence/README.md) on 20 October 2026: invoice number, date, and MYR total extraction with page/token/box evidence, explicit uncertainty and conflict review, and an optional bounded Tesseract adapter. Its 110 fixture/CLI/mocked OCR checks, isolated case install, installed-wheel execution, and independent review passed. Tesseract is absent locally, so real OCR recognition remains unverified. No LLM or external posting is used. See [Document Intelligence verification](agents/05-document-intelligence/README.md#verification).

Added [Scientific Research Agent](agents/06-scientific-research/README.md) on 20 October 2026: deterministic search and thematic grouping over original synthetic paper metadata, with exact abstract offsets, hashes, duplicate accounting, and explicit interpretation limits. Its 36 fixture/CLI tests, 10 CLI scenarios, case-only installation, installed-wheel execution, and independent review passed. It uses no LLM or runtime network and does not assess scientific consensus, study quality, or research gaps. See [Scientific Research verification](agents/06-scientific-research/README.md#verification) and [design plan](agents/06-scientific-research/DESIGN.md).

Added [Chain-of-Agents Orchestrator](agents/08-chain-of-agents-orchestrator/README.md) on 21 October 2026. Three deterministic release-evidence roles use typed handoffs, immutable shared context, exact record provenance, and explicit conflict/missing-evidence review. All 104 fixture/CLI/fault checks, case-only installation, eight installed-wheel scenarios, and independent review passed. The manager owns deadlines and cancellation cleanup. This simulation uses no LLM, persistent memory, or runtime network. See the [implementation plan](agents/08-chain-of-agents-orchestrator/PLAN.md) and [verification evidence](agents/08-chain-of-agents-orchestrator/README.md#verification).

Registered [#31 Typed Decision Agent](agents/31-typed-decision/README.md) on 18 October 2026 as a planned, independently designed case inspired by TypeSafe AI's Jev. Its next step is selecting a probability-producing backend and evaluation data before implementation. The retained book inventory and supplemental pattern remain unchanged; #31 is a project extension.

Planned [#32 MCP Server Builder Agent](agents/32-mcp-server-builder/README.md) on 21 October 2026. It will use an OpenAPI contract and desired tasks to propose a small tool set, generate a standalone stdio server, and check the generated artifact against a synthetic service. The [implementation plan](agents/32-mcp-server-builder/PLAN.md) starts with a fixture and SDK/isolation feasibility check. No runtime, live-model, real-service, or deployment evidence exists yet.

## License

The existing [MIT license](LICENSE), copyright (c) 2026 Ekko, is preserved. Attribute any reused third-party code under its applicable license; the repository license does not grant rights to the source book.
