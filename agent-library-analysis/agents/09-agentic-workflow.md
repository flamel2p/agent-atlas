# The agentic workflow system

**Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 7, “Tool Manipulation and Orchestration Agents,” “The agentic workflow system.” **Reference ID:** 09; reference alias: Agentic Workflow agent. **Locators:** printed pages; 1-based physical PDF pages. **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose, boundaries, inputs and outputs

This pattern supports long-running business processes that need branching, persistent state, recovery, and human checkpoints. Inputs are a business record, data needed for validation, risk judgments, and human/external events. Outputs are a final workflow state plus traceable actions and decisions. The source illustrates e-commerce orders and insurance claims. Success means governed progress through valid transitions, with routine cases automated and uncertain/high-risk cases reviewed. Operational speed and regulatory compliance are architectural goals, not validated outcomes here.

## Source architecture

A workflow manager represents the process as a state machine or graph. Deterministic tools coexist with intelligent nodes; guards choose transitions and checkpoints suspend processing for humans or external events. State/record updates and audit logs carry context. LangGraph and CrewAI are named orchestration options. The insurance illustration assigns intake/OCR, validation, classification, payout, and escalation responsibilities to specialists. Persistent storage, event delivery, transaction semantics, and rollback implementation are not supplied.

## Input-to-output flow

1. Ingest and validate the record; failure can terminate the workflow.
2. Assess risk using an intelligent node or a stated fallback.
3. Route medium/high-risk orders to explicit human approve/reject input; rejection stops, approval resumes.
4. For the e-commerce happy path, reserve inventory and process payment.
5. In the insurance state machine, advance Intake → Validating → Assessing Risk; low risk with adequate confidence moves to Processing Payout.
6. Low confidence/high risk moves to Pending Human Review; approval returns to payout and rejection closes the claim rejected.
7. Record each transition and close approved after successful payment; the depicted insurance flow closes rejected on payment failure.

The 0.85 claim-confidence threshold is an example guard, not a generally validated policy. Waiting/restock and rollback paths are raised as requirements for richer workflows, not implemented branches.

## Source implementation and evidence

Python e-commerce snippets show validation, a risk-analysis stub, inventory/payment function calls, exception handling, and a console `input()` human gate. OpenAI GPT is mentioned but no model/version or complete API invocation is given in the risk snippet. With no API key, the shown fallback returns low risk while detailed rules are omitted; API-analysis failure returns high risk. The insurance case is a conceptual state machine and concrete record walkthrough, not executable insurance-processing code. The chapter explicitly distinguishes these implementation depths.

## Failures, constraints and recovery

The source considers invalid orders, missing inventory, payment failure, uncertain risk, and human rejection. It motivates conditional branches, external-event waiting, recovery/rollback, and auditability. Console blocking demonstrates a human checkpoint but not restart-safe persistence or authenticated review. A payment failure being classified as a rejected claim is a book-specific modeling choice that should not be generalized into real claims policy.

## Proposed minimal demo — implementation proposal

Use a synthetic equipment-request process with states submitted, validated, awaiting review, fulfilled, and rejected. Simulate fulfillment; persist state for later resume. **Normal check:** a low-risk request reaches fulfilled with a transition log. **Limit check:** review-required processing pauses, survives restart, and resumes only on an explicit decision. These are later design checks, not behavior tested.

## Missing decisions

Choose persistence and event/resume mechanisms, transition schema, review identity, timeout handling, idempotency, compensation, and which operations remain simulated. Avoid live payments or real insurance decisions in the learning demo.

## Supporting source locations

- Ch. 7, workflow purpose/e-commerce implementation: printed 195–197; PDF 226–228.
- Ch. 7, graph requirements/insurance specialist roles: printed 198; PDF 229.
- Ch. 7, insurance states/guards/walkthrough: printed 199–200; PDF 230–231.
