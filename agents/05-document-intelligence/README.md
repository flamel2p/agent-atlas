# Document Intelligence Agent

Slug: 05-document-intelligence
Status: demo-ready
Runtime: Python 3.14 (uv CLI, macOS/Linux POSIX)

## Purpose and contract

Extract invoice number, invoice date, and MYR total with every relevant candidate and its source evidence. Accept a field only when all candidates agree, parse correctly, and meet the selected score and layout rules. Otherwise return a review packet. [SPEC.md](SPEC.md) owns the behavior contract.

This learning demo uses no LLM, persistent memory, payment approval, ERP posting, or review correction. Synthetic token scores are test inputs. Real OCR scores are routing diagnostics, not calibrated probabilities of correctness.

## Setup and run

Use Python 3.14 and [uv](https://docs.astral.sh/uv/) from this case directory. Verification used CPython 3.14.8; the lock pins Pillow 13.0.0 and pytest 9.1.1. No credentials or runtime environment variables are required. Restricted environments can use `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache` for tooling.

```sh
uv sync --locked --extra ocr
uv run --locked document-intelligence --example clean
uv run --locked document-intelligence --example conflicting-total
uv run --locked document-intelligence --example weak-label
uv run --locked document-intelligence --tokens src/document_intelligence/fixtures/clean.json
uv run --locked --extra ocr pytest -q
```

`clean` exits 0 with this complete record:

```json
{"invoice_number":"INV-2026-0042","invoice_date":"2026-10-20","total_myr":"1234.50"}
```

The other examples exit 2 with `record: null`, accepted fields individually visible, and every total candidate retained. These are expected review exits. For fixture-only use, `uv sync --locked` omits Pillow; fixture runtime has no third-party dependencies. The dev group installs pytest.

Image mode additionally requires an explicitly installed system Tesseract binary with English trained data. The application never installs prerequisites. Windows is unsupported because the file/process adapter uses POSIX APIs.

```sh
uv run --locked --extra ocr document-intelligence --images src/document_intelligence/fixtures/invoice.png
```

The original synthetic [PNG](src/document_intelligence/fixtures/invoice.png) was generated with Pillow for future recognition checks. Its text matches the clean example, but the JSON coordinates/scores were authored independently and are not OCR output. Tesseract is absent in the build environment. The image command exits 1 with `ocr_unavailable`; recognition remains unverified.

## Public API and input schema

```python
from pathlib import Path
from document_intelligence import Example, ImagePages, TokenFile, extract_invoice

report = extract_invoice(Example("clean"))
report = extract_invoice(TokenFile(Path("invoice.json")))
# Optional OCR, in caller-supplied page order:
# report = extract_invoice(ImagePages((Path("page-1.png"), Path("page-2.png"))))
print(report.status, report.record)
```

`extract_invoice(source)` owns validation, optional OCR, and extraction. Boundary failures raise `InvoiceError` with stable `.code`, without a partial report. Library callers can observe `KeyboardInterrupt`; the CLI sanitizes it to cancellation JSON and exit 130.

The complete [clean JSON fixture](src/document_intelligence/fixtures/clean.json) documents every key. All keys are required; unknown and duplicate keys fail.

| Object | Keys and meaning |
| --- | --- |
| Root | `schema_version` is integer `1`; `pages` is a list of 1 to 3 pages. |
| Page | `number` is contiguous and 1-based; `width`, `height` are positive integer pixels; `tokens` is a list. |
| Token | `id` is a nonblank string up to 64 characters, unique within its page; `text` is nonblank, up to 256 characters. |
| Layout | `line_key` is `[block, paragraph, line]`, all positive integers; `bbox` is `[left, top, right, bottom]`, half-open pixel edges within the page. |
| Score | `ocr_score` is finite, from 0 to 100, or `null`. Booleans are not numbers. |

Image inputs are explicit `.png`, `.jpg`, or `.jpeg` files whose contents decode as PNG/JPEG. Token files use `.json`. Symlink leaf files and special files fail. Each input is read into one bounded byte snapshot for validation, hashing, and OCR. No URLs, directory scans, PDFs, archives, OCR flags, or executable overrides are accepted.

## Architecture and policy

1. Validate bytes into immutable pages/tokens. Fixture mode never imports Pillow or invokes OCR. Image mode validates dimensions, one frame, and EXIF orientation before fixed English Tesseract TSV calls.
2. Group by page and block/paragraph/line, sort horizontally, and match complete labels at the start of each line. Take only the value span to the right.
3. Retain every candidate. Check format, geometry, and the minimum score across both label and value tokens.
4. Accept one distinct normalized value only when no candidate has a review reason. Emit a complete record only when all three fields are accepted, then stop. No retry or fallback exists.

Invoice labels are `Invoice No`, `Invoice Number`, and `Invoice #`. Date uses `Invoice Date`; totals use `Grand Total`, `Total Due`, and `Amount Due`. Case and trailing colon/period punctuation are normalized. `Subtotal`, `Due Date`, and substring matches are ignored. Identifiers match `[A-Z0-9][A-Z0-9/-]{1,31}`; dates must be real `YYYY-MM-DD` dates. Money uses uppercase `RM` or `MYR`, whitespace, and a positive amount with exactly two decimals. Optional thousands commas require correct grouping. Maximum total is `999999999.99`. Decimal arithmetic preserves exact money output.

Adjacent tokens must overlap vertically, must not overlap horizontally, and must have a gap no larger than six times their maximum height. This applies within cue/value spans and across their boundary. It rejects distant columns even under one OCR line key, but is not general layout recognition. Multiple target cues on one line force review. There is no next-line fallback.

A report includes `source_mode`, ordered `source_sha256` fingerprints, OCR `engine` or null, and canonical `pages` with the complete token ledger. Each field has `status`, `value`, `reasons`, and `candidates`. Candidates retain raw/normalized values, page, separate cue/value token IDs and bounding boxes, minimum score, and reasons. Missing value spans have empty IDs and null bbox. Missing scores make the combined minimum null; present weak scores still receive a reason.

Review codes are `missing`, `missing_value`, `invalid_identifier`, `invalid_date`, `unsupported_currency`, `invalid_amount`, `amount_out_of_range`, `multiple_cues`, `ambiguous_geometry`, `ambiguous_layout`, `missing_ocr_score`, `low_ocr_score`, and `conflicting_values`. Scores below 80 require review. A higher-score candidate cannot erase conflicting, invalid, or weak evidence. Identical values retain all provenance. Token permutations preserve semantic output and canonical ledger order; changing JSON bytes correctly changes the fingerprint. Provenance identifies supplied text, not ground truth.

## Limits, effects, and errors

| Boundary | Limit |
| --- | --- |
| Inputs | 3 pages; 8 MiB combined bytes; 12 million pixels per image |
| Ledger/policy | 5,000 tokens per document; 256 characters per token; 64 candidates per field |
| OCR stdout | 2 MiB per page; 64 KiB per metadata call |
| OCR stderr | 64 KiB per process |
| Time | 10 seconds per process; 35 seconds for the stage including metadata calls |

Limit breaches fail the entire run. The adapter caps streams while reading, uses `shell=False` and fixed arguments, and kills/reaps its process group and closes pipes on completion, timeout, overflow, error, and cancellation. It uses in-memory pipes and creates no scratch files. Errors contain no source text or raw exception. Successful evidence reports intentionally include supplied text.

The stage clock starts before image validation. Native Pillow decoding is synchronous and cannot be preempted; expiry blocks the next process call or report. This is not an OS-level decoder/process sandbox. Images are never rotated, cropped, or rescaled. Nontrivial EXIF orientation and multiframe images fail.

Exit 0 means extracted, 2 means review, 1 means input/dependency/processing failure, and 130 means cancelled. Failure JSON contains a status and stable error code, without a record. Typical codes include `invalid_json`, `invalid_schema`, `invalid_geometry`, `input_limit`, `token_limit`, `candidate_limit`, `ocr_unavailable`, `ocr_language_unavailable`, `ocr_failed`, `ocr_timeout`, and `ocr_output_limit`. Unexpected CLI exceptions become `processing_error`.

## Source reading guide

- [Public exports](src/document_intelligence/__init__.py) define the one-call interface and source types.
- [CLI](src/document_intelligence/cli.py) selects one mode, renders JSON, and maps sanitized errors to exits.
- [Source boundary](src/document_intelligence/source.py) validates snapshots, JSON keys/types/counts, geometry, and canonical token order.
- [Invoice domain](src/document_intelligence/invoice.py) defines immutable records, the accepted/review union, evidence, candidate policy, and derived status. Review the candidate-to-field acceptance transition here.
- [OCR adapter](src/document_intelligence/ocr.py) owns Pillow checks, fixed process authority, bounded pipes, cleanup, and TSV normalization. It has no fixture fallback.
- [Policy checks](tests/test_invoice.py), [ingress/CLI checks](tests/test_source_cli.py), and [mocked OCR checks](tests/test_ocr.py) exercise extraction, review, limits, and failure cleanup.

## Verification

Verified on: 2026-10-20
Verification command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --extra ocr pytest -q -m 'not mocked_ocr'`
Verification mode: fixture
Verification result: passed
Verified scope: strict ingress, exact extraction/evidence, uncertainty/conflicts, layout rejection, byte/page/token/candidate limits, CLI exits and sanitized errors.

Verified on: 2026-10-20
Verification command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --extra ocr pytest -q -m mocked_ocr`
Verification mode: mocked-provider
Verification result: passed
Verified scope: fake executables and mocked TSV, Pillow checks, bounded output/deadlines, failures, cancellation/process cleanup, and no fallback. This does not establish recognition accuracy.

The fixture selection passed 82 checks and the mocked-provider selection passed 28 checks. The documented full suite passed 110 checks on macOS with CPython 3.14.8. CLI subprocess probes returned the expected clean record/exit 0, review examples/exit 2, and actual PNG prerequisite failure/exit 1 with `ocr_unavailable`.

The parent reran all 110 checks after integration. A case-only copy at `/tmp/agent05-isolation-20261020/case` also passed `uv run --locked --offline --extra ocr pytest -q`, all three CLI examples, and the expected missing-Tesseract error. Its environment contained only `PATH`, `HOME`, `UV_CACHE_DIR`, and `PYTHONNOUSERSITE`; no sibling files, provider credentials, or `PYTHONPATH` were supplied.

From that isolated copy, `uv build --offline --wheel --out-dir artifacts/dist` passed. The wheel installed with `uv pip install --offline --python /tmp/agent05-isolation-20261020/wheel-env/bin/python --no-deps artifacts/dist/document_intelligence_demo-0.1.0-py3-none-any.whl`. The fresh interpreter ran with `-I` from an empty directory, imported the installed package, and asserted the exact clean record without Pillow. All uv commands used `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache`. These checks establish case independence and packaged fixture availability.

Independent final review passed after corrections for huge numeric scores, invalid file paths, and Pillow validation order. The reviewer separately reproduced the corrected API failures and PNG/EXIF handling. Root `python3 scripts/check_structure.py`, local Markdown-link checks, and `git diff --check` passed. `demo-ready` covers the selected fixture and mocked OCR criteria. Actual Tesseract recognition, calibrated accuracy, remote CI, and deployment remain unverified. This version has no model integration. The next recognition qualification requires Tesseract with English data and the documented PNG command.

## References and limits

Inspired by Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 6, printed pages 153-160 / physical PDF pages 184-191. The [retained brief](../../agent-library-analysis/agents/05-document-intelligence.md) supplies inherited source findings; the purchased book body was not rechecked. The source example's first-nonempty merging and lost confidence/provenance motivated the stricter contract. Illustrative accuracy/review targets are not measured results here.

Primary API references are [Tesseract TSV usage](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html), [Pillow image validation](https://pillow.readthedocs.io/en/stable/reference/Image.html), and [Python subprocess behavior](https://docs.python.org/3/library/subprocess.html). PDF rendering, handwriting, arbitrary layouts, table extraction, fuzzy matching, review correction, ERP posting, and production qualification remain out of scope.
