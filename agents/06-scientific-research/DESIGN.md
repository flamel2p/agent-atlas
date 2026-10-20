# Scientific Research Agent design

## Usage

```sh
uv run --locked scientific-research --objective "retrieval evaluation"
uv run --locked scientific-research --objective "retrieval robustness" --format text
uv run --locked scientific-research --objective "retrieval evaluation" --corpus private-data/corpus.json
```

`parse_corpus(bytes) -> Corpus` validates one immutable snapshot.
`map_literature(Corpus, ResearchRequest) -> LiteratureMap` owns ranking, grouping,
and exact evidence selection. The CLI renders the report and controls I/O.

## Shape and rationale

The Model the Domain principle led to frozen records for corpus provenance,
research requests, ranked papers, themes, and evidence spans. One pure mapping
operation hides clustering and evidence rules behind a small interface.
The full contract lives in [SPEC.md](SPEC.md).

Two independent design candidates agreed on a deterministic extractive map.
Candidate A proposed weighted TF-IDF cosine and threshold clustering. Candidate B
proposed exact Jaccard fractions and complete-link merging toward a target,
stopping when no lexical support remains. B is the selected base because it
avoids a fixture-tuned threshold and exposes why a target can remain unmet.
A's cluster-local citation constraint and simple entry point are retained.
An independent cross-judge also selected B and required explicit tokenization
and span rules, now recorded in the README.

| Alternative | Decision |
| --- | --- |
| Jaccard search and support-aware complete-link grouping | Selected. Exact scores, bounded work, explicit stopping rules. |
| TF-IDF search and fixed-threshold grouping | Rejected for this demo. The threshold adds calibration without a demonstrated need. |
| Fixed taxonomy with evidence buckets | Rejected. It teaches classification into predefined themes. |
| Embeddings with k-means and a live repository | Deferred. Model assets, API access, licensing, and semantic quality need separate evidence. |

Lexical grouping can join papers because they share incidental vocabulary.
Complete-link requires every cross-pair to overlap but cannot prove conceptual
coherence. Synthetic fixtures demonstrate the mechanics, not research quality.

## Implementation plan

1. Define the strict corpus boundary, identity rules, and provenance records.
2. Implement a complete search/group/extract path with exact evidence validation.
3. Add original fixtures, meaningful edge cases, CLI rendering, and packaging.
4. Run fixture tests, CLI scenarios, isolated installation, and wheel execution.
5. Reconcile independent review and synchronize README/SPEC/catalogue evidence.

Source research and design exploration run independently. One builder owns the
coupled implementation in an exclusive checkout. The parent integrates the case
and root catalogue after verification. This follows Separate Before Serializing
Shared State. Prove It Works requires actual CLI and installed-package execution.

## Reconciliation

The implementation uses `paper_id`, `source_id`, and `synthetic` as JSON field
names. Case-folded Unicode word runs excluding underscores and a fixed 21-word
stoplist drive both search and grouping. Sentence-like spans use `.!?`; a valid
punctuation-only abstract falls back to its exact nonblank text. The report
exposes original and removed record counts so identical same-ID repeats cannot
disappear silently. POSIX `O_NOFOLLOW` rejects the final path component if it
is a symlink; ancestor symlinks remain allowed for caller-selected paths. These
choices preserve the selected bounds, authority, evidence semantics, and failure
behavior.

Independent review identified an overly broad Unicode guard. The parent narrowed
it to control, format, and surrogate categories and added exact-provenance
regressions for private-use and unassigned code points. The application-effects
contract now explicitly distinguishes Python/uv caches from report files and
persistent agent state. CLI checks run without disabling bytecode caches.
A fresh reviewer confirmed the fix with 21 focused passing tests. The parent
completed the 36-test suite, case-only installation, installed-wheel execution,
and catalogue integration. [README verification](README.md#verification) records
the commands and evidence limits.
