# Typed Decision Agent specification

Slug: 31-typed-decision
Status: demo-ready
Runtime: Python 3.14, standard library, deterministic fixture backend
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

**Implementation decisions selected before coding on 2026-10-23:** Python 3.14,
standard library, a public case-local library and CLI, and one fixed child-process
fixture adapter. Original hand-authored distributions qualify mechanics only.
No model backend, probability extraction from a model, training, calibration,
or labeled predictive evaluation is selected. The official confidence and
primitives references were rechecked on this date; no vendor code is reused.

`Score`, `Noul`, shared-state question batches, images, persistent serving,
workflow integrations and a live model adapter remain deferred. See [PLAN.md](PLAN.md)
for the implementation sequence and remaining parent review gate.

## Inputs and outputs

The exact request object has four required keys. `request_id` is nonblank text
of at most 128 UTF-8 bytes, `state` is nonblank untrusted text of at most 32,768
UTF-8 bytes, `question` is nonblank text of at most 4,096 UTF-8 bytes, and `labels`
is a JSON array of 2–16 distinct nonblank strings of at most 64 UTF-8 bytes each.
Label identity is exact, case-sensitive and untrimmed. Reject NUL and surrogate
characters in these text fields. Reject unknown fields and unsupported types.
Host `Policy` supplies threshold and timeout; request text cannot modify them.

UTF-8 JSON is limited to 65,536 bytes and nesting depth 8. Duplicate object keys,
NaN/Infinity, malformed JSON and nonstandard numbers are rejected. Numeric tokens
are at most 64 characters with adjusted exponent within [-1000,1000]. Library
fixtures pass the same bounds as CLI JSON. Explicit CLI input paths are read-only
regular files. Every path component is opened with no symlink following. Reject
`..` path components before normalization. Bundled CLI resources use the same
safe reader. FIFOs, directories, missing files and oversized files fail without
an adapter attempt. macOS and Linux with POSIX dir_fd/O_NOFOLLOW support are the
selected platforms; Windows and zipped in-place imports are not supported.

The exact terminal output has `request_id`, `status`, `reason`, `attempts`,
`selected_label`, `probabilities`, `confidence`, `threshold`, `backend`, `mode`,
and `probability_provenance`. `request_id` is null when input cannot be validated.
Only `decision` carries a selected label. A valid abstention retains the validated
probabilities and confidence. All failures carry null label, probabilities and
confidence. `attempts` is 0 or 1 and counts successful child launches. Threshold
is null for invalid request/policy or CLI argument/file failures before policy
application. Reasons are bounded host-owned codes; raw input, exceptions and
paths are never reflected in error messages.

The fixed adapter response is exactly `{backend, mode, provenance, selection,
probabilities}`. Identity values must be `fixed-fixture-v1`, `fixture`, and
`synthetic-hand-authored;not-model-probabilities` respectively. The host checks
them and sets output identity itself, even on failure. This identifies the
selected fixture mode, not validation of any failed distribution. The fixture
container is exactly `{request, behavior, response}` and its request must match
the caller request exactly, including state, question, labels and request ID.
`behavior` is `return`, `fail` or `hang`; the latter two are synthetic fault
injections. State cannot select them. Fixtures do not classify new text.

A distribution must contain exactly the caller labels, finite numeric values in
[0,1], and total mass within absolute tolerance 1e-9 of 1, inclusive. Reject
booleans, strings and malformed numbers. JSON numbers stay Decimal. The library
accepts int, float and Decimal probabilities, converting floats through their
shortest decimal spelling. Exact rational arithmetic then checks mass,
confidence and threshold. No response repair, prose coercion, probability
normalization or invented missing score is permitted.

For a valid distribution, select the highest-probability label and derive
confidence with the formula above. Ties and confidence strictly below the host
threshold abstain; equality remains eligible. Threshold defaults to 0.6 and must
be finite in [0,1]. Ties use exact maximum equality, without epsilon or label
order. The adapter must report null `selection` on ties and the unique maximum
otherwise; inconsistent selections fail validation.

Confidence is a concentration measure, not an accuracy or calibration guarantee.
The formula is evaluated as an exact rational number for policy. Its JSON numeric
representation has 50 significant decimal digits when nonterminating. Supplied
probabilities keep their decimal values. There is no clamping. A distribution
accepted with slightly deficient mass can have a maximum just below 1/n and
therefore a tiny negative confidence. It abstains even at threshold zero. This
explicit consequence of mass tolerance preserves the formula and probabilities.

Terminating confidence decimals retain every exact digit. Nonterminating
confidence uses host-owned ROUND_HALF_EVEN rendering with precision 50 and
explicit exponent/trap settings. Caller Decimal context cannot change results
or turn an otherwise valid result into an arithmetic exception. JSON budgeting,
fixture transport and CLI output use actual UTF-8 bytes without ASCII escaping.
Invalid surrogate characters still fail before a worker attempt.

Terminal statuses are `decision`, `abstention`, `invalid_input`, `invalid_output`,
`backend_failure`, `timeout` and `cancellation`. Failed or abstained results cannot
appear as accepted decisions. The CLI exits 0 for decision/abstention, 2 for
invalid input/output, 3 for backend failure, 4 for timeout, and 130 for cancellation.
Closed stdout ends quietly with exit 0 for results, argument errors and help,
including buffered and unbuffered modes. A fixture distribution is explicitly
synthetic. Verbal model confidence alone does not satisfy the probability contract.

An ordinary non-EPIPE stdout failure exits 3 without a result or traceback.
Help and results share the same descriptor-redirection guard, including buffered
and unbuffered modes. Redirect before interpreter shutdown so failed buffered
output cannot override the intended status with shutdown-flush exit 120.

## Architecture and state

Flow: library/CLI input → strict request validation → one fixed fixture adapter
child → response/distribution validation → deterministic label/confidence/
abstention policy → typed result.

Contracts, adapter, validation and policy remain case-local. State lasts for one
request, with no persistent memory, training, adaptive thresholds or cross-request
context. The host snapshots fixture input; results expose immutable probability
mappings. One fixed Python worker is terminated and reaped before timeout or
cancellation returns. There is no background inference thread. This process
boundary controls lifetime and is not a security sandbox. A future model backend
requires its own source-checked implementation and evaluation evidence.

## Tools and authority

The fixed adapter may replay only the supplied synthetic fixture. It has no
shell, arbitrary path/URL input, tool discovery, message delivery, payments,
account changes or business-system writes. The host starts only the packaged
worker with the current Python interpreter and isolated import mode. Explicit
input files are read by the host before launch, then the bounded snapshot goes
through stdin. Local result output does not authorize downstream execution.

No provider is configured by this registration. Any later live adapter must define its endpoint, permitted data, case-local configuration, time/cost bounds, and error handling in this specification. Keep credentials and private inputs out of tracked files and result logs.

## Execution and termination

1. Validate the request and host configuration before invoking the adapter.
2. Make at most one prediction attempt. No automatic retries, fallback backend, repair loop, or recursive question generation in the first implementation.
3. Validate the response and probability provenance. Invalid or unavailable probabilities end with an explicit failure, never a fabricated accepted result.
4. Compute the selected label and derived confidence. Return a decision or abstention under host policy, then stop.
5. Backend failure, timeout or cancellation terminates without a decision or
   external effect. Host timeout defaults to 2 seconds and is finite in
   [0.05,10] seconds. The adapter deadline includes launch and waiting. While
   waiting, check deadline/cancellation at intervals of at most 0.01 seconds.
   A host threading.Event can cancel before launch or during execution. SIGINT
   becomes cancellation. Defer SIGINT during launch until the host owns the
   process handle and during cleanup until the child is reaped. The worker has
   a separate session; the host owns cancellation. Once a deadline or cancellation is observed, discard
   a simultaneous response, terminate the child, wait at most 0.1 seconds, then
   kill if needed and wait at most 0.2 seconds. Cleanup failure is an honest
   backend failure, never a claimed clean timeout. OS scheduling and process
   creation latency are not hard realtime guarantees.

## Acceptance criteria

Local fixture acceptance checks are implemented and recorded in README.
Independent substantive review and final fix review passed; README records
the source, case-copy and installed-wheel evidence.
Live-model, calibration and deployment evidence remain unverified.

| Criterion | Required evidence |
| --- | --- |
| A valid synthetic distribution returns the expected typed label, derived confidence, and synthetic provenance through the documented library and demo paths. | Fixture |
| Duplicate labels, extra/missing labels, bool/NaN/out-of-range probabilities, invalid totals, malformed responses, and inconsistent selections cannot produce an accepted decision. | Fixture |
| Ties and below-threshold confidence abstain; a non-tied result exactly at the threshold remains eligible. State text cannot override schema, policy, or authority. | Fixture |
| Backend exception, timeout, and cancellation terminate within selected bounds with at most one attempt and no hidden repair/fallback. | Fixture or mocked-provider |
| Case-only installation and execution require no sibling installation, files, credentials, or runtime; independent invocations share no state. | Isolated fixture run |
| Any future selected live backend returns the documented contract and probability provenance on labeled examples. Provider connectivity and predictive quality are reported separately. No live backend is in this implementation's qualifying scope. | Live-model; deferred |
| Any calibration claim has a held-out labeled dataset, stated metric/method and sample count, and observed results. Schema/fixture success alone never qualifies. | Model evaluation; required only if claiming calibration |

A fixture implementation may establish contract behavior without qualifying a model's predictions. The current `demo-ready` scope satisfies the fixture and isolated-run criteria above and retains live-model and calibration criteria as deferred.

## Dependencies and open decisions

Python 3.14 is required, with 3.14.8 selected for local verification. Runtime
dependencies are empty. Hatchling 1.32.4 is the pinned build backend and uv.lock
locks the local package. No provider configuration or model alias is selected.
Original hand-authored fixtures supply probabilities for mechanics tests only.
Live probability semantics, labeled evaluation and model selection remain future
decisions. Recheck primary sources before that integration.

A conventional structured-output LLM adapter is an implementation alternative, not a substitute for validated probability semantics. Jev integration would remain dependent on TypeSafe's hosted API; a self-hosted model would require separate probability and quality evaluation. No training or model-equivalence claim is in scope.
