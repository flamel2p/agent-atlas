# 23 - The Explainable agent

- **Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 12, "Ethical and Explainable Agents."
- **Reference ID:** 23 from the official publisher repository inventory; exact PDF heading "The Explainable agent."
- **Page convention:** printed page / 1-based physical PDF page.
- **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose and contract

**Explicitly stated:** Record actual decision stages and generate explanations from their trace, adapted to users, engineers, or auditors. The architecture separates decision transparency, feature attribution, counterfactual explanations, and calibrated confidence. A medical diagnostic assistant is the detailed case study, not a separately numbered agent here (pp. 346–356 / PDF 377–387).

Inputs are decision data, context/evidence, and explanation audience; outputs are decision, explanation, ranked alternatives, confidence summary, and audit trail. **Inference:** Success means every explanation is traceable to captured evidence and preserves the same underlying decision across audiences. **Not specified:** A measured explanation-fidelity target or validated calibration data.

## Architecture and documented flow

`DecisionLogger` records analysis, rule application, risk assessment, and final synthesis. `ExplanationGenerator` consumes the trace. LIME, SHAP, counterfactual search, and temperature scaling are described as distinct methods. Persisted records should include versions, provenance, context, attribution, audience, and calibration parameters. Package versions are chapter requirements, not evidence of currently supported recommendations (pp. 330, 347–351 / PDF 361, 378–382).

1. Start recording; analyze input and log the result.
2. Apply domain rules; record rule outputs and risk assessment.
3. Synthesize and log the decision.
4. Generate an audience-specific explanation from the recorded trace.
5. In the confidence sketch, generate a fixed number of hypotheses, score and calibrate each, gather evidence, and rank them.
6. Map confidence to HIGH/MODERATE/LOW wording; low confidence recommends human review.
7. In the clinical variant, combine aggregated vitals, interpreted symptoms, and episodic history; rank differentials, explain, store the encounter, and return report. Prose specifies review below a configured threshold and emergency escalation irrespective of confidence (pp. 347–356 / PDF 378–387).

The clinical memory distinguishes episodic encounters, semantic knowledge, and current working dialogue. Figure 12.2 supports the edge-vitals/coordinator/explainer/episodic-memory separation (p. 353 / PDF 384, visually checked).

## Evidence and failure boundaries

Displayed code is architecture scaffolding: domain analysis, explanation algorithms, calibrator fitting, and most clinical types/methods are absent. `score_differentials` is called but is not defined by the preceding `ConfidenceAwareAgent`. No runnable SHAP/LIME computation or calibrated uncertainty decomposition is shown. The source says companion synthetic notebooks exist; this brief does not validate them (pp. 330, 347–356 / PDF 361, 378–387).

The text discusses storage growth, version drift, retention conflicts, sensor staleness, serving failures, and explanation timeouts. Proposed fallbacks are downweight stale data, rule-based triage, and a flagged reduced explanation. Attention-based fallback is not demonstrated as faithful feature attribution. Source claims of regulatory sufficiency and pilot improvements are not independently established evidence or medical guidance (pp. 348, 356–358 / PDF 379, 387–389). Trace recording also does not prove access to a model's internal reasoning.

## Proposed minimal learning demo - unexecuted

Use a small deterministic synthetic classification task with observable rules. Store structured evidence and rule results; produce technical and plain-language explanations from that same trace. An optional attribution adapter can remain separate. Avoid diagnosis or real personal data.

- **Normal-path acceptance:** Two audience renderings identify the same decision and supporting factors, with every claim linked to a trace event.
- **Failure/limit acceptance:** Missing evidence or explanation failure returns an explicit unavailable/incomplete explanation and review status, never a fabricated justification.

**Missing decisions:** Trace schema and redaction; faithfulness evaluation; explainability method/model fit; calibration dataset; immutable storage; retention; asynchronous explanation gating; audience access; and whether a decision may be released without its explanation.
