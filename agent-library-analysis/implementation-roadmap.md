# Development Roadmap

Source: *30 Agents Every AI Engineer Must Build*, Imran Ahmad, Packt, March 2026. Read [the inventory](agent-inventory.md), [foundations](foundations.md), and the selected source brief before using this roadmap.

Status: proposed implementation direction. This document does not add requirements to the book or report completed development. No runtime checks were performed.

## Objective

Create an open-source collection of independently runnable AI Agent learning demos. Each demo should demonstrate a specific architectural pattern, explain its input-to-output flow, and provide observable evidence of its behavior and limits.

The original 30-agent collection is a coverage target. Source gaps and supplemental patterns remain visible in the inventory. The Recommendation Agent requires an independently researched and designed specification if it is selected later; the supplied book does not provide a developed case to extract.

## Decisions before the first implementation

The user selected the [Tool-Using Agent](agents/07-tool-using.md) as the first case and requested repository governance before implementation. Confirm its implementation language next; Python remains a recommendation, not a selected runtime.

Then decide, for that case only:

- The smallest coherent scenario and fixture data.
- The execution surface; a CLI is the initial recommendation for developer-oriented demos.
- The model backend and whether a deterministic demonstration mode is useful.
- Permitted tool effects and the location of generated outputs.
- The stopping rule, failure behavior, and observable acceptance checks.

Do not choose a universal framework, memory system, database, deployment platform, or multi-provider abstraction merely because the collection will eventually contain many cases. Select them when an implemented scenario establishes the need.

## Recommended first sequence

| Order | Pattern | Why it is useful early | Proposed observable result |
| --- | --- | --- | --- |
| 1 | [Tool-Using](agents/07-tool-using.md) | Makes model-selected actions, tool contracts, execution, and validation inspectable. | A bounded fixture-based task produces the expected result and a record of tool calls; an invalid tool request is handled explicitly. |
| 2 | [Planning](agents/02-planning.md) | Adds task dependencies, execution monitoring, and a bounded response to changed conditions. | A multi-step fixture task completes in a valid order; an injected failure produces a defined replan, escalation, or stop. |
| 3 | [Knowledge Retrieval](agents/04-knowledge-retrieval.md) | Adds data provenance, retrieval quality, and unsupported-answer handling. | Questions over a small corpus produce traceable evidence; insufficient evidence produces a clear unresolved result. |

These scenarios and checks are proposals. The source briefs describe the book's patterns; the final implementation task must record which proposed choices the user selected.

## Definition of a complete learning demo

1. **Scope:** the intended user, goal, inputs, outputs, and limits are explicit.
2. **Architecture:** implemented components, state, tool boundaries, and data flow are documented in an original diagram or concise flow description.
3. **Control flow:** the relevant selection, planning, execution, validation, stopping, and escalation behavior is observable. Document decisions and tool results without requiring disclosure of private model reasoning.
4. **Setup:** the entry point, dependencies, fixture data, configuration, and required credentials are documented. Secrets are absent from examples and committed files.
5. **Validation:** meaningful checks cover the architectural lesson and at least one important failure or limit. Separate deterministic fixture checks from mocked provider checks and actual live model runs.
6. **Documentation:** commands, sample inputs, expected outputs, failure behavior, source attribution, implementation decisions, and checks actually run are recorded.

A runnable demo is a learning milestone. Broader production qualification needs evidence specific to the eventual deployment and domain.

## Implement one case at a time

For each selected case:

1. Read its source brief and validate the cited source locations when a design depends on them.
2. Resolve material missing contracts before implementation. Routine choices can use the selected case's scope and the repository's conventions.
3. Verify the chosen APIs and dependency versions using current primary documentation.
4. Record a short implementation specification: selected scenario, architecture, tool contracts, state, flow, stopping rules, failure behavior, and acceptance checks.
5. Build and validate the smallest complete demo.
6. Rewrite the README around the actual resulting behavior and evidence.
7. Extract common code only when completed demos show a stable repeated need.

## Suggested repository shape

This is a proposed structure to refine after selecting the language and first case:

```text
README.md
docs/
  principles.md
  agent-index.md
  decisions/
agents/
  tool-using/
    README.md
    fixtures/
    src/
    tests/
  planning/
  knowledge-retrieval/
templates/agent/        # Common case documentation and governance templates.
```

Dependency manifests, configuration, and test conventions should follow the selected language. Use original public documentation describing the actual demos; maintain detailed source-analysis material separately when it is useful for development.

## Reusable Codex task template

Fill in the selected case and approved decisions before handing this task to an implementation chat. Provide the relevant documents or their accessible paths with the task.

> Implement one independently runnable AI Agent learning demo for **[selected case]** using **[selected language and runtime]**.
>
> The learning objective is **[architectural behavior to demonstrate]**. The selected scenario is **[scenario]**, with inputs **[input contract]**, outputs **[output contract]**, and permitted tool effects **[tool boundary]**.
>
> Read the provided foundations, inventory, and case brief. Treat book facts, inferences, proposed demo choices, and missing details as distinct evidence categories. Use the approved choices in this task as the implementation scope. Resolve any material missing contract before implementing dependent behavior.
>
> Verify chosen APIs against current primary documentation. Implement the bounded flow, state, stopping condition, and failure behavior. Add meaningful checks for **[normal path]** and **[important failure or limit]**, then run the relevant checks.
>
> Deliver the implementation with original architecture and flow documentation, reproducible setup, example input/output, source attribution, and a clear record of checks actually run. Distinguish deterministic, mocked-provider, and live-model validation. Implement only the selected demo; other cases remain roadmap items.

## Current handoff status

- Source analysis: provided in this bundle.
- First case: Tool-Using Agent selected; repository governance comes first.
- Implementation language and concrete scenario: awaiting selection.
- Current dependency/API verification: pending implementation choices.
- Agent code, repository, runtime validation, and publication: not performed.
