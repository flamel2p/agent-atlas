# Scientific Research Agent

Slug: 06-scientific-research
Status: demo-ready
Runtime: Python 3.14 (uv CLI, POSIX)

## Purpose and contract

This demo maps an original synthetic literature corpus into lexical themes and
exact abstract excerpts for human review. It makes no scientific discovery or
quality claim. [SPEC.md](SPEC.md) owns behavior and limits; [DESIGN.md](DESIGN.md)
records the selected architecture.

## Setup and run

From this case directory, with Python 3.14 and uv installed:

```sh
uv sync --locked
uv run --locked scientific-research --objective "retrieval evaluation"
uv run --locked scientific-research --objective "retrieval robustness" --format text
uv run --locked pytest -q
```

`--corpus` is optional. Omit it for the [packaged synthetic fixture](src/scientific_research/data/corpus.json).
The first setup can download Python/build/test packages. With those packages
cached, add `--offline` to `uv sync` and `uv run`. Set
`UV_CACHE_DIR=/tmp/agent-atlas-uv-cache` only where uv's normal cache is unavailable.
Runtime needs no network, secrets, service, model, or environment variables.

JSON is the authoritative output and default format. A mapped or no-match report
exits 0. Rejected arguments, malformed input, and inaccessible or unsafe files
exit 2 with fixed stderr text and no partial stdout. Keyboard cancellation exits
130. The application reads one corpus and writes only stdout/stderr. Python can
create bytecode caches, and uv creates environment/build caches. The application
creates no report files or persistent state. Shell redirection is an operator action.

## Input schema

The selected file is strict UTF-8 JSON of at most 1 MiB. It must be a POSIX
regular file; a final-component symlink, FIFO, socket, and directory are rejected.
The exact root keys are `schema_version`, `corpus_id`, and `papers`. Version is
integer `1` (not boolean). `corpus_id` and each `paper_id` are 1–64 ASCII
characters matching `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`. `papers` contains 0–80
records before deduplication. Each record has exactly these keys:

| Field | Type and bound |
| --- | --- |
| `paper_id` | Identifier as above |
| `title` | Nonblank string, at most 300 Unicode code points |
| `abstract` | Nonblank raw string, at most 8,000 Unicode code points |
| `authors` | Array of 1–12 nonblank strings, each at most 120 code points |
| `year` | Integer 1–9999, excluding boolean |
| `source` | Nonblank label, at most 120 code points |
| `source_id` | Nonblank source record identifier, at most 120 code points |
| `synthetic` | Literal `true` |

Unknown fields, duplicate JSON keys, non-finite numbers, wrong types, conflicting
same-ID metadata, and Unicode control/surrogate/format code points fail. Text is
preserved for evidence. `--objective` is required, nonblank, at most 500 code
points, and must contain a searchable term. `--max-papers` is 1–20 (default 20)
and `--target-themes` is 1–8 (default 4). The Python request interface rejects
boolean integers.

Example custom corpus:

```json
{"schema_version":1,"corpus_id":"example","papers":[{"paper_id":"P1","title":"Retrieval evaluation with labels","abstract":"Labels compare retrieved passages with question needs.","authors":["Example Author"],"year":2025,"source":"Synthetic Archive","source_id":"SA-1","synthetic":true}]}
```

Save the example as `private-data/corpus.json` inside this case, then run:

```sh
uv run --locked scientific-research --objective "retrieval evaluation" --corpus private-data/corpus.json --max-papers 10 --target-themes 3
```

All metadata is untrusted data, including imperative text in an abstract. The
CLI never fetches `source_id` or a URL. The contract accepts synthetic corpora
only.

## Architecture and output

The CLI validates options and reads one bounded file or package resource.
`parse_corpus(bytes)` rejects invalid structure, hashes original bytes, and
deduplicates normalized title, year, and abstract, retaining the smallest ID.
Identical same-ID repeats also collapse; `original_record_count`,
`considered_count`, and `removed_duplicate_count` expose their effect. Distinct
alias IDs appear in `duplicate_decisions`. This is text deduplication, not a
study-family or publication-identity check.

`map_literature(Corpus, ResearchRequest)` tokenizes case-folded Unicode word
runs excluding underscores and the fixed stopword set in
[mapping.py](src/scientific_research/mapping.py). It ranks positive
title-plus-abstract Jaccard overlaps as exact numerator/denominator fractions;
these are vocabulary scores, not confidence. It takes the requested maximum,
then removes objective terms for grouping. Complete-link group support is the
smallest pairwise Jaccard overlap across two groups. Highest positive support
merges first, with ID ties, until the target is met or no merge is supported.
It never forces a merge. A theme's top three descriptors count member term
presence with lexical ties. Up to two representatives maximize their minimum
similarity to other members, then use search rank and ID.

Evidence selects a sentence-like `.!?` punctuation segment by overlap with
query and descriptors; if segmentation produces no word-bearing segment, it
uses the exact nonblank abstract. The span's half-open `start:end` positions
are Python Unicode code-point indices into the full selected abstract.
`abstract_sha256` hashes the UTF-8 encoding of that abstract. The mapper verifies
slice equality, digest, and theme membership before returning. These checks
establish provenance within this snapshot, not scientific truth.

The report carries corpus SHA256 over original bytes, full selected abstracts,
exact relevance fractions, themes, duplicate decisions, stop reason, and
interpretation limits. `no_matches` is a valid report with no themes. Equal
input bytes/options produce byte-identical JSON. Reordering records changes the
raw digest but not the semantic report. No timestamps or persistent state exist.

## Source reading guide

1. [cli.py](src/scientific_research/cli.py) is the entry point. Inspect POSIX
   file authority, bounded reads, fixed failure output, and serialization.
2. [corpus.py](src/scientific_research/corpus.py) defines the immutable snapshot
   and strict JSON, identity, deduplication, and provenance boundary.
3. [mapping.py](src/scientific_research/mapping.py) defines request/report types,
   exact lexical ranking, positive complete-link groups, and member evidence.
4. [test_literature_map.py](tests/test_literature_map.py) checks fixture themes,
   exact spans, edge/limit cases, authority, and subprocess CLI behavior.

## Verification

Verified on: 2026-10-20
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline pytest -q
Verification mode: fixture
Verification result: passed
Verified scope: 36 tests covering supported themes, exact citations, Unicode provenance, deterministic replay, duplicate accounting, empty/small/disconnected inputs, malformed/limit rejection, source instructions as data, network denial, CLI output, safe file reads, and cancellation.

The suite passed under CPython 3.14.8 on macOS. Setup with
`UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline` also passed.
Ten additional CLI scenarios exercised the packaged default, text rendering,
no match, empty corpus, singleton, small corpus, repeated IDs, selection
truncation, invalid options, and malformed JSON. The default JSON and text
examples selected six synthetic papers and produced four themes.

A copy containing only this case passed the same 36 tests with credentials and
`PYTHONPATH` absent from its environment. In that copy,
`uv build --offline --wheel --out-dir artifacts/wheels` succeeded.
`uv venv --python 3.14 /tmp/agent06-isolation-q1atnw9f/wheel-env` and
`uv pip install --offline --python /tmp/agent06-isolation-q1atnw9f/wheel-env/bin/python /tmp/agent06-isolation-q1atnw9f/case/artifacts/wheels/agent_atlas_scientific_research-0.1.0-py3-none-any.whl`
installed the wheel. Running its `scientific-research --objective "retrieval evaluation"`
entry point from a separate directory produced four themes using packaged data.
These temporary paths record the actual run, not setup requirements.

Independent review exercised 300 generated Unicode/duplicate/permutation/provenance
cases, five additional malformed inputs, and identical CLI JSON across three
hash seeds. Its Unicode validation finding was fixed. A fresh focused review
passed 21 tests and found no unresolved actionable findings. The parent ran
`python3 scripts/check_structure.py`, local Markdown-link checks, and
`git diff --check` for integration.

All runtime evidence is fixture-based. There is no live provider/model mode.
Hosted CI, deployment, real-literature usefulness, and scientific validity are
unverified.

## Limitations and references

Lexical overlap can join unrelated topics or miss synonyms. The theme target is
advisory. Sentence splitting treats `.!?` as boundaries and is not a linguistic
parser. Consensus, disagreement, study quality, and research gaps are not
assessed. Human review is required before drawing research conclusions.

This case adapts the workflow described in Imran Ahmad, *30 Agents Every AI
Engineer Must Build* (Packt, March 2026), Chapter 6, printed pp. 161–169
(PDF pp. 192–200). The corpus and implementation are original. Python's
[JSON hooks and integer limits](https://docs.python.org/3.14/library/json.html),
[regular-expression match spans](https://docs.python.org/3.14/library/re.html#re.Match.span),
and [Unicode string indexing](https://docs.python.org/3.14/library/stdtypes.html#text-sequence-type-str)
inform the strict parser and exact citation offsets.
