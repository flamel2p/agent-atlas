# Case instructions

Scope: `agents/05-document-intelligence/`.

Read root `AGENTS.md`, this file, `SPEC.md`, and README before changing this case. Keep owned code, dependencies, configuration, fixtures, tests, state, and artifacts here. Do not edit sibling cases or introduce a common runtime.

Keep behavior and validation aligned with `SPEC.md`. Update relevant checks and README for behavior changes. Report actual checks and unresolved limits separately.

Follow the root [code explanation standard](../../AGENTS.md#code-explanation-standard): define the case's concepts and responsibilities in code, explain non-obvious decisions and authority boundaries, and maintain the README source reading guide.

Use Python 3.14 and case-local uv tooling on macOS or Linux (POSIX process/pipe APIs; Windows is unsupported). Setup with `uv sync --locked --extra ocr`. Run `uv run --locked document-intelligence --example clean`; test with `uv run --locked --extra ocr pytest -q`. See README for actual evidence and remaining qualifications.

Keep token fixture evidence distinct from local OCR recognition. OCR scores are routing diagnostics, never calibrated field accuracy. Preserve all conflicting/uncertain candidates and exact provenance. No LLM, payment approval, ERP posting, PDF rendering, or review correction is in scope.
