# 29 - The Collective Intelligence agent

- **Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 15, "Education and Knowledge Agents."
- **Reference ID:** 29 from the official publisher repository inventory; exact PDF heading "The Collective Intelligence agent."
- **Page convention:** printed page / 1-based physical PDF page.
- **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose and contract

**Explicitly stated:** This is a team-organizing architectural pattern, not one agent. Role-specialized participants propose, critique, refine, and synthesize solutions to problems requiring multiple perspectives. The case designs a programming-assignment rubric using pedagogy, domain, and assessment specialists. Inputs are problem, expertise/roles, tools, prior proposals, and evaluation criteria; outputs are proposals, scored critiques, synthesized result, and deliberation evidence (pp. 441–453 / PDF 472–484).

**Inference:** Intended users include curriculum/design teams needing visible trade-offs. Success means a synthesis survives multiple relevant critiques; agreement alone is not correctness. **Not specified:** A validated collective-quality benchmark or calibrated expert weights for a new domain.

## Architecture and documented flow

`CollaborativeAgent` has identity, role, expertise, LLM, tools, and local `AgentMemory`; `SharedContext` stores contributions/history. `ConsensusEngine` initializes weights and manages bounded rounds. The theoretical discussion explicitly cautions that shared models have correlated errors, undermining Condorcet independence assumptions (pp. 441–449 / PDF 472–480).

1. Create shared context and obtain a proposal from each agent; each reads relevant prior context and provides assumptions/uncertainties plus metadata.
2. Designate a rotating adversarial critic.
3. Have each agent evaluate every other agent's proposal against a common rubric; self-evaluation is excluded.
4. Aggregate evaluator scores using expertise weights.
5. Check convergence. If reached, synthesize and stop early; otherwise refine proposals and repeat up to the round bound (default three).
6. At the limit, synthesize the latest state even without convergence.
7. Conceptual extensions include randomized proposal order, relevance gates, learned weights, constraint relaxation, analogical transfer, and semantic-distance monitoring; these are not all implemented (pp. 443–453 / PDF 474–484).

Requirements name Python 3.10+, OpenAI 1.40.0, NumPy 1.26.4, NetworkX 3.3, python-dotenv 1.0.1, and `gpt-4o` (p. 421 / PDF 452). Tool use/local memory updates are not demonstrated in participant methods.

## Evidence quality and contradictions

**Verified diagram discrepancy:** Figure 15.2 labels UX, architecture, performance, and security roles, while its adjacent prose lists facilitator, research, synthesis, and evaluation roles. It supports shared-state coordination, not the specific prose inventory (p. 442 / PDF 473, visually inspected).

Figure 15.3 and the formula include relevance weighting, but the displayed aggregator only computes expertise-weighted mean of `overall` scores. Proposals described as independent are generated sequentially while reading earlier proposals. Convergence, refinement, synthesis, role mutation, and parsing helpers are absent. A break on convergence bypasses the shown critic reset; zero agents/rounds and evaluator failures lack defined handling (pp. 445–450 / PDF 476–481).

The later "runnable" mock case omits constructor-required identity/tools, supplies a plain callable where `.generate` is expected, and calls `run_session` instead of the earlier `run_consensus`. It is an inconsistent illustrative scaffold, not a verified executable scenario (pp. 451–452 / PDF 482–483).

Groupthink, anchoring, dominance, correlated errors, and coordination cost are explicit constraints. Source claims of better outcomes or emergence are narrative/theoretical, not measured evidence for this library. No mandatory human-review gate is implemented for unresolved disagreement.

## Proposed minimal learning demo - unexecuted

Use deterministic role adapters and original rubric proposals to expose proposal → cross-review → weighted synthesis. Optionally replace adapters with an LLM later. Preserve dissent and show whether termination was convergence or budget exhaustion.

- **Normal-path acceptance:** Three roles contribute distinct criteria; the final rubric links accepted/rejected elements to critiques and contains no self-scoring.
- **Failure/limit acceptance:** Conflicting scores or a missing reviewer exhausts the bound and returns unresolved coverage/dissent instead of claiming consensus correctness.

**Missing decisions:** Independence policy; critique schema; expertise/relevance calibration; actual convergence test; role cleanup; retries/budgets; synthesis faithfulness; dissent retention; and human approval of the result.
