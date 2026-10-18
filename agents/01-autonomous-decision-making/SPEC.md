# Autonomous Decision-Making Agent specification

Slug: 01-autonomous-decision-making
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Problem and scope

Teach a support engineer how an agent chooses an immediate level of autonomy from a ticket, operational evidence, and explicit policy. The smallest coherent scenario uses bundled synthetic tickets and one read-only synthetic service-status tool. It emits an autonomous status reply, guided clarification, or a human-handoff record, with an observable execution trace.

This is a one-decision cognitive loop. No CRM, refunds, account changes, message delivery, human notification, persistent memory, adaptive thresholds, or multi-step planning is implemented. A handoff means a local record, never proof that a human received it. All timestamps describe a synthetic scenario snapshot; even live-model mode uses synthetic operational data.

## Evidence and decisions

Source facts (from the retained [brief](../../agent-library-analysis/agents/01-autonomous-decision-making.md), not a fresh inspection of the purchased book): Chapter 5 describes perception, cognition, and action; autonomous, guided, and human routes; contextual support decisions; and permission/impact guardrails (printed pp.118–131, physical PDF pp.149–162). Longer-term planning is a separate pattern (printed pp.141–144, PDF pp.172–175). The brief identifies inconsistent scoring fields and unspecified tie handling, scheduler, adapters, learning implementation, and global stop conditions. Its reported autonomy rate is unverified.

Selected decisions: plain Python with validated contracts, deterministic host policy, a deterministic offline cognition backend, and optional OpenAI Responses structured output. Use one status observation and at most one model proposal; no framework or persistence. Thresholds and rules below are original demo choices, not book requirements. The offline backend is a rule-based baseline, not an LLM-quality evaluation. Host-authored replies eliminate unvalidated model prose from output.

The trusted fixture supplies request kind, impact, human preference, and operational context. These fields stand in for an upstream authenticated intake system. The natural-language message is untrusted data and cannot override them. This demo does not independently prove that upstream labels match arbitrary natural language.

## Inputs and outputs

CLI selects a named bundled synthetic example; default `routine-outage`. No arbitrary file, URL, shell, or tool arguments are accepted from a model. The library validates all ticket, status-result, and proposal boundaries strictly (unknown fields rejected; no bool-as-number coercion; finite numeric confidence).

Ticket fields: `ticket_id` matching `TKT-` plus 1–32 uppercase alphanumeric/hyphen characters; a nonblank `message` of at most 2000 characters; `service` from the bundled allowlist; `request_kind` in `status`, `troubleshooting`, `refund`, `account_change`, `security`, `unknown`; `impact` in `low`, `high`; `customer_tier` in `standard`, `premium`; `urgency` in `normal`, `urgent`; booleans `human_requested` and `human_available`; timezone-aware `scenario_time`.

Status evidence: matching service, `status` in `operational`, `degraded`, `outage`, `unknown`, timezone-aware `observed_at`, and an evidence ID matching `SYN-` plus 1–40 uppercase alphanumeric/hyphen characters. It must be no more than 300 seconds old relative to scenario time and not from the future. Unknown, stale, mismatched, malformed, or failing status evidence cannot authorize a reply.

Proposal: `route` in `autonomous`, `guided`, `handoff`; numeric `confidence` in [0,1]; `action` in `status_reply`, `ask_clarification`, `handoff`, `refund`, `account_change`; and `reason_code` in `incident_detected`, `context_missing`, `uncertain`, `human_preferred`, `restricted_effect`. Allowed ordinary route/action pairs are autonomous/status_reply, guided/ask_clarification, handoff/handoff. Restricted actions are retained in the schema only to demonstrate denial. Missing confidence and malformed proposals fail closed. Confidence accepts integer/float JSON numbers, rejects booleans and nonfinite/out-of-range values. Provider JSON payloads are bounded to 10000 characters.

Output: JSON report with ticket ID, mode, terminal route/status, priority, policy reason, validated proposal when present, validated evidence when available, host-rendered response or handoff, and sanitized trace. Do not retain raw ticket messages, provider prose, raw exceptions, or secrets in the report. Handoff contains ticket ID, reason, evidence reference where available, and `ready` or `queued` based on human availability. No content may imply an actual refund, account change, or delivered notification. Run state is new for each invocation and discarded on exit; stdout is the only application output, with no artifact writes.

Exit 0: a valid autonomous, guided, or intentional policy handoff. Exit 2: invalid input/configuration or a dependency/proposal/tool failure, even when a safe handoff report is prepared. Exit 130: cancellation. JSON errors use stable codes without raw diagnostic payloads.

## Architecture and state

CLI → fixture validation → hard policy gate → status lookup and result validation → cognition proposal → strict validation and policy arbitration → host action renderer → terminal report.

Contracts define inputs/results. The service tool owns only a bundled snapshot. Replay and live cognition share the same policy and renderer. Policy is independent from the provider and is the only authority for the chosen route. Trace entries use fixed stage/event/reason labels and bounded identifiers. All state, counters, and evidence are run-scoped; no cross-run history or feedback learning exists.

## Tools and authority

`get_service_status(service)` reads the allowlisted bundled service snapshot, with no network or writes. The controller invokes it at most once; the model cannot choose another tool or expand its input scope. Observation must precede any autonomous reply.

`status_reply` prepares a host template containing the validated synthetic service status and evidence ID. `ask_clarification` prepares a host template asking for details. `handoff` prepares a local handoff record. These actions send nothing. Monetary/account/security effects are never implemented. Human unavailability never increases autonomy.

The sole optional network capability is one OpenAI request with synthetic ticket/status context. It requires explicit `--mode live` and case-local environment credentials; never discover credentials in other cases. Use `store=false`, SDK retries disabled, a bounded output budget, and a request timeout. Treat model refusal, incomplete output, invalid response, timeout, or transport failure as dependency failures with a safe handoff. Do not fall back silently or issue a second request.

## Execution and termination

1. Validate CLI, ticket, and configuration. Invalid input stops before tools/provider. Live mode without credentials fails before execution.
2. Apply hard policy gates before any tool/provider: human request, high impact, refund, account change, security, or unknown request → human handoff. Premium tier cannot override a gate.
3. Read at most one service observation. Any failed or invalid/unknown/stale observation → handoff with failure exit. Never claim the issue is resolved.
4. Obtain at most one proposal (offline rules or live structured output). Provider/model failure or malformed proposal → handoff with failure exit. A restricted action → policy handoff. Inconsistent ordinary route/action pairs → invalid-proposal handoff.
5. Apply deterministic precedence: explicit candidate handoff or confidence <0.50 → handoff; candidate guided, 0.50 ≤ confidence <0.80, or an operational service without a diagnosed incident → guided clarification; only an autonomous/status_reply proposal with confidence ≥0.80 and degraded/outage evidence → autonomous status reply. Confidence is a routing input, not a calibrated probability. No score maximization or implicit tie-breaking is used.
6. Priority is host derived: high for urgent/high-impact/security tickets, otherwise elevated for premium tier, otherwise normal. Priority never grants additional authority. Render the selected response/handoff and stop. No retries, follow-up turns, or threshold updates. One proposal timeout is 20 seconds; cancellation stops the run without an action. Implement the async timeout at the controller boundary as well as the SDK request timeout.

## Acceptance criteria

All required readiness criteria use fixture or mocked-provider evidence; live compatibility is additional, separately reported evidence.

- A routine outage produces an autonomous host-rendered reply referencing a matching fresh status result, with exactly one lookup and one cognition attempt.
- Healthy service/troubleshooting and medium confidence produce a guided clarification, never an invented resolution.
- Human request, high impact, and restricted request types produce handoff before any lookup or cognition; unavailable humans produce a queued record, never expanded autonomy.
- Confidence boundaries (0.50/0.80), missing/NaN/bool/out-of-range confidence, malformed proposal, contradictory route/action, and proposed restricted effects follow the stated rules without mutations.
- Invalid/stale/future/mismatched/unknown status results and tool exceptions cannot authorize autonomous output. Tool failures stay distinguishable from successful policy handoffs.
- Model refusal, incomplete/invalid output, request failure, timeout, missing credentials, and cancellation stop within the documented bounds without retries, misleading success, or sensitive output. Mocked checks assert transport options and request shape.
- Trace and host text are grounded in validated context, omit raw message/provider text/errors/secrets, and do not claim delivered handoffs or business effects. Untrusted message instructions cannot change host gates.
- Independent invocations do not share state. Offline replay works without credentials, provider SDK import, network, or sibling resources. Case-only installation and the documented CLI run path have evidence.

## Dependencies and open decisions

Use case-local uv manifests/lock and Python 3.14.8. Locally available versions checked on 2026-10-18: OpenAI Python SDK 3.31.0 and Pydantic 2.14.1. Exact package versions belong in pyproject/lock.

Current primary references checked on 2026-10-18: [Responses structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) specifies `text.format` with a named strict JSON schema, all object keys required, and `additionalProperties: false`; refusal/incomplete output needs separate handling. The [official Python API reference](https://developers.openai.com/api/reference/python) documents configurable request timeouts and `max_retries=0`. The [Responses migration guide](https://developers.openai.com/api/docs/guides/migrate-to-responses) documents `store=false`. Request no tools. Ignore known top-level `reasoning` items without retaining their content; require exactly one completed assistant message with one JSON `output_text`. Reject every non-completed response, refusal, unexpected output item, or malformed structured output before policy execution. Installed SDK response types confirm reasoning and message items can coexist. Local mocked evidence does not establish live compatibility. `store=false` does not guarantee zero provider retention.

The smallest alternative is the offline deterministic baseline; a self-hosted model adapter is deferred until a learning need justifies its maintenance and model qualification. No material behavior decision remains open for this scope. Live API access, real-ticket intent accuracy, actual human delivery, production operation, and deployment are outside selected readiness evidence.
