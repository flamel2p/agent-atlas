# The Self-Improving agent

**Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 9, “Software Development Agents,” “The Self-Improving agent.” **Reference ID:** 15. **Locators:** printed pages; 1-based physical PDF pages. **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose, boundaries, inputs and outputs

The pattern improves future behavior from accumulated outcomes rather than only repairing one task. Intended users operate agents whose environment, needs, or failure patterns evolve. Inputs are execution traces, explicit ratings/corrections, implicit behavior/telemetry, and synthetic evaluations. Outputs are evidence-backed improvement hypotheses, controlled prompt/tool/retrieval/threshold/model adaptations, and versioned evaluation results. Success requires gains against a baseline and held-out data without unacceptable accuracy, security, bias, latency, or cost regressions. Adaptation remains governed by people.

## Source architecture

A closed loop combines Task Execution, a Sensing Layer, coder/artifact production, critic, planner, HITL checkpoint, Learning Layer, and Deploy & Test Refined Behavior. Critic KPIs include completion, recovery, latency, satisfaction, and improvement velocity. Planner records source signal, proposed adaptation, confidence, evidence count, rollback safety, and review need. Data capture/curation prepares learning; updates may use fine-tuning, LoRA, or simpler prompt changes. Immutable version history and evaluation metrics support reversal. LangGraph is a named orchestration option; the implementation of adaptation selection and deployment is conceptual.

## Input-to-output flow

1. Execute a task under the current behavior version and collect outcomes.
2. Aggregate explicit, implicit, and synthetic feedback; filter low-quality or harmful examples.
3. Have the critic identify recurrent performance gaps against defined criteria.
4. Have the planner propose a specific change tied to evidence and validation targets.
5. Route changes according to risk: significant changes require human validation; permitted low-risk changes may proceed after gates.
6. Apply a versioned adaptation and compare against baseline/held-out evaluations.
7. Deploy only after required gates; monitor real outcomes and rollback regressions.
8. Continue collecting feedback for subsequent cycles.

The loop is intentionally ongoing. The book does not give a runnable scheduler or numeric global stopping policy.

## Source implementation and evidence

The concrete Python consists mainly of Pydantic models/Enum defining adaptation types and improvement hypotheses, with example structured outputs. The adaptive fintech-support case describes LangGraph, recency-weighted retrieval, tone updates, and escalation adjustments; it is not a complete executable learning pipeline. No exact model/framework version or training recipe is supplied. Reported resolution, timing, and satisfaction gains are book case-study claims without independent dataset/deployment evidence.

## Failures, constraints and recovery

The source identifies drift beyond policy, feedback-induced bias, overfitting, catastrophic forgetting, poor proxy metrics, and over-personalization. It proposes filtered data, held-out groups, baseline regression checks, risk-based human review, explainable lineage, diversity constraints, and instant version rollback. The governance narrative requires review for significant prompt/threshold changes, but the example PlannerOutput marks prompt/threshold proposals as not requiring review; risk classification must be made consistent before implementation. The support threshold-change narrative does not itself establish calibrated confidence for another domain.

## Proposed minimal demo — implementation proposal

Use synthetic FAQ failures to propose one retrieval-recency adjustment. Compare current and candidate behavior on fixed held-out cases; generate a reviewable change record rather than autonomous deployment. **Normal check:** the candidate improves recent-policy answers while preserving baseline answers. **Limit check:** a regression rejects the adaptation and retains the baseline version. Proposed checks only.

## Missing decisions

Define feedback authority, evaluation sets, adaptation scope, risk classification, minimum evidence, candidate selection, review ownership, version storage, and rollback trigger. Start with configuration/prompt changes before model training.

## Supporting source locations

- Ch. 9, purpose/control architecture: printed 265–268; PDF 296–299.
- Ch. 9, feedback/models/continuous adaptation: printed 269–271; PDF 300–302.
- Ch. 9, support case/adaptations/outcomes: printed 272–275; PDF 303–306.
- Ch. 9, safeguards/lifecycle: printed 276–277; PDF 307–308.
