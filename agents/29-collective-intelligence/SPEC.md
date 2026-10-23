# Collective Intelligence Agent specification

Slug: 29-collective-intelligence
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and evidence

Three deterministic role adapters independently propose an original rubric for a synthetic bounded FIFO queue assignment, then cross-review it. This is an inspectable team coordination demonstration. Agreement does not establish correctness, expert accuracy, calibration, independent errors, or human approval.

The [source brief](../../agent-library-analysis/agents/29-collective-intelligence.md) describes the book pattern and its missing convergence/synthesis helpers. This implementation is original. It deliberately replaces sequential context-reading proposals with a shared immutable snapshot and selects host-owned policy. [PLAN.md](PLAN.md) records ownership and qualification.

## Input boundary

The CLI `collective-intelligence` reads UTF-8 JSON from stdin only. No arguments are allowed except standalone `--help`. Input is at most 32,768 bytes, nesting depth 8 (root object depth 1), 512 total JSON values, object/list cardinality 32, and 1,024 characters per string, including keys. Unknown/duplicate keys, invalid UTF-8/JSON, nonfinite numbers, lone surrogates, and unsupported types are invalid. Numeric literals are at most 32 characters. Decimal exponents (including written fractional places) range from -12 through 6, bounding rational conversion work. Numeric scores are finite JSON integers or decimals, excluding booleans, in [0,10]. Rounds are integers excluding booleans. No coercion occurs.

The exact request object has three required keys:

- `problem_id`: exactly `bounded-queue-v1`.
- `max_rounds`: 1 or 2.
- `review_rounds`: null for deterministic adapters, or an array containing exactly `max_rounds` round objects.

A replay round has exactly `number` (consecutive 1-based integer) and `critiques` (0..6 entries). Each critique has exactly `id`, `reviewer_id`, `criterion_id`, `score`, and `reason`. Reason is a nonempty string up to 240 characters. Its ID must equal `r{number}-{reviewer_id}-{criterion_id}`. Reviewer IDs are `pedagogy`, `domain`, `assessment`; criterion IDs are `c-pedagogy`, `c-domain`, `c-assessment`. A reviewer cannot review their own criterion. Repeated reviewer/criterion edges, invented references, or inconsistent identities are invalid. Missing edges are permitted input and explicitly unresolved evidence. A replay supplies scores only; it cannot change roles, weights, problem, criteria, or policy.

## Domain and authority

Frozen Role, Problem, Criterion, Proposal, Critique, RoundRecord, Decision, and ConsensusResult records belong to one run. No state survives restart. Every initial adapter receives the same frozen Problem object and no prior proposals. Each proposal retains its snapshot and author. The assignment asks for a queue of capacity 3 that preserves FIFO order and rejects overflow without mutation. Criteria are original fixed host templates, one per role:

| Role | Host weight | Proposed criterion |
| --- | --- | --- |
| pedagogy | 3 | Demonstrate observable FIFO behavior with examples. |
| domain | 2 | Enforce capacity and preserve state on rejected overflow. |
| assessment | 1 | Explain representation invariants in a short rationale. |

Host weights are finite positive values checked before aggregation. They are illustrative policy, not learned or calibrated expertise. Adapters propose data only. The host validates proposals and critiques, owns scheduling, arithmetic, selection, termination, and output. Runtime has no model, network, subprocess, user-file access, persistence, credentials, external service, or human approval operation. Closed-pipe cleanup may redirect stdout to the operating system null device. The CLI's sole effect is emitting a report to stdout.

## Arithmetic, synthesis, and dissent

Each criterion expects exactly the other two reviewers. Its denominator is the sum of their host weights. A complete score is sum(weight * score) / expected denominator. Decimal input is converted to exact rational arithmetic; report scores are rounded to six decimal places only for display. Critiques and decisions also expose `score_exact` as numerator/denominator integers, or null for missing coverage, so exact judgments and convergence can be reconstructed. Missing reviews produce score null with both expected and observed weight, never a renormalized partial mean.

A complete criterion is unresolved (`defer`) if its exact mean equals 6 (`threshold_tie`), any reviewer score equals 6 (`reviewer_tie`), or at least one reviewer is above 6 and another below 6 (`contradictory_scores`). Otherwise it is `accept` when the mean is above 6 and `reject` below 6. Missing reviews also defer. Every decision links all available critique IDs and exact criterion identity. Accepted rubric entries can only be those immutable proposed criteria. Rejected and deferred criteria remain in decisions. Every critique remains in round history, including verbatim reason and reviewer identity. Final dissent contains the final-round full critiques whose scores are at or below 6, and every critique on a deferred criterion. No concern is erased by selection.

## Flow and bounded termination

Validate the request before proposals. Collect all three independent proposals before reviewing. For each of at most two rounds, obtain deterministic reviews or the corresponding validated replay round, validate the full graph, and compute decisions. Proposals remain unchanged; the optional second round reconsiders reviews, not authorship or criterion wording.

The executable convergence predicate requires two consecutive rounds with complete 6-edge review matrices, no deferred decision in either round, identical decision labels by criterion, and exact weighted score change at most 1/4 for every criterion. Only then report `converged`. This label means the synthetic policy predicate passed. No first-round convergence is possible. Otherwise report `unresolved` at `max_rounds`, including `budget_exhausted` and final unresolved criterion reasons. Selected criteria in an unresolved result are explicitly provisional. No retry, fallback, repair, or unbounded loop exists.

Output includes `status`, `mode` (`fixture`), `problem`, `roles`, `proposals`, `rounds`, `rubric`, `dissent`, `unresolved`, `provisional`, and `correctness_claim` (always false). Rounds expose critiques, expected review edges, missing edges, decisions, and convergence. The same typed records are returned by `run_session` for valid requests. Input validation is the public boundary; constructing private records directly is not an untrusted adapter API.

Malformed input/CLI arguments return a bounded constant JSON error (`status: invalid-input`) and exit 2 without echoing input. SIGINT/KeyboardInterrupt returns `cancelled` and exit 130. Unexpected internal failures return sanitized `failed` and exit 1. Valid converged or unresolved reports exit 0; callers must inspect status. Closed stdout during help, report writing, explicit flush, or interpreter shutdown returns 0 without traceback, including unbuffered Python. Input consumption is byte bounded, but waiting for a stdin producer is caller-controlled; no hard real-time deadline is claimed.

## Acceptance criteria

Checks independently calculate scores 25/3, 35/4, and 17/5, prove complete coverage/no self-review, same initial object snapshots, immutable records, two-round convergence, single-round exhaustion, missing-review denominators, tied/conflicting votes, stable-score tolerance, faithful dissent, and proposed-only synthesis. Adversarial checks cover JSON/schema/type/identity/reference/resource limits and real-process closed stdout/argument errors. Qualification must execute the CLI, a case-only copy, and an installed wheel from outside the repository. Local fixture evidence does not establish provider, deployment, or production behavior. Independent substantive review and output-error fix review passed; README records the fixture qualification evidence.
