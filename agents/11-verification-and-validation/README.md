# Verification and Validation Agent

Slug: 11-verification-and-validation
Status: demo-ready
Runtime: Python 3.14 (uv CLI, POSIX)

## Purpose and contract

Verify structured synthetic release statistics against a versioned local truth snapshot. The verifier checks signed changes, units, target and baseline periods, and exposes missing, stale, and conflicting evidence. Read the [contract](SPEC.md) and [implementation plan](PLAN.md).

Exact agreement is `confirmed`. A nonzero difference within tolerance is `mostly_true`. Disagreement is `contradicted`; insufficient evidence is `unverified`. Every result other than `confirmed` requires review. These labels describe synthetic evidence only.

## Setup and run

Requires Python 3.14.8, uv, and POSIX file flags. Runtime and tests use the standard library. Hatchling 1.32.4 is the pinned build backend. From this case directory:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline verification-agent fixtures/claims.json
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v
```

Remove `--offline` for first setup if the Python distribution or build backend is not cached. No credentials or provider configuration are needed. `as_of` explicitly selects the evaluation date, including historical eligibility.

The exact fixture confirms four claims for `atlas` in `2026-Q3`. It includes `latency_change=-5 relative_percent` against baseline `2026-Q2`, `adoption_change=2.5 percentage_point` against the same baseline, `resolved_tickets=120 count`, and `latency=240 milliseconds`. The report has `review_required=false`, exact snapshot SHA-256, evidence IDs, and auditable exclusions.

Run a mixed report with all four verdicts:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline verification-agent fixtures/scenarios/mixed.json
```

Additional [scenario fixtures](fixtures/scenarios/) exercise tolerance boundaries, reversed direction, percent dimensions, different baselines, unknown metrics, missing/expired/future evidence, conflicts, and signed zero. Inspect each result's `reason`, `eligible_evidence`, `excluded_evidence`, `expected_value`, `difference`, and `applied_tolerance`. The [serialized schema](SPEC.md#selected-snapshot-and-report-schemas) defines null values and normalization.

Exit 0 means a report completed, including unfavorable verdicts; `--help` also exits 0. Exit 2 rejects request syntax, input, or file access. Exit 3 reports invalid/unavailable evidence. Errors contain a stable code without raw rejected data or paths. Interruption before output returns 130; a broken output pipe returns 1. There is no report-file write option or truth/tolerance override.

Library callers can use the same boundary:

```python
from verification_agent import InputError, SourceError, verify_document

report = verify_document(document_bytes)
result = report.as_dict()
```

`verify_document` returns immutable records or raises `InputError`/`SourceError` with a stable `.code`. The caller supplies document bytes; the verifier loads only its fixed bundled evidence.

## Architecture and flow

Validate the whole request and evidence, match full scope and units, filter inclusive validity dates, detect conflicts, then check direction before Decimal differences. Return evidence details and the snapshot digest in one JSON report. Unknown well-formed metrics are unverified. Recognized mismatched dimensions do not compare numbers. Metric baseline shape still applies, while numeric domains apply only in a compatible unit.

The full-scope index retains every record. Equal observations corroborate; differing eligible observations conflict even when their values are close. Expired/future observations remain visible but cannot create a current conflict. Zero has no direction. A fully specified 40-digit Decimal context isolates arithmetic from both active caller settings and mutable default settings, including exponent limits and traps.

All application state is run-local. The CLI reads one bounded regular request file and the bounded packaged snapshot, rejecting final-component symlinks, directories, FIFOs, and other special files. It constructs and serializes the complete report before writing stdout. Broken pipes can truncate transport output, so consumers must check the exit code and parse a complete JSON document. The application creates no state, artifacts, network calls, model requests, or subprocesses. Development tests invoke subprocesses to check the CLI.

## Source reading guide

1. [cli.py](src/verification_agent/cli.py) defines the entry point, complete-output boundary, concise errors, and exit codes.
2. [domain.py](src/verification_agent/domain.py) defines immutable Scope, Quantity, Claim, MetricRule, Evidence, Result, and Report values, normalized serialization, and derived review status.
3. [schema.py](src/verification_agent/schema.py) enforces closed JSON schemas, ASCII lexical forms, finite decimal strings, domain rules, and full snapshot validation.
4. [verifier.py](src/verification_agent/verifier.py) owns `verify_document`, the fixed snapshot authority, complete-scope index, eligibility/conflict/direction precedence, and private Decimal context.
5. [files.py](src/verification_agent/files.py) uses `O_NOFOLLOW`, `O_NONBLOCK`, descriptor checks, and bounded reads to reject unsafe file types promptly.
6. [truth-v1.json](src/verification_agent/data/truth-v1.json) holds the four metric rules and thirteen synthetic records, including corroborating, conflicting, expired, and future examples.
7. [test_verifier.py](tests/test_verifier.py) checks the observable verdicts, exact evidence digest, ordering, domains, normalization, atomic failures, and bounds. [test_cli.py](tests/test_cli.py) checks real CLI processes and file boundaries, plus simulated interruption and permission failures.
8. [check_isolation.py](scripts/check_isolation.py) copies this case, runs its suite, builds and installs a wheel, and verifies independently constructed requests from outside the checkout.

## Verification

Verified on: 2026-10-21
Verification command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v`
Verification mode: fixture
Verification result: passed
Verified scope: 61 standard-library tests covering the exact four-metric path, all verdicts, direction/tolerance precedence, scope/dimension isolation, expiry/conflicts, strict schema/domain/size limits, active/default Decimal context isolation, deterministic immutable reports, sanitized CLI exits, and bounded regular-file reads. Source corruption tests use temporary private test snapshots; no public truth override exists.

Also executed on 21 October 2026 with Python 3.14.8:

- `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv lock --offline` and `uv sync --locked --offline` succeeded in the case directory.
- The documented exact fixture CLI returned four `confirmed/exact_match` results and `review_required=false`.
- The documented mixed fixture CLI returned ordered `confirmed`, `mostly_true`, `contradicted`, and `unverified` results with `review_required=true`.

Permission and interruption error mapping are simulated in targeted checks. Real subprocess checks cover request/source errors, a closed stdout pipe, and rejection of FIFO, directory, symlink, and character-device inputs.

The integrated case and an isolated case-only copy both passed all 61 tests on 21 October 2026. The following command also built a wheel, installed it into a separate environment, and ran 30 CLI invocations across 16 independently specified scenarios from outside the checkout:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/check_isolation.py
```

This check passed with provider credentials and `PYTHONPATH` absent from child environments. It checked all four verdicts, scope/unit mismatches, stale/future/conflicting evidence, small sign reversal, zero, malformed and oversized requests, repeatability, the installed evidence digest, and unchanged fixture bytes. This is local fixture and package-isolation evidence, not an OS sandbox test.

Independent correctness and explanation review completed. Review found mutable Decimal defaults could affect a partially configured context; the final implementation specifies every context setting and includes a regression. The reviewer reproduced both original failures against the fix and confirmed finite results without caller-state changes. The help-exit documentation was also corrected. No actionable findings remain.

Root `python3 scripts/check_structure.py`, Markdown link/anchor validation, new-file whitespace checks, and `git diff --check` passed. No hosted CI, live-model, or deployment evidence is claimed.

## Limitations and references

This deterministic demo does not extract claims from prose, verify source credibility, assess arbitrary logic, or establish publication readiness. Synthetic validity windows and tolerances are selected policy. SHA-256 identifies loaded bytes, not authenticity. File hygiene is not an OS sandbox, and local administrators can modify installed package files. Normal Python/uv development tooling may create its own caches; the application maintains no persistent state.

Inspired by Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 8. See the retained [brief](../../agent-library-analysis/agents/11-verification-and-validation.md), [inventory](../../agent-library-analysis/agent-inventory.md), and [foundations](../../agent-library-analysis/foundations.md). No book code or prompts are copied. Source locators are retained analysis findings, not a new book execution or PDF review.
