# Explainable agent specification

Slug: 23-explainable
Status: demo-ready
Runtime: Python 3.14, standard-library runtime

## Problem and scope

A reviewer needs to inspect why a synthetic task received a priority and check that user, engineer, and auditor explanations describe the same execution. This case applies a small deterministic policy and captures actual evidence, rule evaluations, and the final selection in one immutable, run-scoped trace. It releases a priority only with complete, validated explanations for all three audiences.

The task is a learning example. It does not triage real incidents or people. It has no model, training, calibrated confidence, SHAP, LIME, counterfactual search, hidden reasoning capture, or autonomous external action.

## Evidence and decisions

Source facts come from Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 12, printed pp. 346-358, physical PDF pp. 377-389. The [source brief](../../agent-library-analysis/agents/23-explainable.md) separates recorded decision stages, audience explanations, attribution, and calibration. Its demonstrated code has material gaps. Trace recording does not establish access to a model's internal reasoning. The [inventory](../../agent-library-analysis/agent-inventory.md) and [foundations](../../agent-library-analysis/foundations.md) informed the scope.

Selected decisions are a pure rule core, frozen event types, one canonical trace, fixed rendering templates, a synchronous all-audience release gate, and a read-only JSON CLI. A table of rule evaluations was selected over free text explanation generation because its claims can be checked exactly. A mutable append-only journal was considered, but frozen per-run values make this example smaller and avoid partial persistence. No material contract decision remains open. Independent review and fix verification passed.

## Inputs and outputs

The `classify` command accepts one UTF-8 JSON object with exact keys `task_id` and `evidence`. `task_id` matches `[A-Za-z0-9][A-Za-z0-9_-]{0,31}`. `evidence` accepts only `outage`, `blocked_users`, and `due_hours`. Missing keys and JSON `null` mean unavailable evidence. Present values are exact JSON booleans for `outage`, integers from 0 to 10000 for `blocked_users`, and integers from 0 to 720 for `due_hours`. Booleans are not integers. Unknown fields, duplicate keys, nonfinite numbers, unsupported values, invalid UTF-8, input over 32768 bytes, and JSON values deeper than 16 levels are rejected. The root value has depth 0. Free text instructions have no place in this schema.

The policy `task-priority-v1` evaluates these rules in order, recording all three results. The first matching rule owns the selection.

| Rule | Predicate | Priority |
| --- | --- | --- |
| `urgent-outage` | `outage` is true and `blocked_users` is at least 5 | `urgent` |
| `high-impact-or-due` | `blocked_users` is at least 1 or `due_hours` is at most 24 | `high` |
| `routine-default` | Always true | `routine` |

All three evidence values are required before any rules run. Missing evidence produces three evidence events and a final event with no priority and status `needs_review`. It produces incomplete explanations that cite the missing evidence and final event. No default value fills a gap.

A complete trace has exactly seven events. IDs `E1` through `E3` record evidence, `E4` through `E6` record rules, and `E7` records the final selection. A missing-evidence trace has exactly four events, with `E4` as its final event. Each rule records its evidence event references. The final event references the chosen rule or the missing evidence. The envelope records schema version, policy version, task ID, and a SHA-256 digest of canonical event data. The digest detects corruption. It is not a signature or proof of source authenticity.

Output is one JSON object with `status`, `decision`, `explanation_status`, `explanations`, `trace`, and `issues`. A `completed` result has a priority, all three audience views, and no issues. Every explanatory claim contains text and nonempty real event IDs. Missing evidence yields `needs_review`, a null released decision, `incomplete` explanations, and an issue code. A malformed or inconsistent trace or any renderer failure yields `needs_review`, a null released decision, `unavailable` explanations, and a stable issue code. No partial audience set is released. A trusted trace can still contain its historical final event when rendering fails, but the top-level decision remains withheld.

The `explain` command accepts exactly a serialized trace object. It validates fields, event shapes, versions, digest, and exact policy replay from recorded evidence before rendering. Removing, duplicating, reordering, changing, or inventing events fails validation, including when an attacker recomputes the digest for an inconsistent trace. A coherent rewrite of all evidence, dependent events, and digest cannot be detected without a trusted external source. This case makes no authenticity guarantee.

## Architecture and state

`contracts.py` owns frozen evidence, event, trace, claim, explanation, and outcome types. `decision.py` owns validation, the policy table, trace construction, canonical serialization, and replay validation. `explanation.py` owns templates and the release gate. `cli.py` owns strict bounded JSON and explicit file reads. The core has no file or network effects.

A trace is the immutable tuple of events for one invocation. An evidence event is the recorded input observation, not proof of real-world truth. A rule event records an actual predicate result, not a causal attribution estimate. A claim is a fixed human-readable statement plus its trace references. Frozen values and tuples prevent application code from silently editing a trace during rendering. Replay compares against the same executable policy but does not independently establish policy correctness.

There is no persistent state. The CLI returns the trace on stdout. The operator decides whether to retain that synthetic data. No trace store, user authentication, audience access control, or retention service exists.

## Tools and authority

The CLI may read the explicitly named regular file or stdin and write one result to stdout. It does not open a browser, call a provider, execute shell commands, write files, or act on the priority. The host policy determines the priority. Renderers only propose a view. The release gate validates each complete view against the canonical rendering for the same trace and rejects modified or unsupported claims.

The file reader rejects final-component symlinks and non-regular files without waiting on a FIFO. Parent path components are not a filesystem sandbox. The named path is an explicit read capability supplied by the operator. Input and trace strings do not grant additional capabilities.

## Execution and termination

1. Read at most 32769 bytes, parse strict JSON, and validate the selected command's input.
2. For classification, capture all three evidence events. Stop at `needs_review` if any evidence is missing.
3. Otherwise evaluate exactly three rules and record their results, then record the first matching priority.
4. For explanation replay, validate and reconstruct the trace before any rendering.
5. Render exactly once for each of three audiences. Validate the entire immutable view, including references and decision.
6. Release the result only after every audience succeeds. A failure suppresses all views and the released priority. There are no retries, unbounded searches, model calls, or background tasks.

Expected boundary failures return safe stable issue codes without echoing raw input or exception messages. The CLI exits 0 on `completed`, 2 on review or invalid input, and 130 on `KeyboardInterrupt`. Cancellation emits a review result with unavailable explanations. Broken stdout closes the process without a traceback.

## Acceptance criteria

All criteria require fixture evidence. No provider or deployment evidence is needed for this selected scope.

- A valid urgent, high, or routine input follows the documented rule precedence, including inclusive threshold values.
- Each audience reports the identical priority and cites actual events from the same immutable trace. Serialization and replay preserve the trace and result.
- Missing evidence stops before rule evaluation, produces incomplete explanations, and withholds the priority.
- Invalid input, removed or reordered events, invented rules, changed decisions, unknown policies, and mismatched digests cannot release a priority.
- Recomputed digests do not hide semantically inconsistent rule or final events. Renderer exceptions, invented prose, broken references, and decision changes withhold every audience view.
- The strict CLI rejects duplicate keys, nonfinite values, oversized input, invalid UTF-8, symlinks, and non-regular files. It reports safe JSON and meaningful exit codes.
- Tests and documented CLI commands run from this case, from a copy containing only this case, and through an installed wheel without sibling paths or checkout imports.

## Dependencies and open decisions

Python 3.14 is the selected interpreter. Runtime dependencies are empty. Hatchling 1.32.4 is a build-only dependency already used in this checkout. The local lock contains no runtime third-party packages. Independent review and fix verification passed; the parent owns the final readiness assessment. Live model, provider, hosted CI, deployment, production audit reliability, and real-world policy utility remain unverified and outside this case.
