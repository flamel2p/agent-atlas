# Knowledge Retrieval Agent specification

Slug: 04-knowledge-retrieval
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Problem and scope

A support reader needs current, traceable passages from a small knowledge base. Demonstrate ingestion, overlapping chunk retrieval, source filtering, bounded evidence selection, and explicit evidence gaps. The scenario is synthetic AtlasDesk subscription/support documentation.

Output is **extractive**: host-assembled exact passages, not generated paraphrases. `answered` means retrieval/selection checks passed, not verified semantic correctness for every English question. No general research, conversational memory, arbitrary uploads, document-field extraction, vector database, external search, or business actions.

## Evidence and decisions

Source: Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Ch.6, Knowledge Retrieval agents, printed pp.146–153 / physical PDF pp.177–184. Read the retained [brief](../../agent-library-analysis/agents/04-knowledge-retrieval.md), [inventory](../../agent-library-analysis/agent-inventory.md), and [foundations](../../agent-library-analysis/foundations.md). The source researcher verified the relevant original extracted pages in this task; raw pages remain outside the repo.

Source facts: lexical/semantic/hybrid retrieval and single-stage patterns are supported. The concrete example uses LangChain, OpenAI embeddings, FAISS, 1,000-character chunks with 200 overlap, and top-three retrieval. Returning sources does not prove claim correctness or freshness. No mandatory retry loop or explicit abstention threshold is implemented in the example.

Selected implementation decisions:

- Python lexical retrieval; rebuild an in-memory index from validated corpus bytes each run. SHA-256 identifies the snapshot. No persistent stale index, framework, hosted store, or embedding cost.
- Paragraph-preserving overlapping chunks: two adjacent paragraphs, one-paragraph overlap, exact character offsets. Single-paragraph documents are valid. Each paragraph is at most 600 characters and each chunk at most 1,202. Citations identify complete paragraphs and deduplicate overlap.
- BM25 ranking over eligible documents only; top three positive-score chunks with stable tie-breaking. Scores are not probabilities. Document and test token normalization and any small alias/stopword table.
- Replay is a conservative lexical baseline: select at most three passages only if their union contains all informative normalized question terms, otherwise abstain. This sacrifices recall and cannot check entailment. Optional model selection can assess relevance semantically within the same candidates; citation validation still does not prove relevance.
- Host-controlled product `atlasdesk`, exact version, `public`/`staff` audience, `as_of` date. Public sees public sources; staff sees public and staff. The CLI simulates identity, not authentication.
- Source eligibility: exact version, effective start inclusive/end exclusive, `reviewed_at <= as_of`, review age at most 90 days inclusive. Filter before ranking or exposure. No filtered IDs/titles/text in query output or model payloads.
- Queries never persist evidence or write state. Only bundled corpus knowledge is available. Refresh means reviewing/editing this case's corpus and rerunning. Metadata dates do not establish real-world freshness.

Lexical normalization applies Unicode NFKC, case folding, and Unicode alphanumeric tokenization (underscores separate tokens). Remove this fixed stopword set: `a an and are as at be by can could do does for from how i in is it me my of on or our please the their them there these they this to us was we what when where which who will with would you your`. Normalize `cancellation`, `cancellations`, `cancelled`, `canceled`, `cancelling`, `canceling` to `cancel`; `subscriptions` to `subscription`; `payments` to `payment`; `refunds` to `refund`. No broader stemming, embeddings, query expansion or semantic search. BM25 uses k1=1.2 and b=0.75 over eligible chunks; unique query terms contribute once. Break equal-score ties lexically by chunk ID. Replay tries the smallest passage combination covering all informative query terms, in retrieved-candidate order.

## Inputs and outputs

CLI: `knowledge-agent ask QUESTION [--backend replay|openai] [--audience public|staff] [--version VERSION] [--as-of YYYY-MM-DD]`. Defaults: replay, public, version `2.0`, today's UTC date. Reproducible examples pin `--as-of 2026-10-19`.

Validate nonblank question up to 1,000 characters and 128 raw tokens, with no leading/trailing whitespace or control/surrogate characters; supported audience/backend, version of 1–32 ASCII letters/digits/dot/underscore/hyphen beginning with a letter/digit, and strict ISO date. Invalid input exits 2. JSON results contain `status` (`answered`, `abstained`, `failed`, `cancelled`), stable reason, backend, question/scope, snapshot digest when available, `answer_mode: extractive`, answer, citations, retrieved chunks, and bounded observable trace/call counts. Non-answers have empty answer/citations. Answered/abstained exit 0; runtime/config/provider errors exit 1; cancellation exits 130. Do not echo raw exceptions, credentials, provider payloads, or filtered metadata.

Bundled JSON corpus schema version 1: 1–32 documents and at most 128 KiB. Each document has unique ID, title, source revision, product/version, audience, `effective_from`, optional `effective_until`, `reviewed_at`, and nonempty text split on blank lines. Maximum lengths: ID/revision 64, title 120, product/version 32, document body 9,600 characters and 16 nonblank paragraphs. IDs/products use lowercase ASCII letters/digits/hyphens, beginning with a letter/digit. Reject unknown/missing fields, duplicate IDs/JSON keys, malformed dates/intervals, unsupported schema, nonfinite JSON numbers, and oversize input. Offsets are Python Unicode character positions in exact source text. SHA-256 hashes validated snapshot bytes. Prose is original repository-owned synthetic material.

Each citation carries document ID/title, source revision, product version, reviewed date, passage ID, start/end offsets, exact quote, and digest. Answers contain only these quotes and fixed host formatting/citation markers. Retrieved chunks expose allowed metadata, scores, IDs, offsets and text, at most three candidates. Up to three unique passages may be selected; every citation maps to an eligible retrieved paragraph and exact source slice. Duplicate/unknown IDs, extra fields, inconsistent selection status or malformed selection fail closed with empty answer.

## Architecture and state

CLI → input/config validation → corpus snapshot validation → access/version/date filtering → paragraph/chunk index → BM25 retrieval → replay/model selector → host citation validation → extractive JSON result.

All state is request-local. Corpus/prompts are packaged with the case. No checkout-root/sibling dependency, sessions, telemetry, disk index, or model-result cache. Python tests may inject synthetic corpus/selector/transport objects; CLI accepts no corpus path or URL.

## Tools and authority

One read-only local search. No model tools. The model cannot change audience, product/version/date, files, filters, limits, or authoritative metadata. Questions and sources are untrusted data. Injection can mislead relevance selection; it cannot confer executable authority or introduce host-accepted invented source prose.

OpenAI mode explicitly opts into transmitting the question and eligible candidate evidence. `OPENAI_API_KEY` and explicit `OPENAI_MODEL` are its only credential/model settings; preflight configuration/SDK before retrieval. Use official Responses API strict JSON schema for selection status/passage IDs, no tools, `store=false`, zero SDK retries, 20-second HTTP timeout, 512 output tokens and at most one request. Fix official API endpoint; ignore arbitrary base URL settings, ambient proxies, custom headers and redirects. The synchronous adapter temporarily suppresses SDK/transport logging and custom-header/log environment options, restoring process settings afterward; it is not designed for concurrent embedding. No live request is required for fixture acceptance; no replay fallback after live failure. Accept one completed assistant output-text selection, optionally accompanied by completed reasoning items; reject incomplete/error/refusal/tool/unexpected output. Bound envelope output items to 16 and selection text to 4,096 characters before local strict JSON and semantic validation.

## Execution and termination

1. Validate request; preflight OpenAI configuration/SDK before corpus access when selected.
2. Load/validate bounded corpus. Corruption terminates with sanitized corpus error.
3. Filter then rank once. No eligible evidence or no positive lexical matches abstains without model call.
4. Keep top three chunks and deduplicate their complete paragraphs. No rewrite, re-query, or retry.
5. Select once, at most three supplied IDs or abstain. Provider refusal, incomplete response, timeout/transport error, malformed/extra output and invalid citation terminate with sanitized failure.
6. Validate all IDs/source slices and render quotes. Only nonempty valid selection is answered; abstention yields evidence-gap reason and no fabricated answer.
7. CLI interruption returns cancelled/130 without partial answer or writes. Bound corpus/query/candidate/output sizes and provider timeout; this synchronous CLI is not hard real-time.

## Acceptance criteria

Fixture/replay:

1. Cancellation query returns current-version policy with exact offsets, revision, review date, digest and inspectable scores.
2. Absent crypto-payments topic abstains with empty answer/citations. Malformed/empty/oversize input and corrupt corpus fail predictably.
3. Public output omits staff-only IDs/text/titles; staff can retrieve its source. Wrong versions, expired/future and >90-day-old sources never enter retrieval/output/selector. Test date boundaries.
4. Overlapping chunks preserve offsets and deduplicate answers. Stable ties are deterministic. Changed bytes change digest and refreshed text is used next run.
5. Unknown/duplicate/excess IDs, fabricated quote/prose fields and contradictory selector status fail closed. Source instructions do not execute actions or expand scope.
6. Documented CLI examples, negative paths and installation from a case-only copy work without siblings/credentials; packaged resource loading works outside the checkout.

Mocked-provider:

7. Preflight precedes retrieval; no evidence means zero calls. Actual SDK with MockTransport verifies strict Responses schema, official endpoint, one request, `store=false`, no tools/retries, timeout/output limits, and only eligible candidate content.
8. Refusal, incomplete/empty/malformed output, invalid selection, 429/5xx/timeout and interruption produce documented terminal outcomes without raw provider text or partial answers. Live relevance/model/account compatibility is separate unverified evidence until run.

## Dependencies and open decisions

Python 3.14, local uv project/lock, stdlib retrieval/validation, pytest 9.1.1, optional OpenAI SDK 3.31.0 (resolved transport httpx2 2.13.1), and hatchling 1.32.4 build backend. See [SOURCES.md](SOURCES.md) for inspected book passages and official API evidence. These are resolved/tested pins, not a claim about the latest release. No material behavior decisions remain; live model ID is caller-configured and live evaluation is separate from fixture readiness.
