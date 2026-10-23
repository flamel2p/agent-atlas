# Typed Decision Agent

Slug: 31-typed-decision
Status: demo-ready
Runtime: Python 3.14, standard library, deterministic fixture backend
Library ID: 31

A case-local library and CLI for validating categorical probability responses
and applying explicit abstention policy. The included adapter replays original
synthetic fixtures. It does not infer answers for new text or demonstrate model
quality. Independent substantive review and final fix review passed. See [SPEC.md](SPEC.md) for the contract and [PLAN.md](PLAN.md) for decisions.

## Run the fixture demo

From this directory, with uv and Python 3.14 available:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline typed-decision
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m typed_decision --threshold 0.9
```

The first invocation returns `decision`, label `information`, confidence `0.85`,
and explicit synthetic provenance. Raising the host threshold to `0.9` returns
`abstention` with no selected label. Both exits are 0. The offline commands require
Python 3.14.8 and Hatchling 1.32.4 in the local uv cache. No runtime dependencies,
provider, network access or credentials are required.

To supply explicit files, use `--request PATH --fixture PATH`. The original
examples are [request.json](src/typed_decision/data/request.json) and
[decision.json](src/typed_decision/data/decision.json). Their request objects must
match exactly. A different state requires a deliberately authored matching
fixture; this binding prevents fixture numbers from implying inference on new
text. `--help` describes host flags. `--timeout` defaults to 2 seconds and accepts
0.05–10 seconds. Request text cannot change configuration.

## Import the library

```python
from decimal import Decimal
from importlib.resources import files
from threading import Event

from typed_decision import Policy, predict
from typed_decision.json_boundary import loads

fixture = loads(files("typed_decision").joinpath("data/decision.json").read_bytes())
cancel = Event()
result = predict(
    fixture["request"],
    fixture=fixture,
    policy=Policy(threshold=Decimal("0.6"), timeout_seconds=2),
    cancel=cancel,
)
print(result.to_json())
```

`predict` accepts JSON-shaped dictionaries and returns a terminal `Result`.
`Result.probabilities` is immutable. Cancellation can be signaled before or during
the request using the host Event. No adapter callbacks or generated executable
code are accepted. The fixed subprocess has one attempt and the host reaps it
before returning a clean timeout or cancellation.

## Contract and uncertainty

The exact request keys are `request_id`, `state`, `question` and `labels`. Labels
are 2–16 distinct strings. Unknown/duplicate JSON keys, malformed values,
oversized/deep JSON and unsafe explicit files fail validation. Read the exact
[input/output limits](SPEC.md#inputs-and-outputs) before composing callers.

The response must contain every label exactly once, finite numeric probabilities
in [0,1], mass within absolute tolerance 1e-9 of 1, matching synthetic provenance,
and a selection consistent with its maximum. Booleans are not numbers here. There
is no repair or normalization. Ties abstain without label-order selection.

Confidence is `(pmax - 1/n)/(1 - 1/n)`, a concentration measure. It is not the
probability that a selected answer is correct. Exact rational arithmetic applies
the threshold; strictly lower values abstain and equality is eligible. JSON
confidence uses up to 50 significant decimal digits for nonterminating values.
Terminating confidence retains every exact digit. Host-owned rendering uses
ROUND_HALF_EVEN and does not inherit caller Decimal precision, rounding,
exponent or trap settings. Internal transport and CLI results use UTF-8 bytes,
so Unicode text is limited by actual encoded bytes rather than ASCII escapes.
Mass tolerance can admit a slightly deficient near-uniform distribution with a
tiny negative confidence. The host retains the formula and original scores,
then abstains even at threshold zero.

Every result includes `backend: fixed-fixture-v1`, `mode: fixture`, and
`probability_provenance: synthetic-hand-authored;not-model-probabilities`. This
identity on a failure describes the configured mode; the null distribution has
not passed validation. Valid abstentions retain probabilities and confidence.
Failure outcomes do not. Only `decision` carries `selected_label`.

| Status | CLI exit | Meaning |
| --- | --- | --- |
| `decision` | 0 | Unique maximum meets the host concentration threshold. |
| `abstention` | 0 | Tie or confidence below the threshold. |
| `invalid_input` | 2 | Request, host configuration or CLI input failure. |
| `invalid_output` | 2 | Fixture, binding, provenance or distribution failure. |
| `backend_failure` | 3 | Fixed worker could not run, failed, or cleanup failed. |
| `timeout` | 4 | Deadline exceeded and child cleaned up. |
| `cancellation` | 130 | Host cancellation or SIGINT, with no accepted decision. |

Error reasons are bounded host-owned codes. Closed stdout exits quietly with
code 0, including help and invalid arguments in buffered and unbuffered modes.
An ordinary non-EPIPE stdout failure exits 3 without JSON or traceback. Both
output failures redirect the descriptor before shutdown to prevent another
buffered flush from changing the exit status to 120.
The process boundary controls lifetime; it does not sandbox untrusted Python.
This demo executes only its own fixed worker. Scheduling and spawn latency are
not hard realtime guarantees. Cleanup waits total at most 0.3 seconds after
timeout/cancellation is observed.

## Verification

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python qualify_isolation.py
```

Verified on: 2026-10-23
Verification command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v`
Verification mode: fixture
Verification result: passed
Verified scope: 40 checks on local macOS with CPython 3.14.8. Normal library and actual CLI paths, rational arithmetic for 2–16 labels, exact terminating confidence beyond 50 digits, caller Decimal context independence, ties, exact threshold equality and neighbors, mass tolerance boundaries, deficient near-uniform distributions, strict requests/responses/provenance/binding, UTF-8 state/labels/request IDs and exact byte bounds, sanitized surrogates, Unicode CLI output under ASCII-configured stdout, single-attempt failure, actual worker timeout/reaping/cancellation, SIGINT including worker-launch interruption, strict files/JSON, sanitized arguments, quiet closed stdout and read-only stdout failures for help/results in both buffering modes.

Additional actual runs on 2026-10-23 in fixture mode:

- `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv lock --offline` and `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline` passed with Python 3.14.8 and Hatchling 1.32.4.
- `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline typed-decision` returned the expected synthetic `information` decision and confidence `0.85`.
- `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python qualify_isolation.py` passed all 40 checks in a case-only copy and all 40 again from an installed wheel in an empty working directory. Both runs exercise the installed console entry point and packaged resources. Temporary environments and artifacts were removed.

The first local test pass found a nonnumeric CLI threshold escaping as a Decimal
exception. The number boundary was fixed, and final unit and isolation runs passed
after that fix. Repository structure checks and independent review passed. Live-model, calibration, predictive evaluation,
hosted CI and deployment evidence remain unverified.

Independent review identified three P2 defects in terminating confidence
precision, inherited Decimal context and ASCII-expanded UTF-8 byte accounting.
Failing-before regressions reproduced each defect. The fixes preserve exact
terminating values, own the repeating-decimal context and count actual UTF-8
bytes throughout transport. The transport audit also reproduced and fixed an
ASCII-configured stdout crash on Unicode results. Final 40-check local, copied
case and installed-wheel runs passed after these fixes. Independent fix review repeated all 40 source, 40 copied-case and 40 wheel
checks and found no remaining actionable findings. Additional independent
probes passed exact 60-digit rendering, all Decimal traps enabled, Unicode
transport under an ASCII locale, read-only and closed stdout, and real SIGINT
cancellation. Readiness covers the selected fixture contract only.

The final output-failure regression reproduced non-EPIPE stdout errors causing
tracebacks and shutdown exit 120 with a read-only descriptor. The shared guard
now redirects before returning exit 3. Argparse help writes propagate errors to
this guard, including in unbuffered mode. Actual result/help processes pass in
both buffering modes, while the existing EPIPE exit-0 checks still pass.

## Read the implementation

| File | Reviewer focus |
| --- | --- |
| [cli.py](src/typed_decision/cli.py) | Entry point, explicit file authority, sanitized errors, exits and guarded stdout flush. |
| [__init__.py](src/typed_decision/__init__.py) | Public `Policy`, `Result` and `predict` interface. |
| [contracts.py](src/typed_decision/contracts.py) | Immutable request/result state, exact schema, provenance, rational arithmetic and host abstention gates. |
| [json_boundary.py](src/typed_decision/json_boundary.py) | Byte/depth/numeric bounds, strict JSON, library snapshots and no-follow regular-file reads. |
| [runtime.py](src/typed_decision/runtime.py) | One fixed child, cancellation/deadline priority, terminate/kill/reap cleanup and honest failures. |
| [_worker.py](src/typed_decision/_worker.py) | Fixed synthetic replay and explicit fail/hang modes, without arbitrary code or provider access. |
| [test_decision.py](tests/test_decision.py) | Independent arithmetic oracle, threshold/tolerance neighbors and probability validation failures. |
| [test_boundaries.py](tests/test_boundaries.py) | Host input boundaries and actual child lifetime checks. |
| [test_cli.py](tests/test_cli.py) | Real-process CLI, SIGINT, error sanitation and stdout behavior. |
| [qualify_isolation.py](qualify_isolation.py) | Reusable case-only copy and clean installed-wheel qualification. |

## References and limits

This independently designed case is inspired by [TypeSafe AI's Jev](https://docs.typesafe.ai/introduction),
its [typed primitives](https://docs.typesafe.ai/primitives) and
[Choice confidence formula](https://docs.typesafe.ai/confidence). The latter two
were rechecked on 2026-10-23. Jev is the official product spelling. #31 is an Agent
Atlas project extension, not an additional numbered book pattern.

The official [System One Adapter](https://github.com/typesafe-ai/system-one-adapter-python)
is a source reference only. No vendor code, model or API is used. There is no
claim of compatibility, equivalent architecture, weights, sampler, RLCD,
calibration, speed/cost, semantic correctness or production qualification.
Numerical/boolean predictions, batches, images, training, serving, integrations,
live providers and business effects remain deferred.
