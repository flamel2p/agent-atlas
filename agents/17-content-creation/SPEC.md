# Content Creation Agent specification

Slug: 17-content-creation
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Problem and scope

A content author needs an email and documentation announcement that use the same approved product facts and obey explicit brand and structure constraints. This learning demo demonstrates a bounded draft, review, and revision loop. Review feedback must change real content choices. Attempts must not be selected by fixture name or attempt number.

This is deterministic constrained composition over synthetic evidence. It does not implement an LLM, arbitrary prose generation, semantic factual verification, publishing, media, analytics, persistent learning, or external tools.

## Evidence and decisions

Source facts are recorded in [SOURCES.md](SOURCES.md), based on the retained analysis of Chapter 10, printed pages 293-306 and physical PDF pages 324-337. The source describes researcher/writer/editor responsibilities and brand constraints. Its concrete retry loop can return invalid best-effort content, and its analytics are mock values.

Selected decisions are original to this implementation. Use exact approved complete fact sentences and a closed vocabulary of connective copy. Evaluate actual rendered drafts. Preserve rejected attempts and reject exhausted content. All runtime state belongs to one invocation. The [implementation plan](PLAN.md) records design alternatives and verification gates.

## Inputs and outputs

`content-creation` runs the packaged launch brief by default. `--scenario NAME` selects a packaged example by allowlisted name. `--brief PATH` reads a caller-selected local JSON brief. The two options are mutually exclusive. Reading a brief does not grant writes or execution.

A brief contains exactly these fields:

- `audience`, one of `team_leads` or `developers`.
- `required_fact_ids`, 1-6 unique IDs from the bundled evidence.
- `forbidden_phrases`, 0-16 nonempty phrases unique after casefolding and whitespace collapse, each at most 80 characters after stripping.
- `email_max_words` and `docs_max_words`, integers from 1 through 500. Booleans are invalid.

Reject unknown or missing fields, duplicate JSON keys, non-finite numbers, invalid UTF-8, unpaired surrogates, unsupported control characters, invalid types, unknown IDs, and files over 16 KiB. Tab, newline, and carriage return are supported whitespace within phrases. Other Unicode control characters and surrogate code points are rejected. Bound JSON nesting to 16 levels, total values/keys to 4,096, and integer tokens to 20 characters. No schema field accepts floating-point numbers.

Brief files must be regular files. Reject final-file symlinks and special files without blocking. Directory aliases such as macOS `/tmp` are allowed. Inspect the final filename without following links, open it with nonblocking and no-follow flags, and confirm its regular-file identity through the descriptor. Raw error text must not echo input contents. Valid but impossible constraints reach an unapproved outcome rather than being silently relaxed.

The fixed packaged JSON content fixture contains the synthetic product LumenBoard, six complete qualified fact sentences, stable fact/source IDs, fixed copy alternatives, and audience priorities. Validate internal identities, references, size bounds, and uniqueness before use. Read at most 32 KiB plus one byte once per run, reject oversized data, compute SHA-256 from those same bytes, and construct immutable values. Packaged brief reads use the 16 KiB limit. The digest identifies a snapshot, not truth or authenticity. Package loading uses fixed resource names.

The CLI emits one deterministic JSON report on stdout for a valid run. It contains overall `status` (`validated` or `unapproved`), `approval` (`not_granted`), fixture digest, and exactly two artifact reports, email then documentation. Each artifact contains status, its attempts, and a `validated_text` value populated only on a passing final review. Unapproved artifacts have `validated_text: null` and retain their drafts and actual violations. Output is reusable content with audit evidence, not a publication instruction.

Every attempt contains its number, rendered text, computed word count, fact evidence, violations, and concrete next changes when another attempt follows. Evidence contains fact ID, source ID, fixture digest, and zero-based, end-exclusive Python character offsets into the rendered text. The text at each range must equal the complete canonical fact sentence. Every factual block has exactly one evidence record, and every evidence record maps to an actual factual block. Missing, extra, duplicate, mismatched, or altered evidence fails review.

Exit 0 means both artifacts validated. Exit 1 means a valid brief produced unapproved content. Exit 2 means invalid input, fixture failure, or output I/O failure, with a bounded diagnostic on stderr. Invalid input produces no campaign report. Keyboard interruption exits 130. Flush stdout before returning success so buffered write failures cannot appear successful.

## Architecture and state

The public domain operation is `create_content(brief: Brief) -> RunResult`. Immutable types represent the brief, draft blocks, evidence, violations, attempts, and terminal reports. Validate Python API input as well as CLI JSON boundaries.

Keep content grammar, rendering, pure review, and deterministic repair policy under one case-owned domain module. A separate boundary module may load/validate input and packaged data when it reduces reader load. The CLI owns parsing, serialization, and exit codes. Do not create framework roles that merely forward shared state.

The controller alone owns per-artifact plan choices, rejected copy alternatives, selected optional facts, and attempt history. The renderer and reviewer do not change them. All state is invocation-local. Passing an artifact freezes it while the other channel completes. Separate runs cannot share mutable state.

## Tools and authority

There are no model tools or runtime network calls. The application can read its packaged fixture and the explicitly selected brief. It writes only stdout/stderr. Shell redirection, if the caller uses it, belongs to the shell. No output-path flag, subprocess execution, credential discovery, provider configuration, or file mutation is implemented.

The host owns facts, copy vocabulary, structure, review policy, and retry budget. A proposed content block cannot alter those rules. Exact fixture agreement establishes consistency with synthetic approved inputs only. It does not establish real-world truth, tone, persuasion, legal compliance, or human approval.

## Content constraints

Email sections are `Subject`, `Introduction`, `Details`, and `Next step`, exactly once in that order. Documentation sections are `Title`, `Summary`, `Changes`, and `Next step`, exactly once in that order. Every section contains a permitted block.

Required facts occur exactly once in Details or Changes, retaining caller-supplied order. Optional facts use ascending audience priority rank with stable ID tie-breaking. Required facts and qualifiers cannot be removed or rewritten to fit length. Every product assertion must be an exact fact block; remaining text must match a permitted structural literal or curated copy variant. A valid citation attached to arbitrary text is insufficient.

Both artifacts must contain the canonical product spelling and no exclamation mark. Forbidden phrases are compared by Unicode casefolding and collapsed whitespace, as literal substring matches. This is a mechanical rule, not semantic tone analysis. Word count is the number of whitespace-separated tokens in the entire rendered text, including headings. The count must not exceed the selected channel maximum.

The reviewer evaluates the actual text, block structure, evidence, required coverage, vocabulary, and length. It must detect altered text even when a proposed draft retains plausible source IDs. Structural literals and copy variants are trusted synthetic inputs whose meaning is not independently verified.

## Execution and termination

1. Validate inputs and freeze the fixture snapshot. Build both channel plans with required facts, audience-ranked optional facts, and preferred copy.
2. Render the candidate and review it. Record the actual text, provenance, word count, and all observed violations.
3. If no violations remain, return `validated` for that artifact and freeze its text.
4. Otherwise select repairs from the current violations. Use stable priority: provenance or structure, brand, then length. Choose one repair category per revision. Integrity violations stop that artifact because the canonical renderer has no legal plan transition that introduces them. Copy rejection selects the next untried variant of the offending block; a banned optional fact may be removed. A brand revision may repair multiple offending blocks in that category. Length repair drops the lowest-priority optional fact first, then chooses the largest word saving from untried shorter copy, with stable slot/variant tie-breaking. Preserve required facts and sections.
5. If no legal change exists, stop with `unapproved_no_repair`. Never repeat an unchanged plan. Corrupt factual content stops revision of that artifact; it is never invented or paraphrased.
6. Re-render and re-review each changed plan. At most three reviewed drafts exist per artifact, the initial draft and two revisions. Remaining violations on attempt three produce `unapproved_limit`. Never record a next change after the final attempt.
7. Overall status is `validated` only if both artifacts validated. Partial success remains visible under overall `unapproved`. `approval` remains `not_granted` for every result.

The finite input and plan sizes bound work. No sleeps, network waits, or retries of external effects occur. An input/fixture failure is terminal before drafting. Interruptions produce no success report. Broken output is an I/O failure, even if validation completed internally.

## Acceptance criteria

All selected criteria require fixture evidence. None requires a live provider.

1. Default launch produces both channels within three attempts, with at least one real rejected draft and a changed passing revision.
2. Relaxed brand constraints pass immediately when all other constraints pass. Changing forbidden wording changes the observed feedback and selected copy, without scenario-dependent logic.
3. Achievable tighter length removes optional material or chooses shorter copy while preserving required facts, sections, and exact provenance.
4. Banning every opening alternative reaches three failed reviews and an unapproved terminal result. Impossible required facts or length cannot produce validated text.
5. One passing channel and one failing channel produce overall unapproved, preserving the passing artifact without further revisions.
6. Mutated factual text with a real fact ID, forged offsets/digest/source, missing/extra citations, unknown copy, duplicate/missing required facts, and damaged section order all fail review.
7. Malformed/oversized/unsafe brief inputs and invalid direct Python inputs fail before drafting. Boundary word counts, Unicode normalization, and output write failures have meaningful checks.
8. Repeated runs are deterministic and independent. Attempt history records actual changes and stays bounded. Inputs and fixture bytes remain unchanged.
9. Documented commands work in a copied case and an installed wheel from an unrelated working directory, with no sibling/root runtime files or provider credentials.
10. Independent review resolves actionable findings. README, source explanations, SPEC, and catalogue describe the same behavior and evidence limits.

## Dependencies and open decisions

Use CPython 3.14, uv, Python standard-library runtime and tests, and Hatchling 1.32.4 as build backend. Pin the Python minor version and backend, maintain a case-local lockfile, and package fixture resources. Safe caller-file handling uses POSIX descriptor flags available on macOS and Linux; Windows is unqualified. Official reference checks are in SOURCES.md. No provider API or framework dependency is selected.

Concrete synthetic copy and example word ceilings are routine implementation choices. Record them in fixtures and derive boundary checks from actual rendered output. No material product decisions remain open for this fixture scope. A future live writer, arbitrary prose, external research, or publishing requires a separately scoped behavior contract.
