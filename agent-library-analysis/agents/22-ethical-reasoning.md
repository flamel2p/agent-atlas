# 22 - The Ethical Reasoning agent

- **Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 12, "Ethical and Explainable Agents."
- **Reference ID:** 22 from the official publisher repository inventory; exact PDF heading "The Ethical Reasoning agent."
- **Page convention:** printed page / 1-based physical PDF page.
- **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose and contract

**Explicitly stated:** Interpose ethical evaluation between reasoning and action. Every candidate action is checked against explicit values, fairness constraints, and applicable rules before dispatch; violations cause mitigation or human escalation. The concrete case is an HR screening assistant with anonymization, bias monitoring, and fairness enforcement (pp. 330–346 / PDF 361–377).

Inputs are proposed action plus runtime context; the HR variant receives resume/job requirements and requires batch/group evidence for fairness analysis. Outputs are permitted or modified actions, review cases, and audit records. **Inference:** Intended users are developers and policy owners supervising consequential agents. Success means the execution gate cannot be bypassed and violations have traceable outcomes. **Not specified:** A validated universal ethics policy or evidence that the example establishes legal compliance.

## Architecture and flow

The text describes deontic obligation/permission/prohibition, but explicitly says the displayed checker is a deterministic rules-engine lookup, not an LLM call or formal SMT solver. Principle-specific validators return compliance, explanation, and severity; an audit logger records action/context/violations. A jurisdiction-aware validator registry is discussed later. Chapter requirements pin Python 3.10+ and packages including LangChain 0.2.16, langchain-openai 0.1.23, OpenAI 1.40.0, SHAP 0.45.1, LIME 0.2.0.1, NumPy 1.26.4, and scikit-learn 1.5.1; they also name `gpt-4o` (pp. 330, 332–336, 358 / PDF 361, 363–367, 389).

1. Receive proposed action and trusted context.
2. Run all relevant principle validators; collect violations.
3. Record the attempted action and findings before returning a result.
4. If none fail, return a permitted action for later dispatch.
5. Otherwise apply mitigation strategies, revalidate, then return a compliant variant or escalate remaining violations to a human.
6. In the HR variant, anonymize, score skills, assess batch disparity, mitigate HIGH/MEDIUM reports, and audit.
7. A rolling-window monitoring sketch emits metrics; HIGH severity triggers an alert. Suggested recovery is freeze automation, human review, evidence snapshot, and possible rollback (pp. 334–346 / PDF 365–377).

Policy sets, audit records, and a decision window are the supported state; model learning is discussed conceptually rather than implemented.

## Evidence quality and constraints

**Verified contradiction:** Figure 12.1 is captioned as the ethical loop but actually depicts a student model, curriculum planner, BKT learning, and pedagogical constraints. It is not evidence for the ethical gate (p. 331 / PDF 362, visually inspected).

Listings leave checker classes, mitigation, audit storage, and many metric methods abstract. The fairness detector's batch inputs do not match the HR sketch's single-evaluation call; `FairnessEnforcer` uses an undefined threshold, and dict-style reports are elsewhere consumed as attributes. Human escalation is described, not completed. The fairness-regime prose on p. 338 / PDF 369 incorrectly points to the medical case for group focus, while Table 12.1 and the HR discussion identify HR. Anonymization alone does not remove proxy signals; the book discusses k-anonymity, proxy audits, prompt injection, gaming, and learning feedback risks. Its legal thresholds/framework claims are source descriptions, not current legal advice.

## Proposed minimal learning demo - unexecuted

Use synthetic action requests and a deterministic policy registry; simulate dispatch and human-review queues. Demonstrate pre-execution gating without real hiring or external side effects.

- **Normal-path acceptance:** An allowed synthetic action produces a permission record and exactly one simulated dispatch.
- **Failure/limit acceptance:** A forbidden data-disclosure request stays undispatched after failed mitigation and produces a review case with policy ID and audit evidence.

**Missing decisions:** Policy authority/versioning, conflict resolution, severity semantics, mitigation bound, tool-wrapper enforcement, review ownership, audit integrity, fairness data/metric denominators, and jurisdiction scope.
