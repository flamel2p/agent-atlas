# AI Agent Demo Library: Source Analysis and Development Handoff

This English reference bundle supports the independent design of runnable learning demos inspired by *30 Agents Every AI Engineer Must Build*, Imran Ahmad, Packt, March 2026, ISBN 978-1-80610-901-2.

Status: source analysis and proposed development direction. No agent implementation, dependency installation, runtime validation, repository creation, or publication was performed.

## Start here

1. Read [the verified inventory](agent-inventory.md) to understand the agent names, source locations, and coverage differences.
2. Use [the shared foundations](foundations.md) as a design reference. Select capabilities required by a scenario rather than implementing every capability in every demo.
3. Read the relevant brief under [agents/](agents/) before designing that demo. Each brief separates source evidence, missing information, and proposed implementation choices.
4. Use [the development roadmap](implementation-roadmap.md) to turn a selected brief into a bounded implementation task.

Selected first case: [Tool-Using Agent](agents/07-tool-using.md). Its tool-selection and execution boundaries make the control flow easy to inspect and verify. Repository governance and per-case ownership are being established before implementation; the runtime and concrete scenario remain undecided.

## Coverage and source differences

The uploaded PDF has 542 physical pages; text was extracted from 528. Some pages are blank or rely on graphical content. Relevant diagrams were inspected selectively; the bundle is not an exhaustive audit of every figure.

The official repository lists 30 reference agents. The PDF develops corresponding sections for 29 of those entries. Its Chapter 16 also develops Domain-Transforming Integration, outside the official numbered list. This produces 30 developed pattern sections in the PDF, with a different composition from the official list.

- Reference 14 is titled **Compliance-Driven agents** in the PDF and **Security-Hardened Agent** in the official list. The overlap does not establish that all described capabilities are equivalent.
- Reference 18, **Recommendation Agent**, appears in the Preface's Chapter 10 synopsis, but no dedicated body section or developed architecture was located. Its brief records the evidence gap rather than inventing a source-derived implementation.
- [Domain-Transforming Integration](agents/extra-domain-transforming-integration.md) is supplemental to the official numbered list.

The [inventory](agent-inventory.md) is the detailed record of these differences. Numeric IDs are official-list reference IDs, not a claim that the PDF explicitly numbers every agent in the same way.

## How to interpret the documents

- **Source fact:** established by the supplied PDF at an identified location.
- **Inference:** an interpretation connecting source material; review it before treating it as a requirement.
- **Proposed demo or acceptance check:** a suggested implementation choice created during this analysis. It is not book evidence, approved product scope, or an executed test.
- **Not specified:** an implementation decision or supporting detail missing from the source.

Page references distinguish the printed page number from the one-based physical PDF page. Use the explicit locators in the documents rather than assuming external errata use the same pagination. The inspected numbered body pages use a physical-page offset of 31; front matter has a separate labeling scheme.

Technology names and versions describe what the book contains. Before implementation, verify the selected libraries, model interfaces, and API contracts against current primary documentation. Report simulation, mocked integration, and live model outcomes separately.

## Evidence quality

The book combines architecture descriptions, code listings, cross-agent case studies, and illustrative material. A code listing is not automatically a complete executable example. The briefs record important missing pieces and inconsistencies, including placeholder behavior and cases where prose, diagrams, and code do not establish the same contract.

Business metrics and domain claims reported by the book have not been independently verified. The clinical, legal, financial, and physical-world briefs are learning references; their proposed demos use bounded synthetic or simulated scenarios.

## Independent project direction

Recommended audience: developers learning agent engineering through small runnable scenarios with inspectable architecture and meaningful checks.

Recommended incremental value:

- One clear scenario, input contract, and observable output per demo.
- A documented control flow, tool boundary, stopping rule, and failure path.
- Reproducible setup and explicit configuration.
- Honest validation status and limitations.
- Original explanations connecting design choices to the implemented behavior.

The implementation language remains a user decision. Python is the initial recommendation because the book's examples use it. A TypeScript implementation can also be selected deliberately; preserve the architectural lesson rather than mechanically translating source code.

Each demo owns its code and dependencies in a separate directory. Root files contain shared governance and development tooling. A common runtime or cross-case package would be a separately scoped architecture decision, justified by implemented cases.

## Publication boundary

This bundle is an analysis handoff. Prepare public explanations around the actual independent implementations and their verified behavior. Keep the purchased PDF and extracted page text out of the public repository. If official code is reused later, inspect and preserve its applicable license and attribution.

Primary comparison references:

- [Official companion repository and reference list](https://github.com/PacktPublishing/30-Agents-Every-AI-Engineer-Must-Build)
- [Official repository license](https://github.com/PacktPublishing/30-Agents-Every-AI-Engineer-Must-Build/blob/main/LICENSE)

The companion code was not executed during this analysis.
