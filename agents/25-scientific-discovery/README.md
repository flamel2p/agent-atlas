# Scientific Discovery Agent

Slug: 25-scientific-discovery
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

This original offline demo identifies a planted untested pair in a supplied synthetic corpus, proposes a grounded falsifiable additive hypothesis, plans a constrained virtual experiment, and records prediction-versus-simulated-measurement feedback. It goes beyond a literature summary. No real literature search, laboratory, LLM, training, network, or discovery claim is involved.

[SPEC.md](SPEC.md) owns exact schemas, authority, arithmetic, bounds, and terminal outcomes. [PLAN.md](PLAN.md) records implementation decisions and completed review.

## Setup and run

Run from this directory with Python 3.14 available to uv. There are no runtime dependencies or credentials. The build backend is pinned to cached hatchling 1.32.4. `--offline` requires that backend and a compatible Python to be present locally; removing it permits normal package setup downloads, not runtime network use.

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --offline --locked
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --locked scientific-discovery
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --locked python -m scientific_discovery --input src/scientific_discovery/fixtures/planted.json
```

The default packaged fixture selects `aerogel` and `pulse`. Its singleton means are 4 and 6, so the hypothesis predicts 10 synthetic response points. Simulated combined-arm values 8, 10, 9 have mean 9 and absolute error 1. With tolerance 1, feedback is `consistent_with_prediction`. This is descriptive synthetic agreement, with no significance or causal guarantee. The baseline and singleton controls are proposed only; supplied measurements cover the combined arm.

The virtual plan has four arms, three repeats per arm, 12 total runs, and cost 24 synthetic credits. Budgets are checked before feedback. No experiment is executed. A zero simulated measurement remains valid because the error is absolute.

Strict JSON accepts at most 65536 bytes, depth 12, 4096 values, 8 topics, 8 required sources, 64 papers, and 28 unordered candidates. Exactly one hypothesis is selected lexicographically. Every paper retains its supplied evidence and source identity. The input hash identifies the original bytes. Unknown/duplicate fields, bad identifiers/references, booleans in numeric fields, nonfinite numbers, final input symlinks, and nonregular files are rejected. See the specification for each field's narrower bounds.

## Outcomes and evidence limits

A missing/empty required source, missing citation, or missing singleton evidence produces `coverage_incomplete` without a hypothesis or experiment. Complete coverage describes only caller-declared synthetic sources. Global novelty always remains `unverified`.

Other valid outcomes are `no_gap`, `constraint_blocked`, `awaiting_measurements`, and `completed`. Reports retain reached stages, tested-pair provenance, selected evidence, and unresolved conditions. Conflicting singleton assertions are averaged equally and their ranges remain visible. This aggregation does not establish confidence or consensus. The additive hypothesis is an explicit unvalidated extrapolation.

Valid domain reports exit 0, including unresolved outcomes. Invalid input or input I/O exits 2 with a small JSON error on stderr. Interruption exits 130. Closed stdout exits 1 quietly, including help and buffered/unbuffered Python. There is no retry, arbitrary code, state persistence, provider adapter, or output-path dispatch. The application writes its report only to stdout; shell redirection is caller-owned.

## Source reading guide

- [CLI](src/scientific_discovery/cli.py) owns file/resource loading, help, controlled errors, cancellation, explicit flush, and closed-pipe shutdown handling. [Module entry point](src/scientific_discovery/__main__.py) shares that boundary.
- [Input parser](src/scientific_discovery/input.py) enforces bounded strict JSON, numeric and reference rules, immutable request construction, and regular-file access.
- [Domain](src/scientific_discovery/domain.py) defines run-local records and the coverage → gap → hypothesis → experiment → feedback state machine. Inspect coverage and budget gates before arithmetic consumption.
- [Original fixture](src/scientific_discovery/fixtures/planted.json) supplies two synthetic archives, single-topic effects, tested pairs, citations, the planted pair, and simulated combined-arm measurements.
- [Checks](tests/test_discovery.py) assert independently calculated arithmetic, failure/limit behavior, adversarial data handling, process boundaries, and cancellation.
- [Qualification script](scripts/qualify.py) repeats source checks, copies only this case into temporary storage, builds/installs its wheel, and executes both installed entry points without a repository working directory or PYTHONPATH.

## Verification

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --locked python -m unittest discover -s tests -v
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --offline --locked python scripts/qualify.py
```

Verified on: 2026-10-23
Verification command: `.venv/bin/python scripts/qualify.py`
Verification mode: fixture
Verification result: passed
Verified scope: CPython 3.14.8; 37 checks each in source, standalone copy, and installed wheel (111 passing executions); source and copied module CLI, installed console and module CLI; packaged fixture arithmetic and resource loading; incomplete evidence, zero/negative measurements, disagreement, exact and insufficient budgets, bounded candidates/papers, strict JSON and filesystem input, deterministic isolation, hostile evidence text, controlled invalid input, injected pre-report KeyboardInterrupt, and buffered/unbuffered closed stdout/help.

The qualifying command above was executed from the repository root. The equivalent local command is shown in the preceding block. A direct source fixture CLI run also passed. The first implementation run found directory-descriptor handling and unbuffered help pipe defects; both were fixed before the recorded qualifying run. Qualification staging and environments are temporary and removed after success.

Independent review and fix verification passed. Status is `demo-ready` for the fixture scope; the parent owns catalogue integration. No live-model, external literature, laboratory, deployment, production, scientific validity, or global novelty evidence is claimed. Structural integration is parent-owned.

## References

The [source brief](../../agent-library-analysis/agents/25-scientific-discovery.md) documents Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Chapter 13, printed pp. 375–387 / physical PDF pp. 406–418. The book's incomplete clients, efficacy narrative, and relative-error formula are source context rather than reproduced implementation or validated outcomes. This case uses original synthetic text and code and preserves the repository MIT license.

Independent review found argparse diagnostics could echo oversized caller arguments. A subprocess regression produced over 11 KiB of non-JSON stderr before the fix. Parser errors now enter the bounded JSON boundary. Parent reran 37 tests in source, case-only copy, and installed wheel with `.venv/bin/python scripts/qualify.py`; independent fix review passed.
