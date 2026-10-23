# Education Intelligence Agent specification

Slug: 28-education-intelligence
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Problem and evidence boundary

An original three-objective arithmetic curriculum demonstrates Bayesian Knowledge Tracing, prerequisite planning, progressive hints, and due reviews. The host compares synthetic answer strings with fixed keys. It never evaluates learner code. One correct answer is an observation, not proof of mastery or educational efficacy.

The [source brief](../../agent-library-analysis/agents/28-education-intelligence.md), [inventory](../../agent-library-analysis/agent-inventory.md), and [foundations](../../agent-library-analysis/foundations.md) inform the pattern. This implementation selects original formulas, policy, data, and limits. Book efficacy, deployment, and calibration claims remain unverified. The parent owns independent review and catalogue integration.

## Strict input schema

`education-demo` with no arguments reads its packaged `session.json`. `education-demo --input PATH` reads one UTF-8 regular file. `--help` prints fixed help. All other argument combinations fail without echoing caller data. No stdin, directory, device, FIFO, or final-component symlink is accepted. Parent directory symlinks are outside the no-follow guarantee. Only stdout is written.

JSON has at most 32768 bytes and nesting depth 12. Duplicate keys, unknown or missing fields, booleans used as numbers, nonfinite numbers, unsupported types, and exceeded bounds fail before a result is committed. Every field below is required. Objects have exactly the listed fields.

- Request has `now`, `parameters`, `graph`, `state`, and `answers`.
- `now` is a canonical UTC second timestamp `YYYY-MM-DDTHH:MM:SSZ` between 2000-01-01 and 2099-12-24 inclusive. All other timestamps use that format and years 2000 through 2099. Leap seconds and fractional seconds are rejected.
- `parameters` has `guess`, `slip`, and `learn`, each a finite probability in [0,1]. These are illustrative BKT parameters, not calibrated estimates.
- `graph` has 1 through 3 nodes. A node has `objective` and `prerequisites`. Objective IDs come from the fixed host catalog `count`, `add`, and `multiply`. IDs are unique. Prerequisites contain at most 2 unique IDs from this graph. Self edges and cycles fail. The packaged graph is count -> add -> multiply. Caller graphs are explicit synthetic curriculum variants, not authority to add answer keys or executable content.
- `state` has exactly one record per graph objective. A record has `objective`, `mastery`, `attempts`, `failures`, `last_evidence`, and `due_at`. Mastery is a finite probability in [0,1]. Attempts are integers in [0,10000]. Failures are consecutive incorrect assessed answers, integers in [0,3], no greater than attempts. `last_evidence` and `due_at` are timestamps or null. Zero attempts require both timestamps null and zero failures. Nonzero attempts require both timestamps, `last_evidence <= now`, and `due_at > last_evidence`. Due times may be in the future. Supplied state is caller data with no authenticated historical guarantee.
- `answers` contains at most 12 records, each with `objective`, `answer`, and `observed_at`. Objective must belong to this graph. Answer is null or a string of at most 128 Unicode code points. Comparison uses surrounding-whitespace stripping and exact string equality. `count` asks how many stones are in [stone, stone, stone], key `3`. `add` asks `2 + 3`, key `5`. `multiply` asks `2 * 3`, key `6`.
- Evidence times must be <= now and nondecreasing across the request. Every assessed answer must be strictly newer than that objective's last assessed evidence. Missing evidence is represented by null. It changes no mastery, attempt, failure, evidence time, or review schedule. It must still reference a prerequisite-eligible objective and have a valid nonfuture timestamp.

## Domain model and arithmetic

Frozen `ObjectiveGraph`, `LearnerState`, `AnswerEvidence`, `BKTParameters`, `ReviewSchedule`, and `LearningResult` values define run-scoped state. Parsing owns boundary validation. The host owns answer keys, arithmetic, gates, hint levels, and terminal labels. There is no model, network, database, persistent learning, arbitrary code execution, or external dispatch.

For prior mastery p, guess g, slip s, learning probability t, first calculate the observation posterior q. For correct evidence, `q = p*(1-s) / (p*(1-s)+(1-p)*g)`. For incorrect evidence, `q = p*s / (p*s+(1-p)*(1-g))`. A zero denominator rejects the whole request. Then apply the learning transition `p_next = q + (1-q)*t`. The trace reports p, q, and p_next. No learning transition occurs without assessment evidence. Floating point arithmetic is exposed without rounding; a result must stay finite in [0,1].

The sole mastery threshold is **0.8**, used inclusively for mastered labels and every prerequisite gate. An objective is eligible only when all its direct prerequisites meet that threshold. Since the graph is acyclic, no activity bypasses an unmet direct prerequisite. Returned eligibility includes mastered objectives for review. Practice includes only eligible objectives below threshold. Supplied mastery can be high without evidence; it is explicitly caller-supplied, not a host certification.

## Session flow, review, and stops

1. Parse all records and validate the complete graph and state before processing evidence.
2. If any supplied failure count is already 3, return `teacher_review` without processing answers.
3. Process evidence in input order on a private state copy. Reject an ineligible answer, replayed assessed timestamp, impossible denominator, or attempted increment beyond 10000. Such an error returns no state or partial trace.
4. Correct evidence resets failures to zero. Incorrect evidence increments failures. Hint level equals failures. Levels 1 and 2 return fixed guiding hints. Level 3 returns the final guiding hint and stops as `teacher_review`; remaining answers are counted as unprocessed. No automatic teacher override exists.
5. After assessed evidence, set `last_evidence = observed_at`. Set review due from the evidence time, after 7 days for a correct answer whose updated mastery meets 0.8, otherwise after 1 day. Review intervals are an illustrative fixed policy, not SM-2 or a retention guarantee. Null evidence changes no schedule.
6. Compute due reviews using injected `now`, with `due_at <= now` and current prerequisite eligibility. Sort by due timestamp then ID. Sort practice by objective ID. Select the earliest due review first, otherwise the first practice objective. Return at most one `next_activity`, containing kind, objective, and the fixed prompt.
7. Terminal priority is `teacher_review`, then `evidence_required` if any processed evidence was null, then `completed` if all objective mastery values meet 0.8, otherwise `practice_required`. `completed` describes the synthetic threshold check only. Due reviews may still exist. All outcomes stop after the bounded request. No retry or background task exists.

The response has `status`, `threshold`, `state`, `trace`, `eligible`, `practice`, `due_reviews`, `next_activity`, `unprocessed_answers`, and `limits`. State records have the input state schema and can be explicitly supplied on another invocation. Trace records have objective, assessment (`correct`, `incorrect`, or `missing`), prior, posterior, mastery, hint_level, and hint. Missing evidence has a null posterior and hint. Due review records have objective and due_at. Limits reports answers=12, objectives=3, hints=3, attempts=10000. No caller answer text is returned. Teacher-review results suppress next_activity.

Invalid input returns only `status=invalid_input` and a fixed `error` code, exits 2, and returns no learner state. Codes are `invalid_arguments`, `invalid_json`, `invalid_schema`, `bound_exceeded`, `invalid_graph`, `invalid_time`, `invalid_probability`, `invalid_state`, `ineligible_objective`, `replayed_evidence`, `impossible_observation`, and `input_unavailable`. No exceptions, file paths, or supplied text appear in errors. SIGINT returns `status=cancelled`, exits 130, and returns no learner state. A closed stdout is quiet and exits 0, including during help and interpreter flushing. Other output I/O failure exits 2 without a traceback. Normal domain outcomes exit 0.

## Acceptance criteria

Independent rational arithmetic checks both observations and transition order. Tests prove missing evidence preserves the entire record, threshold equality unlocks only valid activities, review ordering uses injected time, hints escalate and teacher review stops remaining evidence, and invalid graph/parameters/state/times/denominators cannot advance the learner. Real subprocess checks cover malformed arguments, excessive/deep JSON, special files, and closed stdout in buffered and unbuffered modes. Qualification runs the actual CLI, a case-only temporary copy, and an installed wheel from outside the repository. Fixture evidence does not establish live-model, real-course, deployment, production, or authenticated learner-history qualification. Independent substantive review and output-error fix review passed; README records the fixture qualification evidence.
