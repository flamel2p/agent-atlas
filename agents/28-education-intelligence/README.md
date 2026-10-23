# Education Intelligence Agent

Slug: 28-education-intelligence
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

This offline demo updates synthetic learner beliefs from fixed arithmetic answer keys, respects prerequisites, progresses through guiding hints, and selects due reviews using a supplied clock. It never executes submitted code. No credentials, model, network, or persistent store is required.

[SPEC.md](SPEC.md) defines the complete strict JSON schema, arithmetic, limits, and terminal outcomes. [PLAN.md](PLAN.md) records implementation and review ownership. Independent review and the output-error fix review passed.

## Run the demo

From this directory with Python 3.14.8 and uv available, run:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline education-demo
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline education-demo --input src/education_intelligence/fixtures/missing.json
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline education-demo --help
```

The offline setup requires cached `hatchling==1.32.4`. A fresh environment can omit `--offline` during setup to acquire the pinned build backend. Runtime has no third-party dependency.

The default original fixture starts `count` at 0.7 mastery. Its correct answer produces observation posterior 0.9130434782608695, then post-learning mastery 0.9217391304347826. `add` becomes eligible. The injected clock makes the `count` review due, so the next activity is that review. `multiply` remains locked. The missing-evidence fixture returns `evidence_required` with unchanged learner records.

To supply a session, copy the [default fixture](src/education_intelligence/fixtures/session.json) and pass its path with `--input`. Every field is required. The only objective IDs and answer keys are the host catalog. The uniform inclusive threshold is 0.8. At most 3 objectives, 12 answers, 128 characters per answer, 3 guiding hint levels, 10000 attempts per objective, and 32768 input bytes are accepted. JSON depth is at most 12. Three consecutive incorrect assessments stop as `teacher_review`. State in the returned `state` array can be explicitly supplied on a later invocation.

The CLI reads regular files and refuses final-component symlinks, FIFOs, and devices. It returns errors as bounded fixed codes without caller text. Results and help use controlled writes and flushes. Closed stdout exits quietly with code 0. Normal domain outcomes exit 0, invalid input exits 2, and cancellation exits 130. No report files or learner state are saved automatically.

## Source reading guide

- [cli.py](src/education_intelligence/cli.py) is the installed `education-demo` entry point. Inspect argument authority, bounded no-follow file reads, sanitized error codes, cancellation, and controlled stdout flushing.
- [core.py](src/education_intelligence/core.py) defines the immutable domain records and strict JSON boundary. Inspect graph validation, observation-before-learning math, private run state, the shared 0.8 threshold, replay rejection, teacher-review stop, and evidence-time review scheduling.
- [__main__.py](src/education_intelligence/__main__.py) provides equivalent `python -m education_intelligence` execution.
- [test_core.py](tests/test_core.py) compares calculations with independent rational odds and tests gates, review timing, missing evidence, hint progression, schema errors, limits, and state isolation.
- [test_cli.py](tests/test_cli.py) drives real subprocesses for argument sanitization, file boundaries, packaged fixtures, and closed stdout in buffered and unbuffered execution. Cancellation uses a boundary-injected interrupt and does not claim OS-signal timing coverage.
- [qualify.py](qualify.py) reruns the suite in source, a case-only copy, and an installed wheel from a temporary directory outside the repository. It checks installed import provenance and both console and module execution.

## Verification

Run these case-local commands:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python qualify.py
```

Verified on: 2026-10-23
Verification command: .venv/bin/python qualify.py
Verification mode: fixture
Verification result: passed
Verified scope: 31 tests in source, 31 in a standalone case copy, 31 against an installed wheel; four real CLI fixture runs; wheel import isolation; BKT arithmetic, gates, hints, due timing, input failures, limits, and closed stdout in both buffering modes.

The final qualifying command ran from this case using CPython 3.14.8 after the documented uv setup. Temporary copies, wheels, and environments were removed by the qualification script. Independent review passed 10,648 rational BKT probes. The subsequent stdout fix review passed both case suites and a shared 36-process matrix across cases 28–29, including read-only and closed stdout. Ordinary output errors retain exit 2 without interpreter-shutdown diagnostics.

## Limits and references

The graph and answers are synthetic, and BKT parameters are illustrative. The host trusts supplied state as data and does not authenticate a learner's history. A single correct answer does not prove mastery. Repeating an answer at a fresh timestamp can increase the illustrative belief; there is no independent assessment identity or anti-cheating system. Missing evidence preserves belief and schedules. Review intervals are a fixed demonstration policy, not a validated retention model. No forgetting model, IRT placement, live assessment, pedagogical efficacy study, teacher delivery, live-model validation, deployment, or production qualification is claimed.

The [source brief](../../agent-library-analysis/agents/28-education-intelligence.md) records the book's formula and threshold discrepancies. This original implementation uses one explicit threshold and independently checked observation and learning calculations. [Foundations](../../agent-library-analysis/foundations.md) explain the source-analysis boundary. The repository MIT license applies.
