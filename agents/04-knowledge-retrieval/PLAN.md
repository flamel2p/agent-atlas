# Knowledge Retrieval build plan

[SPEC.md](SPEC.md) owns behavior. This plan records implementation and validation checkpoints.

1. Establish ownership, source evidence, inputs/outputs, retrieval/access/freshness contracts, extractive answer limits and provider authority.
2. Package synthetic versioned support documents; implement bounded corpus validation, overlapping chunks, exact provenance, pre-ranking filters, BM25 and conservative replay selection.
3. Add optional bounded OpenAI Responses selection: early preflight, strict schema, one call, no tools/retries, sanitized errors, host validation.
4. Check normal/gap paths, access/version/date boundaries, malformed input/corpus, overlap/deduplication, invalid citations, provider failures and real SDK mocked transport.
5. Resolve independent review findings; run documented examples/tests and case-only installation without sibling resources/credentials; check root structure.
6. Synchronize docs/catalogue and readiness to actual evidence. Keep fixture, mocked-provider, live-model, hosted CI and deployment results distinct.

## Progress

Completed on 19 October 2026:

1. Contract established; retained analysis and original extracted book passages inspected, current official Responses API behavior checked. See [SOURCES.md](SOURCES.md).
2. Eight synthetic versioned documents packaged; bounded validation, scope/date filters, overlapping paragraph chunks, BM25 and conservative replay implemented.
3. Optional OpenAI selection implemented with pinned SDK and strict host validation; no live request made.
4. 181 fixture/CLI/mocked-provider tests passed without warnings; 12 independent CLI scenarios passed.
5. Independent review's cleanup-interruption finding fixed and regression-tested. Final review found no remaining actionable findings. Full suite passed in a case-only copy; a built wheel ran without copied source or the OpenAI SDK. Structure/whitespace checks passed.
6. SPEC, README and root catalogue synchronized to `demo-ready` for selected fixture/mocked-provider acceptance criteria. Live model, hosted CI and deployment remain unverified.

No implementation step remains for the selected scope. Live-model relevance evaluation is the next separate validation step if the optional provider path is to be used; enterprise authentication, production ingestion and semantic retrieval require new scope.
