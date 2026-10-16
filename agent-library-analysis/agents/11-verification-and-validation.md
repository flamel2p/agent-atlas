# The Verification and Validation agent

**Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 8, “Data Analysis and Reasoning Agents,” agent subsection and “Case study: News fact-checking assistant - An agent for journalistic integrity.” **Reference ID:** 11. **Locators:** printed pages; 1-based physical PDF pages. **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose, boundaries, inputs and outputs

The pattern checks generated claims and reasoning before downstream use. Intended users include editors and owners of evidence-sensitive analytical pipelines. Inputs are statements/intermediate reasoning, trusted evidence, rules, and numerical tolerances. Outputs are verdicts, discrepancies, sources, and review flags. Success means factual support, logical coherence, consistency, and reproducible decisions. An absence of matching evidence is an unverified outcome rather than confirmation.

## Source architecture

Four functions are described: fact-checking, logical coherence, retrieval-augmented evaluation, and consistency analysis. A meta-reasoning layer examines the primary agent’s output. Retrieval provides authoritative data; NLI classifies entailment/contradiction/neutral; numerical/symbolic checks can recompute results. Format/rule checks, red-teaming, and human triggers complement this. The newsroom case narrows the design to Claim Extractor, Evidence Retriever, and Verifier. Its read-only trusted dictionary is simulated evidence state, not a real external newsroom database. Auditability is required; durable storage is unspecified.

## Input-to-output flow

1. Decompose source text into discrete verifiable claims.
2. Map or search each claim’s metric, entity, and period against trusted sources.
3. Parse units/quantities and compare against evidence using a stated rule or tolerance; broader implementations also examine logical relationships and internal consistency.
4. Assign supported/refuted/inconclusive or case-specific Confirmed/Mostly True/Contradicted/Unverified outcomes.
5. Return evidence and reasoning artifacts; accept, revise, reject, or escalate uncertain/inconsistent outputs according to policy.

The newsroom sample returns Error for unparseable values and Unverified for missing matches. Its normal report stops after processing extracted claims. Production review queues and iterative validation branches are recommendations, not supplied code.

## Source implementation and evidence

An NLI snippet uses PyTorch/Transformers with `facebook/bart-large-mnli` for one premise/hypothesis pair; it does not implement the multi-source weighing described alongside it. The concrete newsroom Python example uses OpenAI `gpt-4o` with JSON-object output and a restricted regex fallback. Dictionary lookup acts as a simplified retriever. It compares percentage values with 0.5-percentage-point tolerance and money with a $500,000 tolerance. SymPy, LangGraph, TruLens, LangSmith, and Guardrails.ai are broader options; versions are unspecified. The book’s newsroom speed claim has no independently verified deployment evidence here.

## Failures, constraints and recovery

The chapter addresses fabricated figures, contradictory evidence, circular reasoning, scope errors, parse failures, and low confidence. It calls for freshness, schema validation, source weighting, calibrated tolerances, logging, and human review. A concrete sample issue matters: its fallback extracts “fell by 5%” as positive 5%, while the trusted value is negative; numeric parsing does not infer direction. This can produce a misleading verdict. Fixed entity/year patterns also constrain fallback coverage.

## Proposed minimal demo — implementation proposal

Verify synthetic release-statistic claims against a versioned local truth table. **Normal check:** an exact claim confirms with the correct record and units. **Limit check:** a directionally reversed percentage or missing record is contradicted/unverified rather than confirmed. These are proposed future checks.

## Missing decisions

Define truth-source authority, units/direction, claim schema, tolerances, NLI role, credibility/conflict policy, review thresholds, and data freshness.

## Supporting source locations

- Ch. 8, functions and validation architecture: printed 211–215; PDF 242–246.
- Ch. 8, newsroom architecture/setup/extraction: printed 220–223; PDF 251–254.
- Ch. 8, mapping/tolerances/reporting/operational advice: printed 223–226; PDF 254–257.
