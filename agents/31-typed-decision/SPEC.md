# Typed Decision Agent specification

Slug: 31-typed-decision
Status: planned
Runtime: undecided
Library ID: 31 (project extension; not a book reference ID)

## Problem and scope

Teach developers how to turn unstructured context into a strictly typed decision that software can validate and handle according to explicit uncertainty rules. The intended consumer is an application developer composing business workflows, rather than an end user chatting with an assistant.

The first implementation will classify a synthetic business message into one of a caller-supplied set of labels. It will expose a case-local library interface and a reproducible demo. Its learning objective is the prediction contract, probability provenance, validation, and abstention. Domain-specific support routing, as demonstrated separately by case #01, is not this case's objective.

"Jev clone" is the informal inspiration. This case targets an independently designed application interface, not reproduction of Jev's weights, architecture, sampler, or Reinforcement Learning for Calibrated Decisions (RLCD). It does not promise drop-in API compatibility, equivalent calibration, speed, cost, or freedom from semantic errors.

## Evidence and decisions

Primary sources inspected on 2026-10-18:

- **Source facts:** TypeSafe AI styles its model **Jev** and describes it as a System One model for software decisions. Jev is named after William Stanley Jevons, not presented as an acronym. See the [introduction](https://docs.typesafe.ai/introduction) and [launch article](https://typesafe.ai/blog/introducing-system-one-models-and-jev).
- **Source facts:** The [primitives reference](https://docs.typesafe.ai/primitives) defines `Choice` (label selection with probabilities and confidence), `Score` (rubric-based numerical output with probabilities and confidence), and `Noul` (yes-probability, without a separate confidence field). Multiple named questions can share one state; they are evaluated independently.
- **Source facts:** [Choice confidence](https://docs.typesafe.ai/confidence) rescales the largest class probability relative to uniform uncertainty: `(p_max - 1/n) / (1 - 1/n)`. It is not itself a probability that the selected answer is correct. TypeSafe's [primer](https://docs.typesafe.ai/introduction/machine-learning-primer) explains calibration across groups of predictions, rather than as a guarantee for one answer.
- **Source facts:** TypeSafe's [documented model limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13) include arithmetic, date comparison, adversarial inputs, and option-order sensitivity. Its MIT-licensed [System One Adapter](https://github.com/typesafe-ai/system-one-adapter-python) provides an LLM-backed comparison interface. Neither the adapter nor constrained output establishes Jev-equivalent model behavior.

**Selected decisions:** name this case **Typed Decision Agent**, with slug `31-typed-decision`; begin with single-question categorical prediction and synthetic data; keep all results local with no business effects. Use original code unless a later implementation deliberately selects and attributes licensed reuse. Preserve the retained analysis/bootstrap snapshots.

**Proposed choices:** use a small library plus CLI, a deterministic fixture backend for contract checks, and one separately selected model backend for actual predictions. `Score`, `Noul`, shared-state question batches, images, persistent serving, and workflow integrations are deferred. These are possible extensions, not implemented features.

**Unresolved:** runtime/backend, exact public schema, probability extraction method, numerical tolerance, thresholds, request-size limits, timeout, and labeled evaluation set. Resolve these before implementing dependent behavior. No API/library version or model alias is selected.

## Inputs and outputs

Planned input: request identifier, untrusted text state, a question, and at least two distinct caller-defined labels. Host configuration supplies the permitted schema, limits, and any abstention threshold; text state cannot modify them. Reject empty/duplicate labels, unsupported types, unknown fields, and oversized input before inference. Concrete field names and size limits remain open.

Planned output: request identifier, terminal status, selected label when available, label-keyed probabilities when valid, backend/mode identification, and explicit probability provenance. A distribution must contain exactly the allowed labels, finite numeric values in [0,1], and total mass of 1 within a selected tolerance. Reject booleans as probabilities. Do not silently repair malformed distributions, coerce arbitrary prose, or synthesize missing scores.

For a valid distribution, select the highest-probability label and derive confidence with the formula above. Ties and confidence strictly below the selected threshold abstain; equality remains eligible for a decision. Do not resolve ties by label order. Confidence is a concentration measure, not an accuracy or calibration guarantee. A model label inconsistent with its distribution fails validation.

Terminal outcomes distinguish a valid decision, abstention, invalid input/output, backend failure, timeout, and cancellation. Failed or abstained results must not appear as accepted decisions. A fixture distribution is explicitly synthetic. A model's verbal confidence alone does not satisfy the probability contract.

## Architecture and state

Planned flow: library/CLI input → strict request validation → one prediction adapter → response/distribution validation → deterministic label/confidence/abstention logic → typed result.

Contracts, adapter, validation, and decision policy remain case-local. State lasts for one request; no persistent memory, training, adaptive thresholds, background work, or cross-request context. The fixture backend verifies mechanics only. A model backend requires its own source-checked implementation and evaluation evidence.

## Tools and authority

The proposed adapter may classify only the supplied state against the supplied labels. It has no shell, arbitrary file/URL access, tool discovery, message delivery, payments, account changes, or business-system writes. Local result output does not authorize downstream execution.

No provider is configured by this registration. Any later live adapter must define its endpoint, permitted data, case-local configuration, time/cost bounds, and error handling in this specification. Keep credentials and private inputs out of tracked files and result logs.

## Execution and termination

1. Validate the request and host configuration before invoking the adapter.
2. Make at most one prediction attempt. No automatic retries, fallback backend, repair loop, or recursive question generation in the first implementation.
3. Validate the response and probability provenance. Invalid or unavailable probabilities end with an explicit failure, never a fabricated accepted result.
4. Compute the selected label and derived confidence. Return a decision or abstention under host policy, then stop.
5. Backend failure, timeout, or cancellation terminates without a decision or external effect. A finite request timeout must be selected and enforced before implementation can qualify as runnable.

## Acceptance criteria

These are future checks, not executed results. All are unverified.

| Criterion | Required evidence |
| --- | --- |
| A valid synthetic distribution returns the expected typed label, derived confidence, and synthetic provenance through the documented library and demo paths. | Fixture |
| Duplicate labels, extra/missing labels, bool/NaN/out-of-range probabilities, invalid totals, malformed responses, and inconsistent selections cannot produce an accepted decision. | Fixture |
| Ties and below-threshold confidence abstain; a non-tied result exactly at the threshold remains eligible. State text cannot override schema, policy, or authority. | Fixture |
| Backend exception, timeout, and cancellation terminate within selected bounds with at most one attempt and no hidden repair/fallback. | Fixture or mocked-provider |
| Case-only installation and execution require no sibling installation, files, credentials, or runtime; independent invocations share no state. | Isolated fixture run |
| A selected live backend returns the documented contract and probability provenance on labeled examples. Provider connectivity and predictive quality are reported separately. | Live-model |
| Any calibration claim has a held-out labeled dataset, stated metric/method and sample count, and observed results. Schema/fixture success alone never qualifies. | Model evaluation; required only if claiming calibration |

A fixture implementation may establish contract behavior without qualifying a model's predictions. Any future `demo-ready` scope must explicitly state which acceptance criteria it satisfies and retain unverified evidence modes.

## Dependencies and open decisions

No dependencies, package manifests, provider configuration, or executable code are added at registration. Runtime and backend remain undecided. First select how probabilities will be obtained and evaluated, then fix the numerical/operational limits and exact schema before implementation. Recheck current primary documentation at that point; rolling model aliases are not stable version pins.

A conventional structured-output LLM adapter is an implementation alternative, not a substitute for validated probability semantics. Jev integration would remain dependent on TypeSafe's hosted API; a self-hosted model would require separate probability and quality evaluation. No training or model-equivalence claim is in scope.
