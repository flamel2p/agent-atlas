# Scientific Research Agent specification

Slug: 06-scientific-research
Status: demo-ready
Runtime: Python 3.14 (uv CLI, POSIX)

## Problem and scope

A researcher or engineer supplies a research objective and a bounded synthetic
paper corpus about retrieval evaluation. The case teaches literature selection,
corpus-derived thematic grouping, and evidence provenance. It produces a
deterministic extractive evidence map for human review.

The agent chooses matching records, theme membership, and representative
excerpts under fixed host policy. It is a one-pass deterministic agent workflow.
It does not generate hypotheses, assess consensus or disagreement, evaluate study
quality, infer research gaps, run experiments, or validate scientific claims.
Custom input is limited to synthetic corpora. No live literature or LLM is used.

## Evidence and decisions

Source facts come from Imran Ahmad, *30 Agents Every AI Engineer Must Build*,
Packt, March 2026, Chapter 6, "Scientific Research agents".
The workflow is described on printed pp. 161-162, physical PDF pp. 192-193.
The concrete sample on printed pp. 163-166, PDF pp. 194-197, queries arXiv,
embeds title/abstract text, runs k-means, and extracts a report without a
generative LLM. Advanced multi-source capabilities are conceptual.

Direct inspection found that summary lookup can select outside the cluster,
sentence provenance is not retained in the final summary, and the newest
representative papers are not necessarily the summary's sources. The example
only guards empty results, not a record count below four clusters. Prose promises
abstract filtering but the inspected listing does not enforce it. Limitations
on printed pp. 166-169, PDF pp. 197-200, require expert interpretation and do not
establish independent scientific discovery or measured business outcomes.

Selected adaptation: original synthetic metadata, exact lexical Jaccard scores,
complete-link grouping with a support-aware target, exact member abstract spans,
and a stdlib-only runtime. This is an independent implementation of the pattern.
It does not reproduce the book's model, API, or performance claims.
See [DESIGN.md](DESIGN.md) for alternatives and the implementation plan.

## Inputs and outputs

The default corpus is an original packaged fixture. `--corpus PATH` reads one
caller-selected regular JSON file. Reads reject final-component symlinks and non-regular files,
use a byte limit before parsing, and never fetch a source URL. Input schema
version is integer `1`. Unknown keys, duplicate JSON keys, non-finite numbers,
wrong types, missing values, and conflicting paper identities fail.

Corpus fields are `schema_version`, `corpus_id`, and `papers`. Each paper owns
an ID, title, raw abstract, authors, year, source label, source record identifier,
and an explicit `synthetic: true` marker. The implementation documents exact
field names and bounds in the README. Bounds include 1 MiB raw bytes, 80 records
before deduplication, 300 title characters, 8,000 abstract characters, and
500 objective characters. An empty paper array is valid. An objective must
contain at least one searchable term.

The request selects at most 20 papers and a target of 1-8 themes. Defaults are
20 papers and 4 themes. Integer options reject booleans in the Python interface.
Exact duplicate content is detected using normalized title, year, and abstract.
The retained record has the smallest paper ID. Aliases are retained in a
deduplication ledger. Reusing one ID with different metadata fails before
content deduplication. Deduplication is a text heuristic, not study-family
detection. Canonical ordering makes semantic output independent of input order.

The report includes a schema version, objective, outcome, query terms, original,
considered, removed-duplicate, and selected counts, exact relevance fractions, matched terms, selected papers
with full abstracts, theme descriptors and membership, up to two representative
spans per theme, duplicate decisions, stop reason, and interpretation limits.
Corpus SHA256 hashes the original bytes. Each evidence span includes the paper ID,
abstract digest, start/end Unicode code-point offsets, and exact source text.
Offsets are half-open: `abstract[start:end] == text`. Evidence must belong to a
selected member of its theme. Digest equality proves byte/text identity, not
scientific validity.

JSON is the authoritative serialized report. A text renderer uses the same
report. Equal input bytes and options yield equal output bytes with no timestamps.
All reports identify the synthetic source and mark consensus, disagreement,
quality, and gaps as not assessed.

## Architecture and state

Frozen dataclasses and tuples model the snapshot, request, ranked papers, themes,
and evidence spans. `corpus.py` owns strict parsing, identity rules, deduplication,
and snapshot provenance. `mapping.py` owns lexical policy and the pure
`map_literature(corpus, request)` operation. The CLI owns argument parsing,
one bounded local read, rendering, stdout/stderr, and exit codes.

All state belongs to one invocation and disappears on exit. There is no durable
memory, shared runtime, callback/tool plugin system, provider configuration,
or dependency on a sibling case. Package resources contain all default fixtures.

## Tools and authority

The host reads the packaged fixture or the explicit local corpus, validates it,
and executes the fixed search/group/report pipeline. Application effects are
bounded reads and stdout/stderr only. The application creates no report artifacts,
updates no state, and has no network operations, subprocess calls, dynamic
execution, or secrets. Python may create bytecode caches, and uv creates its
normal environment/build caches. Shell redirection remains an operator action.

Paper titles, abstracts, authors, and source identifiers are untrusted data.
Imperative text cannot change options, call tools, or alter host policy.
Terminal control characters are rejected at input boundaries. Human review is
required for interpreting studies and deciding any actual research direction.

## Execution and termination

1. Validate arguments and load one bounded corpus snapshot. Preserve source text.
2. Tokenize objective and papers with one documented case-folding/token/stopword
   policy. Rank positive title-plus-abstract Jaccard overlaps using exact fractions.
   Scores express lexical overlap, never confidence. Resolve ties by paper ID.
3. Keep at most the requested paper count. Report truncation when matches exceed it.
   Empty/no-match corpora return a valid `no_matches` report with no themes.
4. Remove query terms from each selected paper's thematic token set. Start with
   singleton groups. Complete-link similarity is the minimum pairwise Jaccard
   similarity across two groups. Merge the pair with highest strictly positive
   support, tie-breaking by sorted member IDs. Stop at the target count or when
   no supported merge remains. No merge is forced to meet the target. Small
   corpora can yield fewer themes; disconnected corpora can yield more.
5. Order themes by earliest search rank. Derive up to three lexical descriptors
   from member term frequency, with lexical ties. Select up to two representative
   members using minimum within-theme similarity, then search rank and ID.
6. Choose a sentence-like span from each representative using objective and
   descriptor overlap. Sentence segmentation is a punctuation heuristic.
   Verify exact slice equality, abstract digest, selection, and theme membership
   before returning the report. Do not paraphrase abstracts into unsupported claims.
7. Render a complete report only after validation. Mapped and no-match reports
   exit 0. Argument/input failures exit 2 with sanitized stderr and no partial
   stdout. Cancellation exits 130. No retries or adaptive searches occur.

The corpus and selected-count bounds limit work. Grouping performs at most
`selected_count - 1` merges. There is no external wait, iterative model loop,
or wall-clock success claim.

## Acceptance criteria

All criteria use fixture evidence. There is no provider mode in this case.

- The default objective/corpus yields multiple themes with selected evidence.
- Every emitted span resolves exactly to its included abstract, digest, and
  theme member. Unselected/out-of-theme records never supply theme evidence.
- Equal bytes/options produce byte-identical output. Input permutations preserve
  semantic results except the raw snapshot digest.
- Empty, no-match, singleton, fewer-than-four, and duplicate-only inputs terminate
  with honest outcomes. Disconnected vocabulary never forces a thematic merge.
- Duplicate records cannot inflate counts. Conflicting IDs fail before mapping.
- Record/byte/string/option bounds, malformed JSON, duplicate keys, non-finite
  values, invalid types, unreadable/final-component-symlink/non-regular paths fail without a report.
- Embedded instructions remain data. Runtime tests deny network access and check
  that the CLI creates no report artifacts in its working directory.
- The documented CLI succeeds from a case-only copy and from an installed wheel
  outside the source directory. Root structure validation also passes.
- Independent review finds no unresolved actionable correctness/authority issues.

## Dependencies and open decisions

Python 3.14 and its standard library own runtime behavior. Development dependencies
and build tooling are case-local and locked with uv. No model assets, credentials,
OCR engine, browser, repository API, or network service is required.
There are no material open decisions for the selected demo. Live retrieval,
semantic models, real-paper licensing, and scientific quality appraisal require
a separately scoped extension.
