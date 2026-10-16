# 25 - The Scientific Discovery agent

- **Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 13, "Healthcare and Scientific Agents."
- **Reference ID:** 25 from the official publisher repository inventory; exact PDF heading "The Scientific Discovery agent."
- **Page convention:** printed page / 1-based physical PDF page.
- **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose and contract

**Explicitly stated:** Move beyond answering known questions to identifying defensible knowledge gaps, proposing testable hypotheses, and designing validation experiments. Inputs are a research topic, literature corpus/citations, theoretical frameworks, and experimental constraints. Outputs include synthesis/evidence maps, ranked gaps, evaluated hypotheses with experiments, and prediction-error feedback. Researchers remain responsible for experiment selection and interpretation (pp. 375–387 / PDF 406–418).

**Inference:** Success means a hypothesis is grounded, falsifiable, and linked to an explicit gap rather than declared a discovery because it sounds plausible. **Not specified:** Verified novelty against the entire literature, a universal gap probability model, or a validated research outcome for a runnable demo.

## Architecture and documented flow

Named components are a fault-tolerant literature scanner, citation/semantic clustering, synthesis, gap detector, theory retriever, scientific reasoning engine, hypothesis evaluator, experiment designer, and tracker. Figures 13.2–13.3 show targeted-search feedback and specialized agents around shared orchestration/experimental state (pp. 379, 385 / PDF 410, 416, visually inspected).

1. Look up query cache; return a fresh result if available.
2. Fan out database searches; tolerate individual exceptions, combine successes, deduplicate by DOI/title similarity, and cache the corpus.
3. Cluster papers by semantics/citation structure; summarize consensus, disagreement, and unexplored areas.
4. Detect referenced-but-unstudied topics, cross-domain intersections, and declining-publication/still-cited questions; rank by novelty, feasibility, impact, and available data.
5. For top gaps, retrieve theory and generate abductive candidates under consistency/testability constraints.
6. Evaluate each candidate, pair it with proposed experiments, and filter/rank using the stated consistency/testability thresholds.
7. Re-enter targeted search for gaps; after human-run experiments, store measurements, calculate prediction errors, and pass feedback to model updates (pp. 376–387 / PDF 407–418).

The scanner names PubMed, arXiv, Scopus, IEEE, environment-supplied keys, rate/budget controls, Redis cache, and seven-day TTL. These are source configuration examples, not currently verified provider limits. SciBERT and a generic `scientific-llm` are named without concrete implementation versions. State includes corpus/cluster/citation maps, cached searches, hypotheses, predictions, results, and pending feedback.

## Implementation evidence and constraints

Listings provide orchestration shapes, not complete source clients, clustering, entropy estimation, scientific reasoning, or model training. Retry/backoff/circuit breakers are discussed; `search_with_fallback` is not implemented in the displayed code. MCP/A2A integration is described conceptually, not demonstrated. The experiment-error formula divides by the measured value without a zero guard (pp. 376–386 / PDF 407–417).

Partial search failures affect coverage; paywalls, publication bias, delayed results, and prediction inaccuracies are explicit limitations. An absence in the retrieved corpus does not prove no prior work exists. The polymer case's timelines, formulations, and accuracy improvements are book-reported narrative, not independent empirical validation or reproducible demonstrations (pp. 384–389 / PDF 415–420). Stop budgets and human approval procedures are not fully specified.

## Proposed minimal learning demo - unexecuted

Use a small original synthetic research corpus containing controlled citations, contradictions, and a planted unexplored question. Generate a labeled hypothesis and virtual experiment plan; feed back simulated measurements. No laboratory or real-world scientific intervention.

- **Normal-path acceptance:** The planted gap produces a testable proposal linked to supporting/absent evidence and a simulated prediction-versus-result record.
- **Failure/limit acceptance:** Drop a corpus source or remove necessary evidence; the report marks coverage incomplete and novelty unverified instead of asserting a proven discovery.

**Missing decisions:** Corpus permissions/coverage, topic representation, gap scoring, search stopping/budgets, hypothesis schema, novelty validation, experiment constraints, measurement-zero handling, human review, and governed learning updates.
