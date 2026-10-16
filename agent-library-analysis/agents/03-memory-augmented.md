# The Memory-Augmented agent

**Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 5, “Foundational Cognitive Architectures,” “The Memory-Augmented agent.” **Reference ID:** 03. **Locators:** printed pages; physical PDF pages are 1-based. **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose, boundaries, inputs and outputs

The pattern preserves context beyond one interaction so an assistant can maintain coherence and personalize later responses. Inputs are a current query, user identity, active session, prior interactions, and domain knowledge. Outputs are context-aware responses/actions plus a stored interaction record. Success means recovering relevant history and grounding factual answers without overwhelming the current context. The book illustrates a healthcare assistant; that example is architectural exposition, not clinical validation or an appropriate unrestricted public demo.

## Source architecture

The cognition core coordinates three stores: transient working memory in the current prompt; timestamped episodic memory for prior events; and semantic memory for factual knowledge from documents, databases, or APIs. Vector retrieval bridges the core and long-term stores. Relevance can account for similarity, recency, and user preferences. Consolidation/summarization compresses growing histories. Chroma, Pinecone, and Weaviate are named database options. These are text-supported components; the simplified implementation demonstrates only episodic retrieval and storage, not a complete three-store system.

## Input-to-output flow

1. Receive the user query and maintain current-turn context in working memory.
2. If cross-session continuity is needed, search episodic history; if factual knowledge is needed, query semantic memory.
3. Retrieve relevant context and combine it with the current request for cognition and response generation.
4. Produce a response or action informed by current context, personal history, and domain facts.
5. Store interaction/events with user identity and timestamp for later recall.
6. Periodically consolidate or summarize long histories to keep retrieval and prompts manageable.

The concrete class retrieves at most three prior interactions for the user, generates a response, then adds the new record. It does not implement branching store selection or consolidation. No retrieval-failure escalation or global loop limit is specified.

## Source implementation and evidence

Chapter prerequisites: Python 3.10+, a virtual environment, CPU operation, 8 GB RAM minimum, and optional CUDA 12+ GPU. The Python class accepts abstract LLM and vector-database clients and calls their generic search/add/generate methods. There is no provider-specific adapter, explicit embedding model, persistence setup, or database schema. The personalized-healthcare case explains how all memory types might interact; it is broader than the supplied class. The prose says retrieval provides “full conversational history,” although the shown search is limited to three relevant records; completeness should not be assumed.

## Failures, constraints and recovery

The memory trigger table associates skipped working memory with incoherence, skipped episodic recall with repeated history, and missing semantic retrieval with stale or fabricated factual answers. Growing stores risk information overload and maintenance complexity. The source proposes relevance selection and summarization to reduce prompt bloat. It does not establish a privacy lifecycle, deletion rules, correction semantics, or protections against storing erroneous model responses as future evidence.

## Proposed minimal demo — implementation proposal

Build a synthetic study-preference assistant that recalls preferred explanation style across sessions and consults a small course FAQ. **Normal check:** a second session retrieves the same user’s earlier preference and identifies its source. **Limit check:** another user’s history is never retrieved, and an absent memory is reported without inventing prior preferences. These checks are proposals only.

## Missing decisions

Choose store boundaries, retrieval ranking, user isolation, retention/deletion, correction of stale memories, summarization policy, provider, and persistence. Decide whether the first version demonstrates episodic memory alone or the full three-store pattern.

## Supporting source locations

- Ch. 5, technical requirements: printed 118; PDF 149.
- Ch. 5, memory types/trigger table/architecture: printed 135–138; PDF 166–169.
- Ch. 5, simplified class/healthcare case: printed 138–141; PDF 169–172.
- Ch. 5, comparison/context management: printed 141–144; PDF 172–175.
