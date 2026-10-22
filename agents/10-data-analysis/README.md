# Data Analysis Agent

Slug: 10-data-analysis
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

This original demo translates a constrained analytical question into a typed plan, exact calculations, record provenance, and a host-selected chart. The scenario is synthetic quarterly product activity. The [specification](SPEC.md) owns behavior, and the [plan](PLAN.md) records the design comparison.

The backend is deterministic Python standard library code. It runs without credentials, an LLM, generated code, network access, or another case. State lasts one request. A follow-up is a new complete question, such as the same operation over a narrower interval.

## Setup and run

Run from this case directory. Python 3.14 and [uv](https://docs.astral.sh/uv/) are required. Runtime dependencies are empty; the build backend is `hatchling==1.32.4`.

```sh
uv sync --locked
uv run --locked data-analysis --help
uv run --locked data-analysis --question "top 3 products by revenue_rm from 2026-07-01 to 2026-09-30"
uv run --locked data-analysis --question "monthly units from 2026-07-01 to 2026-09-30"
uv run --locked data-analysis --question "describe revenue_rm from 2026-07-01 to 2026-09-30"
```

The default dataset is [the bundled synthetic CSV](src/data_analysis_agent/data/quarterly_activity.csv). Pass `--dataset path/to/activity.csv` to read a user-supplied CSV. Explicit file inputs are reported as user-supplied, even when the file copies the fixture. The CLI never changes source files.

Every outcome is JSON on stdout. Default execution writes no artifacts. To create `report.json` and `chart.svg`, select a new destination under an existing parent:

```sh
mkdir -p artifacts
uv run --locked data-analysis --question "top 3 products by revenue_rm from 2026-07-01 to 2026-09-30" --output artifacts/top-products
```

`report.json` contains the same outcome as stdout. Open `chart.svg` in a browser. The destination must not exist, and no parent may be a symlink. On macOS, `/tmp` itself is a symlink; use a physical path such as `/private/tmp` for explicit temporary destinations.

Publication creates the destination exclusively and removes its own files and directory after a caught write error or interruption. It does not promise crash-atomic publication or protection from hostile filesystem changes. A process kill or power loss can leave partial output. Inspect that directory and remove it deliberately before reusing the same path. Existing destinations always fail unchanged.

## Supported questions and data

Questions fully match one form, ignoring ASCII letter case and surrounding whitespace:

```text
top N products by METRIC from YYYY-MM-DD to YYYY-MM-DD
monthly METRIC from YYYY-MM-DD to YYYY-MM-DD
describe METRIC from YYYY-MM-DD to YYYY-MM-DD
```

`METRIC` is `units` or `revenue_rm`. `N` is an ASCII integer from 1 to 10. Dates are inclusive, in years 2000-2100, and span at most 366 days. Questions are limited to 256 characters. Extra clauses, unsupported metrics, and invalid dates return `needs_clarification` before dataset I/O.

CSV requires exactly `date,product,units,revenue_rm`, in that order. The file must be UTF-8, at most 256 KiB, and contain 1-1000 records. Product/date pairs must be unique. At most 20 products are allowed; labels contain 1-40 printable ASCII characters without surrounding spaces. Input files must be regular files without a symlink leaf.

Units are blank or a nonnegative ASCII integer up to 1,000,000,000. Revenue is blank or a nonnegative ASCII decimal up to 1,000,000,000.00, with one or two digits after an optional decimal point. Nonempty numeric tokens have at most 13 characters. Signs, exponents, underscores, Unicode digits, and nonfinite values are rejected. All records are validated, including records outside the requested interval.

Blank selected-metric cells are missing values. An observed zero remains an observation. Missing values of the other metric do not affect a result. Reports include total, in-period, outside-period, used, and missing record counts, missing record ordinals, and contributing ordinals for each aggregate. Ordinals count CSV records after the header, not physical text lines. SHA-256 identifies the exact dataset bytes; it does not certify data truth or complete coverage.

| Operation | Calculation and chart |
| --- | --- |
| `top` | Observed subtotals by product, descending by value and then ascending by exact label. Products with no observed selected value are omitted. A zero-baseline bar chart uses the same totals. |
| `monthly` | Every intersecting calendar month, clipped to the interval. Partial months are marked. A month without an observed value is null. At least two observed months select a line chart; null months break lines. One observed month selects a table. Exact point values are available in SVG titles and the report. |
| `describe` | Statistics over individual nonmissing product/date records. Sample standard deviation uses denominator n-1 and is null for one observation. A table uses the same values. |

Sums use an independent Decimal context at precision 40 and are exact within the bounded domain. Money sums have two fractional digits, unit sums are integer strings, and mean, median, and sample standard deviation have six fractional digits with `ROUND_HALF_EVEN`. Decimal values serialize as JSON strings. Counts remain JSON integers.

| Terminal status | Exit | Artifacts |
| --- | --- | --- |
| `completed` | 0 | Only when `--output` succeeds |
| `needs_clarification` | 2 | None |
| `no_data` | 2 | None |
| `invalid_dataset`, `input_error`, `output_error` | 3 | None on expected failures with successful cleanup |
| `cancelled` | 130 | Owned partial output is cleaned up; incomplete cleanup is disclosed |

Invalid CLI options use argparse's exit 2. Expected failures have concise structured messages without raw CSV content. Programming failures propagate rather than becoming a successful analysis.

## Expected synthetic results

The bundled CSV contains 14 records: 12 in Q3 2026 and two outside it. Four products appear in the quarter, including an observed zero. These records are an invented learning fixture, not evidence about any business.

The top-three revenue question returns:

| Product | Observed revenue RM | Contributing record ordinals |
| --- | --- | --- |
| Desk lamp | 12751.50 | 3, 7, 11 |
| Travel mug | 9627.75 | 5, 9, 13 |
| Field notebook | 7840.10 | 2, 6, 10 |

Cable kit's subtotal is RM4560.38. Monthly unit totals are July `425`, August `285`, and September `485`. The revenue description returns count `12`, sum `34779.73`, minimum `0.00`, maximum `4675.55`, mean `2898.310833`, median `2807.750000`, and sample standard deviation `1203.021920`.

The fixture's SHA-256 is `0c0a20a60d2fcb23ca876ff2bb6495c6f20dc38f8f6a09c781021d8553cb6aa9`.

## Architecture and source reading guide

```text
question + bounded CSV bytes
  -> complete grammar and schema validation
  -> one typed rank, monthly, or describe plan
  -> calculation + quality counts + record provenance
  -> JSON and optional SVG from the same values
```

Start with these case-local files:

- [CLI entry point](src/data_analysis_agent/cli.py): `main`, bounded regular-file reads, exit codes, exclusive output ownership, and caught-failure cleanup.
- [Analysis boundary](src/data_analysis_agent/analysis.py): `analyze(question, dataset_bytes, source_label)`, full question matching, all-record validation, missing-value policy, Decimal arithmetic, and host chart selection.
- [Domain types](src/data_analysis_agent/domain.py): immutable records, distinct plan variants, terminal outcomes, quality counts, provenance, and Decimal-to-string serialization.
- [Rendering](src/data_analysis_agent/rendering.py): result serialization, markup escaping, bounded label columns, zero baselines, and null-month line gaps. It does not recompute aggregates.
- [Behavior tests](tests/test_data_analysis.py): independent integer-cents totals, sample statistics and rounding, input rejection, real CLI calls, competing output commands, and injected write failures and interruption.

`analyze` performs no I/O. Its `source_label` identifies supplied bytes and never becomes a path. The reserved built-in label identifies synthetic data only when the bytes also match the fixture hash.

## Verification

Verified on: 2026-10-21
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v
Verification mode: fixture
Verification result: passed
Verified scope: 33 tests on CPython 3.14.8. Covers exact ranking, inclusive and narrowed dates, missing and zero values, record-level sample statistics, rounding and Decimal context isolation, row provenance and byte hashes, grammar and CSV limits, XML escaping and label bounds, real CLI outcomes, source preservation, no-clobber output races, and caught partial-write failure/interruption cleanup. Real SIGINT checks interrupt directory and file acquisition, verify cleanup and handler restoration, and retry successfully.

Additional local fixture checks on 2026-10-21:

- `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv lock --offline` created the case-local lock.
- `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline` passed.
- `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline data-analysis --help` passed.
- The three complete example questions above ran through `uv run --locked --offline data-analysis` and returned the exact values documented here. Each also ran with `--output`, producing JSON matching stdout and valid SVG.
- `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv build --offline` produced the source distribution and `dist/data_analysis_agent-0.1.0-py3-none-any.whl`.

Standalone qualification copied only this case into a fresh temporary directory, excluding its environment, build outputs, and artifacts. With `PYTHONPATH` and provider credentials absent, `uv sync --locked --offline`, all 33 tests, and `uv build --offline` passed. The resulting wheel was installed into another fresh environment with `uv pip install --no-index --no-deps` and run from an empty working directory. Fourteen CLI scenarios passed: ranking, monthly totals, description, narrowed dates, unknown metric, trailing clause, invalid period, no matching records, existing-output refusal, missing month, row-level statistics, singleton, all missing values, and malformed data. Independent assertions checked totals, dates, quality counts, provenance, chart data, failure exits, and default no-write behavior.

Independent review checked the implementation and explanations and compared calculations on 120 generated datasets against independent Fraction and high-precision Decimal references. It found an interruption gap between resource creation and cleanup registration. The SIGINT deferral fix and regression check passed a fresh independent review; no correctness finding remains open.

The generated bar chart, monthly line chart, and summary table were visually inspected in Safari. XML and geometry checks also passed. This is visual evidence for those three examples, not cross-browser or accessibility qualification. Root structure, whitespace, and local documentation-link checks passed. No live-model, external-provider, hosted CI, deployment, or production evidence is claimed; the implemented backend requires no model or network.

To rerun the local behavior checks and build:

```sh
uv run --locked python -m unittest discover -s tests -v
uv build
```

## Limits and references

This is a constrained input language, not general conversational understanding. Supplied records do not define a complete product/date population. Absent rows cannot establish zero activity, and missing values are disclosed rather than imputed. Descriptive results establish neither statistical confidence nor causality. Forecasting, inference, normalization, outlier removal, databases, and generated-code execution are outside this contract.

Inspired by Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 8. The [retained brief](../../agent-library-analysis/agents/10-data-analysis.md) distinguishes source claims from this selected implementation. The purchased source was not rechecked for this task. All demo code and data are original.
