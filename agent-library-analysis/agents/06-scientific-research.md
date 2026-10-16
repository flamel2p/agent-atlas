# Scientific Research agents

**Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 6, “Information Retrieval and Knowledge Agents,” “Scientific Research agents.” **Reference ID:** 06; singular reference alias: Scientific Research agent. **Locators:** printed pages and 1-based physical PDF pages. **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose, boundaries, inputs and outputs

This pattern helps researchers map a literature corpus and synthesize consensus, disagreement, and gaps. Inputs are a research objective and accessible papers/metadata; outputs include thematic summaries, comparative tables, evidence maps, and suggested research directions. The intended user remains a subject-matter expert. Synthesis of existing literature does not independently validate a hypothesis, run experiments, or establish new scientific knowledge. The drug-discovery case is an illustrative narrative; its time savings are not independently evidenced.

## Source architecture

A cognition core plans broad scanning, thematic clustering/summarization, and synthesis. The advanced architecture adds parallel repository search, citation-graph traversal, entity linking, multi-hop reasoning, and multi-vector retrieval across paper aspects. Metadata supports provenance. PubMed, arXiv, IEEE Xplore, and Scopus are named sources; MCP and A2A are discussed as possible interoperability mechanisms. These advanced components are conceptual, not all present in the sample. The code uses an in-memory DataFrame and embedding matrix; persistent research memory is unspecified.

## Input-to-output flow

1. Interpret the objective and formulate a search strategy with dependencies.
2. Query literature repositories for relevant records and metadata.
3. Group records by methodology, findings, or theme and summarize representative material.
4. Compare evidence and produce a structured synthesis emphasizing agreement, divergence, uncertainty, and gaps.
5. Have domain experts review synthesis; subsequent corpus updates require refreshing the process.

The concrete sample queries only arXiv, embeds title-plus-abstract text, applies k-means, assembles short extractive summaries, and prints themes, citations, and an evidence table. Empty search results stop the example with a suggestion to broaden the query. It does not implement cross-source reconciliation or an adaptive research loop.

## Source implementation and evidence

The Python example names arxiv, sentence-transformers, scikit-learn, pandas, NumPy, and nltk. It uses `all-MiniLM-L6-v2`, a maximum of 80 records, four clusters, and k-means with fixed random seed and `n_init="auto"`. No generative LLM is used in this concrete scan/cluster/report path. Package versions are unpinned. It prints bibliographic URLs but does not establish study quality or experimental validity.

The prose promises representative cluster papers; the citation code selects recently published papers within each cluster. Summary helpers search nearest abstracts across the whole corpus rather than explicitly restricting them to assigned cluster membership. Those are useful implementation boundaries to inspect before copying the example.

## Failures, constraints and recovery

The source identifies hallucinated/misattributed citations, limited context, publication bias, licensing/API access restrictions, update burden, and the need for expert verification. It explicitly denies independent experimental discovery while a later comparison table uses broader “hypothesis” and “experimental design” language; interpret those as support tasks requiring human review. The sample does not guard a result count smaller than its fixed cluster count.

## Proposed minimal demo — implementation proposal

Cluster a bounded, synthetic paper-metadata corpus on retrieval evaluation and generate an evidence-linked theme map. **Normal check:** each summary sentence resolves to an included abstract. **Limit check:** insufficient records reduce the cluster count or return a clear limit message. These are proposals, not tests performed.

## Missing decisions

Choose live versus fixture data, redistribution rights, sample/cluster limits, ranking, citation granularity, quality appraisal, model availability, and the human review boundary.

## Supporting source locations

- Ch. 6, purpose/workflow: printed 161–162; PDF 192–193.
- Ch. 6, concrete scan/cluster/report code: printed 163–166; PDF 194–197.
- Ch. 6, advanced architecture/case/limitations/comparison: printed 166–169; PDF 197–200.
