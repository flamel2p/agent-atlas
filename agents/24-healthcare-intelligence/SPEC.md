# Healthcare Intelligence Agent specification

Slug: 24-healthcare-intelligence
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Problem and source boundary

An original, wholly fictional evidence exercise demonstrates normalization, Bayesian updates, provenance, incomplete or conflicting knowledge, and simulated review. The fixed conditions `amber-pattern`, `violet-pattern`, and `teal-pattern` and signals `glimmer` and `ripple` have no medical meaning. No diagnosis, treatment, clinical thresholds, real records, EHR, network, model, external alert, or clinical efficacy or calibration claim is supported.

The [source brief](../../agent-library-analysis/agents/24-healthcare-intelligence.md) records book claims and incomplete sketches. [Foundations](../../agent-library-analysis/foundations.md) inform the separation of source data and host authority. Neither source owns this executable contract. Parent selected a case-local standard-library kernel after two design passes in the [batch plan](../../docs/AGENTS_22_32_PLAN.md).

## Input schema and bounds

Every object has exactly the fields listed below. No arbitrary text or instructions are accepted. Input is UTF-8 JSON, at most 65,536 bytes, depth 8 containers, and 2,048 JSON nodes. Duplicate keys, unknown or missing fields, nonfinite numbers, booleans, null, unsupported types, malformed UTF-8, lone surrogate strings, and numerical tokens over 32 characters are invalid. Numeric tokens have absolute exponent at most 12. Arrays have the bounds below. All validation completes before evidence processing. Exceeded bounds return `limit`.

- Root fields are `schema_version` equal to `synthetic-1`, `as_of`, `priors`, `observations`, `knowledge`, and `review`.
- `as_of` and all timestamps use exact UTC `YYYY-MM-DDTHH:MM:SSZ` form with valid calendar dates. Observation and retrieval times must be at or before `as_of`.
- `priors` has exactly the three fictional condition keys. Each is a JSON number in [0,1] and their exact decimal sum is 1. Zero priors are permitted.
- `observations` contains 0 to 2 objects with `id`, `signal`, `value`, `unit`, and `observed_at`. IDs are unique ASCII `[a-z][a-z0-9-]{0,31}` strings. Signals are unique and chosen from `glimmer`, `ripple`. Values are JSON numbers. `ticks` values are in [0,1], `milli_ticks` in [0,1000]. Canonical ticks equal value or value/1000. The fictional band is `high` at canonical value >= 0.5, otherwise `low`. These are toy encoding rules with no physiological meaning.
- `knowledge` contains 0 to 16 objects with `id`, `signal`, `band`, `source`, `version`, `retrieved_at`, and `likelihoods`. IDs are unique under the same ASCII rule. Source and version follow that rule too. Signal uses the same fixed taxonomy. Band is `low` or `high`. `likelihoods` has exactly the three condition keys with numbers in [0,1]. These are P(band | condition), so they need not sum to 1. An all-zero vector is permitted structurally and produces unresolved zero mass when relevant.
- `review` is `pending`, `acknowledged`, or `rejected`. This is a simulated input decision, with no authenticated identity or real approval authority.

There are no configuration files, environment secrets, model prompts, persistent state, or runtime dependencies. The CLI accepts one optional `--input PATH` regular nonsymlink file. Without it, the packaged original fixture is used. FIFO, devices, directories, and symlinks are rejected without reading. The CLI reads at most the byte bound plus one. It does not accept stdin or URLs.

## State and execution

Immutable `Observation`, `KnowledgeRecord`, `BeliefDistribution`, `EvidenceEvent`, `ReviewResult`, and request/report records belong to one run. The host processes signals in fixed taxonomy order, independent of input order. Knowledge provenance contains each matched record's ID, source, version, and retrieval time; observation ID and time remain attached to the event. Provenance identifies supplied records and does not authenticate their truth or integrity.

1. Strictly parse and validate the entire request, including unused knowledge.
2. Normalize observations into exact rational ticks and derive the toy bands.
3. Require both signals, observations no older than 24 hours, and at least one matched knowledge record per observed band. Require all matched knowledge no older than 30 days. Exact freshness boundaries are inclusive. Unmatched stale knowledge is irrelevant.
4. Retain every matched record. If their likelihood vectors differ numerically, mark `conflicting_knowledge`. No source or version wins automatically, including if one record is stale. Identical matches corroborate provenance but contribute one likelihood vector per observation. Repeated evidence is never multiplied twice.
5. If any completeness, freshness, or conflict condition failed, stop with `unresolved` and a null posterior. Otherwise multiply each prior by each observed band's likelihood, and normalize positive total mass. Exact rational arithmetic avoids positive-mass underflow. Zero total mass returns `unresolved` with `zero_mass` and a null posterior. No partial posterior is published.
6. Valid positive posterior plus `pending` returns `review_required`. `acknowledged` returns `simulated_reviewed`; `rejected` returns `review_rejected`. Unresolved evidence always overrides a review decision. Each report states `real_approval: false` and `effect: none`. No recommendation is generated.

At most 2 observations x 16 knowledge matches and 3 conditions are processed, with no retries, repair, fallback, or background loop. Reports are JSON on stdout only. The process performs no report-file writes. Caller shell redirection is outside the program's authority. KeyboardInterrupt returns `cancelled` with no later evidence processing. No cancellation or review input grants an external effect.

## Output and failures

A domain report contains `schema_version`, `mode: fixture`, `outcome`, `as_of`, `priors`, `posterior`, `evidence`, `issues`, and `review`. Belief entries contain each condition plus `probability` as an approximate JSON float and `exact` as a reduced fraction string. Decisions use exact values. Evidence entries contain observation ID/time, signal, normalized ticks as an exact fraction, band, and matched provenance. Issues contain stable `code`, nullable signal, and implicated record IDs. Review contains the input decision, `real_approval: false`, and `effect: none`.

Malformed input returns a small error report with `mode: fixture`, `outcome: invalid_input`, a stable error code, and no input echo or posterior. Bounds return `limit`, local I/O failures return `io_error`, and interruption returns `cancelled`. Exit codes are 0 for all valid domain outcomes including unresolved review, 2 for invalid input or limit, 3 for I/O, 130 for interruption, and 1 for a closed output pipe. Parse errors contain no source input, path, or secret-bearing exception text. Domain results are not a real-world success signal.

## Acceptance criteria

- The normal fixture starts from (1/2, 3/10, 1/5), applies glimmer-high (4/5, 1/5, 1/10) and ripple-low (1/2, 1/4, 3/4), and returns (20/23, 3/46, 3/46). Preserve source/version/time and normalized ticks.
- Unit-equivalent and reordered observations return the same beliefs. Identical source records do not double-count likelihoods. Reject unsupported labels and incompatible units.
- Missing, stale, conflicting, and zero-mass evidence returns unresolved with no posterior. Review acknowledgements cannot override this state. Invalid probabilities never enter arithmetic.
- Check duplicate keys, unknown fields, nonfinite values, booleans, malformed times, byte/depth/node/numerical bounds, symlinks/nonregular files, broken output pipes, and isolated runs.
- Run tests, actual CLI, isolated case copy, and installed wheel from outside the repository. Keep rerunnable qualification tooling local. Independent review remains parent-owned and is required before readiness.

## Evidence limits

All evidence is original fixture behavior. No provider, live model, real professional service, deployment, production, empirical independence, or calibration validation is claimed. Runtime arithmetic assumes conditional independence of these authored likelihoods. Changing that assumption or accepting real clinical inputs requires a separately approved contract.
