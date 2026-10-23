# Collective Intelligence Agent

Slug: 29-collective-intelligence
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

Three deterministic roles propose original criteria for a synthetic bounded FIFO queue assignment and cross-review each other's work. The host produces an attributed rubric, rejected/deferred criteria, exact weighted scores, critique links, dissent, and a bounded terminal result. Independent substantive review and the output-error fix review passed.

## Setup and run

Run these commands from this directory. Runtime uses the Python standard library. Packaging uses the cached `hatchling==1.32.4`; offline setup needs uv, Python 3.14.8, and that build backend already available locally.

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --offline --frozen --python 3.14.8
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --frozen collective-intelligence < fixtures/baseline.json
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --frozen collective-intelligence < fixtures/conflicting-scores.json
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --frozen collective-intelligence --help
```

The minimal request is `{"problem_id":"bounded-queue-v1","max_rounds":2,"review_rounds":null}`. Use [replay.json](fixtures/replay.json) for the exact explicit critique format. [SPEC.md](SPEC.md) defines all required fields, bounds, and host policy. No credentials or environment configuration are needed.

The baseline converges after two rounds. Pedagogy/domain criteria are selected with exact scores 25/3 and 35/4; the assessment criterion is rejected at 17/5. Host reviewer weights are pedagogy 3, domain 2, assessment 1. Each mean excludes the criterion's author. These synthetic weights have no accuracy calibration.

| Fixture | Expected terminal status | Policy exercised |
| --- | --- | --- |
| [baseline.json](fixtures/baseline.json) | converged | Deterministic role reviews. |
| [replay.json](fixtures/replay.json) | converged | Explicit complete review graph. |
| [missing-reviewer.json](fixtures/missing-reviewer.json) | unresolved | Missing assessment reviews; full denominators retained. |
| [conflicting-scores.json](fixtures/conflicting-scores.json) | unresolved | Opposing votes remain unresolved despite a weighted mean above 6. |
| [threshold-tie.json](fixtures/threshold-tie.json) | unresolved | Threshold and individual-reviewer ties. |

## Flow, limits, and authority

All three adapters receive the same frozen problem object with no prior proposals. Once all proposals exist, each criterion receives reviews from its other two roles. The second round reconsiders review judgments while preserving original proposals. The host validates identity/reference graphs and synthesizes only proposed criteria. A complete, resolved decision vector must repeat across two rounds with every exact score moving at most 1/4 to converge. Agreement demonstrates this predicate only. Complete round histories retain earlier dissent, while the final `dissent` field contains final-round concerns.

The CLI reads stdin up to 32,768 bytes, with depth 8, 512 JSON values, cardinality 32, strings up to 1,024 characters, and reasons up to 240 characters. Numeric literals are at most 32 characters, with decimal exponents from -12 to 6; scores are finite, non-boolean numbers in [0,10]. Host limits are three roles, three criteria, six reviews per round, and two rounds. Unknown/duplicate keys, self-reviews, forged identities/references, repeated edges, and invalid scores are rejected. Missing edges are valid unresolved evidence.

Reports expose rounded display scores alongside exact numerator/denominator scores. Missing reviews produce null scores and explicit expected/observed weights. Ties, opposing votes, and exhausted budgets remain unresolved. Selected rubric entries are marked provisional whenever convergence fails. Criterion acceptance/rejection/defer decisions link their critiques, and full reasons remain in the report.

Valid `converged` and `unresolved` reports both exit 0. Inspect `status`. Invalid input/arguments return sanitized constant JSON and exit 2; cancellation exits 130; internal failure exits 1. Standalone `--help` is the only argument. Closed stdout terminates cleanly for buffered and unbuffered execution; cleanup redirects descriptor 1 to the operating system null device. Runtime performs no network, model calls, persistence, user-file access, subprocess execution, or external approval. A caller controls stdin delivery and EOF; no hard real-time deadline is claimed.

## Source reading guide

- [cli.py](src/collective_intelligence/cli.py) is the console entry point. Inspect byte-limited stdin, sanitized failures, explicit output flush, and pipe cleanup. [__main__.py](src/collective_intelligence/__main__.py) exposes the same path through `python -m collective_intelligence`.
- [validation.py](src/collective_intelligence/validation.py) parses JSON before adapter execution. Inspect lexical depth checks, duplicate rejection, numeric work bounds, exact schemas, and graph validation.
- [core.py](src/collective_intelligence/core.py) defines frozen domain records, independent proposals, host weights, cross-review aggregation, convergence, proposed-only synthesis, and dissent provenance.
- [test_collective.py](tests/test_collective.py) independently checks arithmetic and the review matrix, probes malicious/bounded inputs, and runs real CLI processes for transport behavior.
- [qualify.py](qualify.py) copies only this case to a temporary directory, runs its tests and console fixtures, builds an offline wheel, installs it in a separate environment, proves import isolation, and repeats all tests and fixtures outside the repository.
- [SPEC.md](SPEC.md), [PLAN.md](PLAN.md), and the [source brief](../../agent-library-analysis/agents/29-collective-intelligence.md) distinguish selected behavior, qualification, and source limitations.

## Verification

Executed on 2026-10-23 using CPython 3.14.8 and uv 0.12.23 on macOS arm64.

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --frozen python -m unittest discover -s tests -v
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --frozen python qualify.py
```

Verified on: 2026-10-23
Verification command: .venv/bin/python qualify.py
Verification mode: fixture
Verification result: passed
Verified scope: 29 case-only copy tests and 29 installed-wheel tests; five actual console fixtures in each environment; wheel import isolation outside the repository.

The direct case suite also passed all 29 tests. Checks cover independent expected weighted scores, complete coverage, no self-scoring, shared immutable initial snapshots, invalid adapter results, strict replay/JSON validation, bounded rounds, missing reviewers, ties, contradictions, exact convergence tolerance, dissent/history fidelity, session isolation, sanitized argument/input errors, real-process cancellation, and six closed-stdout combinations across help/result/error and buffered/unbuffered Python. Baseline CLI and help were also run directly through the installed local console entry point. Independent review passed 363 exact-vote oracle probes. The subsequent stdout fix review passed both case suites and a shared 36-process matrix across cases 28–29. Non-EPIPE output failures now retain exit 1 without interpreter-shutdown diagnostics. The final qualification command ran from this case after the documented uv setup.

## Evidence limits

All data and judgments are original synthetic fixtures. No live model, professional accuracy, expert independence, human approval, provider connection, deployment, or production qualification is claimed. This case does not validate the book's efficacy claims. Weighted agreement can preserve shared mistakes. Readiness covers only the documented fixture contract.
