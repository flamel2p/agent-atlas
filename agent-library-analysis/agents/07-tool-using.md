# The Tool-Using agent pattern

**Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 7, “Tool Manipulation and Orchestration Agents,” “The Tool-Using agent pattern,” with its selection/recovery subsections. **Reference ID:** 07. **Locators:** printed pages; 1-based physical PDF pages. **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose, boundaries, inputs and outputs

The pattern turns a natural-language goal into calls to a predefined tool chest. Its user can request a calculation, live-data lookup, or chart without directly invoking APIs. Inputs are the request, available-tool metadata/contracts, and task data; outputs are tool results and a final artifact. Success means the selected tools perform the intended operation with valid arguments and traceable execution. A tool returning without exception does not establish semantic correctness.

## Source architecture

Four components are explicit: reasoning core for Think/Plan, registry for names/descriptions/input-output schemas, execution engine for state/retries/errors, and guarded functions in the tool chest. Selection can use intent classification, embedding similarity, permissions/type/status filtering, plan-driven assignment, and reranking after failure. The three-stage funnel narrows by intent, ranks semantically, then enforces constraints. Working state passes intermediate outputs between calls; temporary failure memory prevents repeated use of failing tools. JSON schemas/Pydantic are contract options. LLM reasoning is the architectural definition, but the concrete visualization example uses keyword rules.

## Input-to-output flow

1. Parse the user goal into an intent and required result.
2. Consult tool metadata and filter/rank candidates against operational constraints.
3. Construct a direct call or a multi-step plan.
4. Validate arguments and execute selected tools, carrying intermediate state forward.
5. On failure, use targeted retry/backoff, an alternative tool, confidence-based switching, or temporary exclusion of failing tools where configured.
6. Return the result; if automated recovery is exhausted, pause and escalate with attempted tools/errors and original context.

The sample path parses metric/dimension/chart type, loads CSV, aggregates, and renders bar/line output. Unsupported parsing aborts with an error. The conceptual recovery stack exceeds the implementation shown.

## Source implementation and evidence

Python functions use pandas and plotting through `plt`, followed by a rule-based parser and sequential orchestrator. Type hints are described as interface contracts; there is no actual dynamic schema registry or LLM selection implementation in this sample. No exact model or package versions are supplied. The chapter summary calls the visualization code executable, but that should not imply it implements semantic search, circuit breaking, or durable orchestration. Imports/adapters and plotting dependencies must be verified before later execution.

## Failures, constraints and recovery

The source distinguishes input/schema errors, runtime failures, semantic mismatch, and unavailable/deprecated tools. Recommended responses include validation, retries/timeouts, fallback chains, logging, and human review. One sample boundary needs repair: after aggregation returns `None`, an already populated DataFrame remains in state, so the orchestrator may continue with stale data rather than abort the failed step. Rules also default unknown aggregation requests to sum. Recovery intent is broader than the code’s actual failure behavior.

## Proposed minimal demo — implementation proposal

Provide an allowlisted CSV-summary tool set and a bounded request-to-chart workflow over synthetic campaign data. **Normal check:** a recognized comparison request invokes load → aggregate → plot in order and produces correct totals. **Limit check:** a missing column stops downstream plotting and returns a structured error with the failing tool. These checks are future design options.

## Missing decisions

Choose real LLM versus rule-based selection, schemas, tool allowlist, retry limits, permission checks, output paths, error protocol, and semantic result validation.

## Supporting source locations

- Ch. 7, pattern/components/function contracts: printed 174–179; PDF 205–210.
- Ch. 7, selection funnel/strategies/parser: printed 179–183; PDF 210–214.
- Ch. 7, failure categories/recovery/orchestrator: printed 183–186; PDF 214–217.
