# Ethical Reasoning specification

Slug: 22-ethical-reasoning
Status: demo-ready
Runtime: Python 3.14, standard-library runtime, strict JSON CLI

## Problem and scope

A policy owner needs to see how an ethical checkpoint constrains proposed tool effects. This demo checks synthetic aggregate reports, permits one simulated publication, repairs a restricted-field proposal once, or returns a review case. No hiring decisions, legal compliance, general ethical judgment, model calls, network effects, or persistent state exist.

## Evidence and decisions

**Source facts.** The retained [brief](../../agent-library-analysis/agents/22-ethical-reasoning.md) identifies deterministic principle validators, audit before dispatch, mitigation followed by revalidation, and human escalation. Its source is Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 12, printed pp.330-346, PDF pp.361-377. The source leaves policy thresholds, dispatch enforcement, audit storage, and mitigation details incomplete. Figure 12.1 does not depict this pattern.

**Selected decisions.** Use frozen typed records, an immutable host-owned policy registry `synthetic-v1`, exact rational disparity arithmetic, one redaction, and a dispatcher that evaluates policy itself on every attempt. Registry rules all apply. Any finding denies dispatch. A local review owner label `synthetic-policy-owner` identifies responsibility, without sending a message or obtaining approval. The input version selects no alternate rules.

**Tradeoff.** A pure evaluator plus separate permission-bearing dispatcher was considered. Rechecking inside the dispatcher avoids stale or fabricated permission objects. A general policy expression language would obscure the small authority boundary, so the registry contains ordinary host functions. Source concepts inform this independent implementation, not production qualification.

## Inputs and outputs

The CLI accepts one UTF-8 JSON file, or stdin with `-`. Maximum input size is 16,384 bytes, maximum nesting depth 12. Duplicate keys, unknown or missing fields, non-finite numbers, floats where counts are required, booleans as counts, invalid UTF-8, and unsupported versions are rejected. Invalid input has exit 2, a structured `invalid_input` output, and zero attempts or effects. Error strings never echo supplied values.

The top-level object has exactly `schema_version` (integer 1), `policy_version` (`synthetic-v1`), `synthetic` (true), `action`, and `groups`. `action` has exactly `action_id` (1-32 ASCII letters, digits, underscores, or hyphens), `kind` (`publish_summary`, `export_records`, or `rank_individuals`), `recipient` (`internal_dashboard` or `external`), and unique nonempty `fields` (1-4 values drawn from `aggregate_count`, `selection_rate`, `synthetic_name`, `synthetic_email`). Fields are symbolic names only. No personal values or free-text instructions are accepted.

`groups` contains 2-8 distinct `group_id` records with exactly `group_id`, `eligible`, and `selected`. IDs use the action ID syntax. Eligible is an integer 1-10,000, and selected is an integer 0-eligible. Counts describe unverified synthetic observations, not population completeness, authenticity, causal fairness, or protected-group membership.

Output contains schema/policy versions, terminal `status`, final symbolic action, structured `events`, simulated `effects`, `review` or null, and an error or null. Successful output exits 0. `review_required` exits 3. Controlled I/O failure exits 2, cancellation exits 130. No input values are copied into invalid-input errors.

## Architecture and state

`domain.py` owns validated immutable requests. `policy.py` owns the frozen rule registry and evidence findings. `engine.py` owns one run's dispatch attempts, events, effects, and bounded repair. `cli.py` owns bounded decoding, serialization, and exit status. State exists only in process memory for one request. Independent invocations never deduplicate each other.

An event is observable evidence of this local execution. Sequence numbers establish in-run order only. They provide no tamper resistance, cryptographic integrity, trusted evidence provenance, or durable audit guarantee. An effect is a symbolic publication receipt, never a real disclosure.

## Tools and authority

The only tool is `SimulatedDispatcher.attempt(request)`. It accepts a validated request, recomputes all host rules, appends an audit event before changing effects, and emits at most one symbolic receipt per action ID. A caller supplies no permit flag. A session is bound to its original request. The first attempt must equal that request, and the second must equal its exact restricted-field redaction. Altered kind, recipient, identifier, or group evidence causes a `HOST-SESSION-2` denial. Duplicate attempts against a completed or exhausted session add a `HOST-SESSION-1` audited denial and no effect. At most two attempts are allowed before the session closes. A failed attempt can be followed only by a policy-rechecked mitigation attempt. Python code and policy functions are trusted host code, not a sandbox against a malicious in-process caller.

The immutable registry has these versioned rules:

| Policy ID | Rule |
| --- | --- |
| SYN-ACTION-1 | Only `publish_summary` is permitted. |
| SYN-RECIPIENT-1 | Only `internal_dashboard` is permitted. |
| SYN-FIELDS-1 | Only `aggregate_count` and `selection_rate` are publishable. |
| SYN-FIELDS-2 | At least one publishable field must remain after repair. |
| SYN-SAMPLE-1 | Every group has at least 20 eligible observations. |
| SYN-DISPARITY-1 | Let each rate be selected/eligible. When the maximum rate is positive, min(rate)/max(rate) must be at least 4/5. All-zero rates require review because that ratio is undefined. |

The 4/5 ratio and minimum sample count are arbitrary teaching choices. They are not legal thresholds, a statistical significance test, an assurance of unbiased outcomes, or a domain recommendation. Both a policy failure and insufficient evidence require review and zero dispatch.

## Execution and termination

1. Decode and validate the entire bounded request before creating a dispatch session.
2. Attempt original dispatch. Every policy runs, all findings are recorded, and only an empty finding set permits an effect.
3. If permitted, return `completed`, one effect, and no review.
4. If restricted fields occur, redact those symbolic field names once. Preserve ID, kind, recipient, and counts. Record the mitigation and fully revalidate through the dispatcher, even if no fields remain. Input permits only nonempty fields; the private mitigation representation may be empty and is denied by SYN-FIELDS-2.
5. If revalidation permits, return `completed` with one effect and both attempts in the evidence trace. Otherwise return `review_required` with policy findings, owner label, and zero effects. If no restricted fields occur, return review after one attempt.
6. There is no retry, alternate policy, count manipulation, automated approval, or external review delivery. The controller performs at most two dispatch attempts and one mitigation. A valid run emits at most four events. Cancellation before a terminal output returns `cancelled`; the process never writes a durable effect.

## Acceptance criteria

All criteria require fixture evidence.

1. An allowed action executes exactly once and records the original attempt before its terminal event.
2. Restricted fields can be removed once. The repaired action is fully rechecked, and a permitted repair produces exactly one effect with no restricted fields.
3. Export, individual ranking, external recipients, unresolved disparity, small groups, and all-zero evidence return review with policy IDs and no effects. Redaction must not erase an independent violation.
4. The dispatcher itself blocks a forbidden action when invoked directly. It blocks replay and excess attempts without a second effect. The registry cannot be changed by input JSON or mutated through its exported mapping.
5. Exact 4/5 disparity passes; a value below it fails. Zero numerators and invalid count denominators are handled explicitly.
6. Malformed, duplicate-key, deeply nested, oversized, non-finite, unknown-field, unsupported-version, and non-synthetic input produce structured failure with no effect.
7. The documented CLI works from an isolated case copy and from a locally installed wheel outside the repository. Tests do not import sibling paths or depend on provider configuration.

## Dependencies and open decisions

Runtime requires only Python 3.14. Hatchling 1.32.4 is the pinned build dependency. No credentials or `.env` file are needed. The [Python JSON](https://docs.python.org/3.14/library/json.html), [Fraction](https://docs.python.org/3.14/library/fractions.html), and [Hatch package configuration](https://hatch.pypa.io/latest/config/build/#packages) documentation informed the boundary implementation. Source and dependency checks do not demonstrate deployment.

Implementation decisions are selected. Independent review and fix verification passed. The parent owns catalogue integration. Live-model and deployment validation are inapplicable and unrun.
