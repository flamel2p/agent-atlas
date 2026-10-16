# The chain-of-agents orchestrator

**Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 7, “Tool Manipulation and Orchestration Agents,” “The chain-of-agents orchestrator,” plus shared-memory/arbitration subsections. **Reference ID:** 08. **Locators:** printed pages and 1-based physical PDF pages. **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose, boundaries, inputs and outputs

A manager divides a multifaceted request among specialist agents and synthesizes their findings. Intended users need complementary expertise or heterogeneous data sources. Inputs are a task, registered capabilities, shared context, and specialist outputs. Outputs are coordinated results and a consolidated report with conflicts or review needs exposed. Success depends on consistent context, dependency management, structured communication, and defensible synthesis. Multiple agent functions do not by themselves provide durable collaboration.

## Source architecture

The cooperation protocol has roles/capabilities, communication infrastructure, shared context, and supervisor orchestration. A message envelope includes sender, recipient, task ID, and payload; role registration, typed delegation, and pending/running/done/error statuses govern coordination. RPC, queues, and shared stores are possible transports. Working memory holds immediate context; vector-indexed episodic and semantic stores provide history and durable facts. An arbiter detects conflicting outputs, checks trusted evidence, estimates confidence, and escalates unresolved cases. MCP/A2A are discussed as emerging interoperability standards; the chapter does not implement either protocol.

## Input-to-output flow

1. Receive the task and load relevant long-term context into working memory.
2. Select specialists from declared roles/capabilities and delegate typed requests.
3. Track status and dependencies; receive structured outputs.
4. Record findings in episodic memory and make relevant context available to downstream specialists.
5. Synthesize results, checking for divergence.
6. If disagreement is detected, consult trusted sources through arbitration; accept sufficiently confident consensus or route to human review.
7. Log inputs, confidence, decisions, and rationale with the final report.

These are text-supported stages. Exact concurrency policy, timeouts, task cancellation, and manager termination are unspecified.

## Source implementation and evidence

The market-intelligence example has Python NewsAgent, FinancialAgent, and SentimentAgent functions returning common `source/status/data` dictionaries. Their values/headlines are hardcoded; external API calls appear only as commented possibilities. The manager’s memory writes and LLM analyst retrieval are described in prose. A separate ManagerAgent method sketches synthesis/conflict scoring, rather than a complete runnable manager with persistent stores and arbitration. No specific model/version or real provider is established.

## Failures, constraints and recovery

The conceptual conflict detector uses similarity thresholds; arbitration combines trusted data, confidence policy, logging, and human escalation. Those are design descriptions, not calibrated evidence. The sample conflict code expects `change_pct` and `sentiment_score`, but earlier specialists return neither key in that form: financial output lacks change percentage and sentiment uses `score`. It calculates discrepancy and flags it; it does not implement evidence-based resolution or the human branch. The normalized financial scale also assumes typical price movements. Treat the market narrative as an example, not investment advice or measured business performance.

## Proposed minimal demo — implementation proposal

Coordinate three fixture-based specialists that summarize synthetic product release notes, test outcomes, and user feedback. **Normal check:** the manager receives all typed outputs and creates a report with source IDs. **Limit check:** contradictory version statuses produce an unresolved-conflict review item instead of silently choosing a specialist. These are proposals only.

## Missing decisions

Define message/output schemas, shared-memory ownership, task status semantics, orchestration framework, conflict definition, evidence hierarchy, arbiter confidence calibration, and escalation/timeout policy.

## Supporting source locations

- Ch. 7, orchestrator/cooperation protocol: printed 186–188; PDF 217–219.
- Ch. 7, memory architecture/market specialists: printed 188–191; PDF 219–222.
- Ch. 7, arbitration and sample synthesis: printed 191–194; PDF 222–225.
- Ch. 7, implementation-depth summary: printed 200; PDF 231.
