# Self-improving agent specification

Slug: 15-self-improving
Status: demo-ready
Runtime: Python 3.14, uv, standard library runtime, unittest

## Problem and scope

An FAQ maintainer needs to distinguish a supported retrieval improvement from feedback overfitting. One experiment replays synthetic baseline failures, validates corrections against separate host curator records, proposes one topic-scoped revision tie-breaker, and evaluates that frozen proposal once. A passing proposal requires human review. Every outcome retains the baseline as serving behavior.

The experiment demonstrates controlled configuration learning. It does not train a model, infer topics, edit answers, run a continuing service, deploy, record human approval, or roll back a deployment.

## Evidence and decisions

Source facts come from Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 9, "The Self-Improving agent": architecture printed pp.265-268 / PDF pp.296-299; feedback and adaptation printed pp.269-271 / PDF pp.300-302; support case printed pp.272-275 / PDF pp.303-306; safeguards printed pp.276-277 / PDF pp.307-308. PDF locators count physical pages from one. The source describes feedback curation, versioned changes, heldout comparison, human governance, and rollback. Its gains are unverified case-study claims. Its scheduler, numeric evidence threshold, candidate algorithm, authentication, and deployment implementation remain unspecified. The planner's example review flags conflict with the governance narrative.

Selected behavior is independently implemented from the retained [source brief](../../agent-library-analysis/agents/15-self-improving.md), [inventory](../../agent-library-analysis/agent-inventory.md), and [foundations](../../agent-library-analysis/foundations.md). Design A supplies the pure experiment, separate curator manifest, normalized-query deduplication, development controls, and immutable run-scoped lineage. Design B supplies topic-scoped adaptation. The selected ranking is a tie-breaker, not either proposal's additive recency score. Source gaps remain limitations rather than implied functionality.

## Inputs and outputs

`load_scenario(ScenarioName)` reads exactly three bundled JSON files for an allowlisted scenario and returns frozen `ScenarioData`. `run_experiment(ScenarioData)` accepts that validated value and returns a frozen terminal report. The CLI prints canonical JSON plus one newline. Python callers can render a report with `report.to_json()`.

Each scenario has `selection.json`, `curators.json`, and `holdout.json`. All envelopes require `schema_version=1`. Selection contains `corpus`, baseline `config` with `recency_topic=null`, baseline `traces`, untrusted `feedback`, and `development_controls`. Curators contains separate host `records`. Holdout contains labeled `cases` in nonempty `recent` and `stable` groups. The fixture loader constructs the baseline identity from its validated corpus and configuration; traces carry `baseline_version_id`, which must replay against that exact identity to count as support.

Documents have `document_id`, `topic`, positive integer `revision`, normalized distinct `tokens`, and `answer`. Queries have `query_id`, `topic`, and normalized distinct `tokens`. Tokens are lowercase ASCII alphanumeric strings. Query signatures are the topic and sorted token set, independent of query IDs and input token order. IDs and topics match `[a-z][a-z0-9_-]*`. Revision order is synthetic order, not a freshness date guarantee.

Traces have `trace_id`, `query`, `baseline_version_id`, and nullable `observed_document_id`. Feedback has `feedback_id`, `trace_id`, `target_document_id`, and `curator_record_id`. Host records have `record_id`, `trace_id`, and `target_document_id`. Host records must reference known traces and same-topic, positive-overlap documents. Each trace has at most one host record. Structurally valid untrusted feedback may name unknown references and is excluded with an explicit reason. Feedback cannot self-declare approval or add instructions. Such unknown fields are schema errors.

Labeled examples contain `query`, nullable `expected_document_id`, and `group`. Development controls use `group=development`. Holdout uses `recent` or `stable`. Non-null labels reference same-topic positive-overlap documents. Null labels represent an expected no-answer. Holdout query IDs and signatures are disjoint from all trace and development queries. Trace query IDs are unique. Repeated signatures among traces are permitted but cannot multiply support. Development query IDs and signatures are unique and disjoint from traces.

The decoder rejects unknown or missing keys, duplicate JSON keys, nonfinite numbers, duplicate record IDs, invalid references in host data, malformed types, booleans as integers, and resource excess. Hard caps are 1 MiB per file, JSON nesting depth 16, 100 documents, 100 traces, 100 feedback records, 100 curator records, 100 development controls, 100 heldout cases, 64 tokens per document/query, 32 characters per token, 64 characters per ID/topic, 2,000 characters per answer, and revision at most 1,000,000. Every file is read with a cap before decoding. Empty corpus, query tokens, document tokens, and either holdout group are errors. Other record lists may be empty.

Reports contain schema/algorithm versions, scenario name, corpus/selection/holdout digests, complete baseline snapshot, serving baseline ID, feedback decisions, and terminal reasons. A created proposal includes candidate configuration and parent ID, supporting feedback IDs, topic, and evidence digest. Full supporting feedback, replay traces, and host curator records allow the support digest to be recomputed from the report. Development evidence appears only after a proposal exists. Heldout evidence appears only after development passes. Evaluated reports contain every query's before/after choice, exact-ID correctness, group counts, gained IDs, and lost IDs. No-candidate reports have no candidate or invented metric. The report digest hashes the complete canonical report excluding its own digest field. SHA-256 identifiers are integrity identifiers, not signatures.

## Architecture and state

`experiment.py` owns frozen domain records, deterministic retrieval, evidence eligibility, proposal identity, development replay, heldout evaluation, and terminal reports. `scenarios.py` owns bounded JSON decoding, schema and cross-reference checks, fixture lookup, and frozen input construction. `__main__.py` only parses arguments, invokes the experiment once, and prints JSON.

All application state lives in frozen dataclasses and tuples for one run. Config has exactly one adaptable field, `recency_topic`. Version identities bind algorithm, corpus, config, parent, and support digest. Candidate identity and support exclude all heldout values. The report is self-contained lineage, with no mutable serving pointer or persistent registry. Shell redirection is user-owned persistence, not immutable filesystem protection.

## Tools and authority

Retrieval considers only same-topic documents with positive distinct-token overlap. The baseline sorts by overlap descending, then document ID ascending. The candidate adds revision descending between those two keys only for its selected topic. It cannot outrank a larger overlap, cross a topic, edit corpus/answers, change the evaluator or labels, or search parameters.

Only separate host curator records authorize correction targets. They are synthetic fixture-author authority, not real authentication or independently verified truth. A matching feedback field has no authority on its own. Unknown targets, mismatched curator records, wrong baseline IDs, non-replayable observations, cross-topic or irrelevant targets, unchanged/older targets, conflicts, and duplicate query signatures do not count. Conflicting feedback targets exclude the entire referenced trace. Identical-target copies on one trace count once. Independent support requires distinct trace IDs, query IDs, and normalized signatures.

Exactly one topic with at least two independent eligible baseline failures is required. Zero qualifying topics returns `no_proposal_insufficient`. Multiple qualifying topics returns `no_proposal_ambiguous`. No tie is resolved arbitrarily. All eligible feedback decisions remain inspectable even when no proposal is created.

## Execution and termination

1. Read and validate three bounded fixture files. A malformed host bundle raises `ScenarioError` before any experiment report.
2. Replay and classify feedback without receiving heldout input. Require exactly one qualifying topic.
3. Construct one frozen candidate and its lineage. Check every supporting correction and every baseline-correct development control. Failure returns `rejected_development` without heldout metrics.
4. Evaluate baseline and candidate once against the identical complete heldout tuple. Exact document-ID correctness is a synthetic metric, not semantic quality or calibrated confidence.
5. Reject any baseline-correct case becoming wrong with `rejected_regression`, even when the total correct count increases. Otherwise require strict recent-group gain and strict total gain. Failure returns `rejected_no_gain`. Passing returns `review_required`.
6. Return the deterministic report and stop. The serving ID is always baseline. There is at most one proposal, one development pass, one heldout pass, no retries, and no tuning from holdout failure. Cancellation raises without a completed report or runtime writes.

CLI exit 0 means a completed experiment, including rejection or no proposal. Argument or fixture validation errors exit 2, print an error on stderr, and emit no JSON report. Broken stdout produces a nonzero I/O exit. The experiment does not perform network calls or persist application data.

## Acceptance criteria

All criteria use fixture evidence.

1. `improvement` proposes one supported topic, fixes development corrections, gains heldout recent/total correctness without a loss, returns `review_required`, and retains the immutable baseline.
2. `regression` gains aggregate correctness but loses a protected correct answer, reports its IDs, rejects, and retains baseline.
3. `insufficient` and `poisoned` create no candidate or metrics. Exclusions identify authority, replay, relevance, deduplication, and conflict failures.
4. Development regression and heldout no-gain stop at their specific gates. No-match queries can correctly abstain. Larger overlap and unrelated topics remain unaffected.
5. Distinct query IDs cannot make copied signatures independent. Conflicts and multiple qualifying topics do not select arbitrary winners.
6. Holding selection fixed while changing valid heldout labels preserves candidate ID, config, parent, and support. Repeated input produces byte-identical JSON. Hashes can be independently recomputed.
7. Malformed schemas, resource bounds, host-reference errors, invalid labels, split overlap, and CLI misuse fail without a misleading report.
8. The documented case-local suite and CLI run from a standalone copy. A built wheel installs and runs with bundled fixtures without siblings or root imports.

## Dependencies and open decisions

No runtime dependencies, provider configuration, credentials, framework APIs, or external services. Build backend is cached `hatchling==1.32.4`; Python is constrained to `>=3.14,<3.15`. The case-local lock and backend pin make local builds reproducible within the documented cache. No open material implementation choice remains. Independent review and parent qualification passed for the fixture contract; see the README verification record for exact scope and limits.
