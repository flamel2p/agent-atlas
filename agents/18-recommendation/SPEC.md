# Recommendation Agent specification

Slug: 18-recommendation
Status: demo-ready
Runtime: Python 3.14 (uv CLI, POSIX)

## Problem and scope

Help a learner choose synthetic programming exercises from explicit interests and eligibility constraints. The learning objective is an inspectable content-based recommendation decision with host-owned filtering, scoring, cold-start behavior, and bounded termination.

This is a one-shot deterministic decision agent under the repository foundations' broad taxonomy. It is an independently designed extension for reference 18. It has no learned model, collaborative filtering, hybrid architecture, inferred preferences, feedback learning, persistent user identity, or runtime network.

## Evidence and decisions

The retained [source brief](../../agent-library-analysis/agents/18-recommendation.md) records a Preface synopsis and teaser without a developed recommendation section. No implementation architecture or evaluation is attributed to the missing book treatment. [SOURCES.md](SOURCES.md) preserves those locators and separately verified primary guidance.

Selected decisions are a fixed original synthetic exercise catalogue; explicit weighted topic interests; prerequisite skills distinct from topics; integer dot-product scoring; deterministic ordering; and stdout-only reports. Google guidance supports the general content-based feature approach. The exact scenario, policies, bounds, fixtures, and acceptance criteria are project decisions. No material scope question remains.

## Inputs and outputs

The CLI uses the packaged catalogue and either a packaged scenario or one caller-selected UTF-8 JSON request file. With no arguments it runs the normal scenario. No catalogue path, output path, URL, shell command, or user/session ID is accepted. CLI request and scenario options are mutually exclusive. All JSON documents reject duplicate object keys and nonstandard constants.

All request fields are required. Unknown fields are invalid.

```json
{
  "topic_weights": {"python": 3, "testing": 2},
  "max_duration_minutes": 30,
  "max_difficulty": "intermediate",
  "completed_skills": ["python-basics"],
  "excluded_exercise_ids": [],
  "limit": 3
}
```

Topic weights are integers 1-100. Empty weights mean no stated interests. Difficulty is ordered beginner, intermediate, advanced. Duration is a per-exercise limit, not a budget for the sum of recommendations. Completed skills are caller assertions for filtering and do not establish mastery. Exclusions are exact catalogue IDs.

The catalogue contains a version, explicit topic and skill vocabularies, and exercises with unique ID, title, unique topic tags, integer duration, difficulty, and required skills. Version is nonblank text of 1-64 characters without control characters. Prerequisites reference skill identifiers rather than other exercises. There is no dependency graph traversal. Unknown topic, skill, or exercise references fail validation.

Identifiers match `[a-z][a-z0-9-]{0,63}`. Titles have 1-120 characters and cannot be whitespace-only or contain control characters. Each catalogue has at most 200 exercises, 100 topics, and 100 skills. An exercise has 1-10 topic tags and at most 20 required skills. Duration and maximum duration are 1-480 minutes. Limit is 1-20. Request collection sizes cannot exceed their corresponding catalogue/vocabulary bounds. Reject booleans in integer positions, duplicate list members, malformed types, missing/extra fields, and invalid enum values.

Each input document is at most 256 KiB, with a maximum of 32 nested containers counting the root container as one. Public Python calls must receive plain built-in JSON-shaped values within the same structural bounds. Their document size is the compact UTF-8 JSON representation. Excessive recursion, non-JSON values, non-finite numbers, or cyclic containers fail with a sanitized `InputError`, a `ValueError` subclass. An iterative structural walk and a bounded node count reject oversized Python containers before serialization. The pure public boundary is `recommend(request: object, catalogue: object) -> dict`. It validates both arguments before deriving domain records. The CLI fixes the catalogue to the packaged resource; the Python function accepts a bounded synthetic catalogue for direct use and tests.

A successful report contains policy/catalogue versions, independent-extension provenance, status and reason, request parameters, catalogue/eligible/matching/returned counts, ordered recommendations, rejected IDs with every applicable gate reason, and sorted unmatched eligible IDs. Every recommendation includes ID, title, duration, difficulty, integer score, and sorted matched-topic weight contributions. The contributions sum to the score. Reports declare the score meaning and ordering policy. Titles, timestamps, input order, randomness, and hidden user state never determine ranking.

The report uses `policy_version`, `catalogue_version`, `provenance`, `status`, `reason`, `request`, `counts`, `recommendations`, `rejected`, `unmatched_eligible_ids`, `score_meaning`, and `ordering_policy`. Counts contain `catalogue`, `eligible`, `matching`, `returned`, and `rejected`. Recommendations contain `id`, `title`, `duration_minutes`, `difficulty`, `score`, and `matched_topics` entries with `topic` and `weight`. Every rejected entry contains `id`, `reasons`, and `missing_skills`, including an empty missing-skills list when appropriate. Request collections are normalized for deterministic reporting.

## Architecture and state

One pure recommendation boundary owns validation, private immutable domain records, all eligibility gates, scoring, ordering, and report construction. A thin CLI owns argument parsing, bounded file/resource reads, strict JSON decoding, serialization, and exit status. Canonical catalogue and scenario requests are package data loaded with importlib.resources. No runtime depends on repository-root files, sibling cases, cwd-relative fixture paths, credentials, or a private sibling installation.

All state lasts for one call. No history, preference mutation, profile database, cache, clock, or background task exists. Changing explicit preferences affects only the next independent request.

## Tools and authority

The host may read its fixed package resources and the single request file explicitly selected by the caller. Reads are bounded regular-file reads; reject final-component symlinks and special files without blocking. Directory aliases such as macOS `/tmp` are permitted. No runtime file writes occur. The only normal output is one JSON report on stdout. Input failures produce one sanitized JSON error on stderr, empty stdout, and exit 2. Broken output or resource I/O failure must not report success or expose a traceback/private input.

The selected file-authority implementation requires POSIX `O_NOFOLLOW`, `O_NONBLOCK`, and `O_CLOEXEC`. It is qualified locally on macOS, with no Windows portability claim. Argument validation failures follow the same input-error contract. `--help` prints usage without loading inputs and exits 0 when output succeeds. Expected output/resource failures exit 1, including closed buffered and unbuffered stdout pipes and stdout descriptors closed before Python starts. A closed stderr cannot receive an error report, but the process preserves its nonzero exit, including when its descriptor was closed before startup. Keyboard interruption exits 130 without persisted state.

No model or retrieved instruction can propose actions. Strings in requests and catalogue are data. There are no shell, provider, browser, database, messaging, or external fulfillment tools. Shell redirection is the caller's authority, not a program output-path capability.

## Execution and termination

1. Read bounded input and validate the complete request and catalogue before ranking.
2. Inspect every exercise once. Collect every applicable hard rejection in fixed order, `excluded`, `duration`, `difficulty`, `missing_skills`. A missing-skills rejection lists the sorted missing skill IDs.
3. Score only eligible items. A topic is a binary item feature. Weighted overlap is the sum of request weights for matching item tags. Nonmatching tags contribute zero. Scores measure this rule, not confidence, probability, or predicted benefit. Multi-topic items may score higher by matching more interests.
4. Apply one terminal outcome. With no eligible items, return `empty` and `no_eligible_exercises`. An empty catalogue is distinguishable by its zero catalogue count. With empty interests and eligible items, return `cold_start` with a labeled non-personalized baseline and score zero. With interests but no positive-score eligible items, return `no_match` with no recommendations. Otherwise return `personalized` with positive-score items only. Never pad with unrelated items or relax a constraint.
5. Sort recommendations by descending score, ascending duration, then ascending ID, and truncate to limit. In cold start the zero scores reduce ordering to duration then ID. Sort rejected and unmatched IDs lexicographically so catalogue permutation leaves the complete report unchanged.
6. Emit the report and stop. There is one scan and bounded sorts over at most 200 items, no retries, no open-ended loop, and no repeated tool calls. Process interruption ends computation without persisted effects. Valid empty/limit outcomes exit 0; invalid input exits 2; output failure exits nonzero.

Matching count means eligible items with positive topic overlap, including zero for cold start. Unmatched eligible IDs mean eligible items with score zero, including the eligible baseline population during cold start. The candidate counts must satisfy catalogue count = eligible count + rejected count. Returned count never exceeds limit or eligible count.

## Acceptance criteria

All selected criteria require fixture evidence only.

1. Hand-calculated weighted matches and preference changes produce the specified scores and ranking. Matched-topic contributions reproduce each score exactly.
2. Every hard gate can exclude an otherwise top-scoring exercise. All simultaneous reasons are visible, and duration/difficulty equality remains eligible.
3. Ties and catalogue permutations produce identical complete reports. Limits truncate after filtering and sorting. Unrelated items never pad personalized output.
4. Cold start is labeled non-personalized, no-match stays empty, and empty catalogue/all-filtered catalogues remain distinguishable.
5. Unknown references, duplicate IDs/keys/members, booleans, invalid bounds, malformed/oversized/deep JSON, and invalid direct Python inputs fail closed. Expected errors disclose no request content or traceback.
6. Sequential requests have no state leakage. No model, network, persistent state, or runtime file writes are required.
7. CLI normal, cold-start, constrained, no-match, no-eligible, invalid-input, special-file, and output-failure paths have actual subprocess evidence.
8. A separate CLI oracle derives constraints, ranking, explanations, and counts directly from fixture data without importing runtime scoring or validators. It passes in checkout, standalone case copy, and an installed wheel invoked outside the source directory.
9. Locked setup, case tests, source/wheel packaging, repository structure, explanations, reading-guide links, and independent substantive review pass before demo-ready.

## Dependencies and open decisions

Use uv-managed Python 3.14 and stdlib unittest. No runtime dependencies. Pin Hatchling 1.32.4 for packaging and retain a case-local lockfile and MIT notice. The selected runtime and cached backend were verified locally; official build configuration was checked on 2026-10-23. `recommendation.domain` owns private immutable records, validation, and ranking. `recommendation.documents` owns strict bounded JSON and reads. `recommendation.cli` owns CLI argument and output handling. Original synthetic data lives in `src/recommendation/data/`. No live-model, real learner-quality, hosted-CI, deployment, commit, or publication evidence is required or claimed.
