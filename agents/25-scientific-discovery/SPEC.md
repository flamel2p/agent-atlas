# Scientific Discovery Agent specification

Slug: 25-scientific-discovery
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose, sources, and selected decision

Find an untested pair in an original synthetic corpus, construct a grounded falsifiable additive hypothesis, plan a constrained virtual experiment, and compare its prediction with supplied simulated measurements. This goes beyond case 06's literature mapping. No real literature service, network, model, laboratory, training, or scientific discovery claim exists.

The [source brief](../../agent-library-analysis/agents/25-scientific-discovery.md), [inventory](../../agent-library-analysis/agent-inventory.md), and [foundations](../../agent-library-analysis/foundations.md) supply pattern context, not execution evidence. Their incomplete source clients and relative-error example are not reused. Absolute error permits zero measurements. The selected implementation is original.

## Strict input contract

The CLI accepts `--input FILE` or defaults to packaged `fixtures/planted.json`. UTF-8 JSON input is at most 65536 bytes, nesting depth 12, 4096 total JSON values, and 2048 characters per string. Files must be regular files opened without following a final symlink, then read with a byte bound. Unknown or duplicate keys, nonfinite numbers, booleans in numeric positions, bad UTF-8, and malformed types are invalid. Identifiers match `[a-z][a-z0-9_-]{0,39}`. Arrays below are unique unless noted. No text field is an instruction.

The exact root object has `schema_version` (integer 1), `corpus_id` (identifier), `topics`, `required_sources`, `sources`, `constraints`, and `measurements`.

- `topics` contains 2..8 objects with exactly `id` and `label` (nonblank string, at most 120 characters), unique IDs.
- `required_sources` contains 1..8 source identifiers. This is the caller's declared coverage scope, never an exhaustive literature manifest.
- `sources` contains 0..8 objects with exactly `id` and `papers`. Source IDs are unique and must be declared in `required_sources`. Each `papers` array contains 0..16 papers, at most 64 overall.
- Each paper has exactly `id`, `title` (nonblank, at most 200 characters), `topics` (1..2 known unique topic IDs), `effect` (finite number in -100..100 synthetic response points), `evidence` (nonblank, at most 1000 characters), and `citations` (0..8 paper IDs). Paper IDs are unique across sources. Citations may reference missing papers; these mark coverage incomplete. Self-citations are invalid. Paper fields are supplied synthetic assertions; prose is carried as evidence, never scientifically verified.
- `constraints` has exactly `max_runs` (integer 0..100), `max_cost` (finite number 0..1000 synthetic credits), and `tolerance` (finite number 0..100 response points).
- `measurements` contains 0..28 objects with exactly `pair` (two distinct known topic IDs) and `values` (exactly three finite numbers in -200..200 response points). Pair order is immaterial. Duplicate pairs are invalid. These are supplied simulated outcomes, not independently generated observations.

Packaged fixture resources use the same input parser. There are no credentials or environment settings.

## Domain and deterministic flow

Frozen typed records scope all state to one invocation. Arithmetic uses Python binary64 floats and `statistics.fmean`; comparisons use those computed values with no hidden rounding or statistical calibration. `CorpusRecord` owns topics, papers and declared sources. `CoverageRecord` records missing sources, empty sources, missing citations, and topics without singleton evidence. A singleton paper studies one topic. A pair paper marks that unordered pair as tested regardless of its reported effect. The complete-coverage label refers only to declared synthetic inputs.

1. Validate the entire request before domain work. Hash the original bytes using SHA-256 and retain that identity in every valid report.
2. Compute coverage. A missing source, source without papers, missing citation, or missing singleton evidence for any topic means `coverage_incomplete`. Return without hypothesis, plan, or feedback. Novelty remains `unverified`.
3. Enumerate at most 28 unordered topic pairs. Remove pairs studied in any paper. Rank remaining candidates lexicographically by their canonical topic IDs, independent of input order. Select at most one. If none remain return `no_gap`.
4. For the selected pair, compute each topic's arithmetic mean effect from all its singleton papers. Predict the sum of those means. Retain all singleton evidence, citations, source IDs, and observed effect ranges. Disagreement is visible; no confidence or consensus is inferred.
5. Produce a `Hypothesis` stating that the combined effect is within `tolerance` of the additive prediction. It is falsified in this virtual exercise when absolute error exceeds tolerance. This is an unvalidated extrapolation, not a causal or scientific claim.
6. Produce an `ExperimentPlan` with baseline arm (prediction 0), each single-topic arm (its mean), and combined arm (sum). Each arm has three repeats, for exactly 12 runs at 2 synthetic credits per run, cost 24. If either budget is insufficient return `constraint_blocked`; no simulated measurements are consumed.
7. If the selected pair lacks measurements return `awaiting_measurements` with its feasible plan. Otherwise consume its three supplied simulated combined-arm values once, compute their arithmetic mean, and compute `abs(prediction - mean)`. Error <= tolerance yields `consistent_with_prediction`, otherwise `prediction_refuted`. This comparison is descriptive and has no significance test. Controls are a proposed plan only; the report explicitly says the supplied data covers the combined arm only.
8. Return `completed` and stop. No updates to model weights, host rules, corpus, filesystem state, or subsequent runs occur.

## Output and authority

A valid JSON report has exactly `schema_version`, `status`, `input_sha256`, `corpus_id`, `coverage`, `novelty`, `candidates`, `hypothesis`, `experiment`, `feedback`, `trace`, and `limitations`. Domain records serialize as JSON objects. Absent stages are `null`. Coverage includes `complete`, sorted `declared_sources` and `observed_sources`, `tested_pairs` with their paper IDs, and each missing-evidence list. Novelty has `scope: supplied_synthetic_corpus`, `global: unverified`, and `corpus_gap: unverified | observed | absent`. Candidates include canonical `pair`, tested-pair exclusion provenance is visible in coverage, and each hypothesis contains exact supporting evidence objects. Trace lists only reached stages and the terminal status. All valid reports state synthetic-only interpretation and combined-arm-only measurements.

Host code alone owns validation, pair ranking, arithmetic, budget checks, and terminal states. The only application output is JSON on stdout. No arbitrary path output, input-driven code, subprocess, network, persistent memory, or tool dispatch is exposed. Runtime Python/uv caches are outside this application-effect claim.

CLI exit 0 means a valid domain report, including unresolved states. Exit 2 means invalid input or input I/O failure and emits a small JSON error to stderr without input text. Exit 130 handles interruption. Exit 1 handles closed output pipes, including buffered, unbuffered, and help output, without traceback or shutdown flush noise. There is no retry or repair loop. A cancellation before report emission emits no partial report or simulated external action.

## Acceptance criteria

The original fixture has three topics, single-topic evidence, two tested pairs with internal citations, and the planted `aerogel`/`pulse` gap. Means 4 and 6 give prediction 10. Measurements 8, 10, 9 give mean 9 and absolute error 1. Tolerance 1 counts as consistent. Zero measurements yield finite error 10. Independent expected arithmetic checks must also cover conflicting evidence aggregation and refutation.

Meaningful checks cover incomplete sources/citations/singleton evidence, no gap, unavailable measurements, exact budgets and blocked budgets, ordering invariance, adversarial instruction text, schema/size/depth/number validation, regular-file input policy, deterministic isolation, and closed stdout/help. Qualification runs the documented CLI, a standalone case copy, and installed-wheel resource execution outside the repository via a rerunnable local script. Independent review and parent integration remain required before `demo-ready`. Live model, external literature, scientific validity, deployment, and production remain unverified.
