# Case instructions

Scope: `agents/10-data-analysis/`.

Read root AGENTS.md, CONTRIBUTING.md, this file, SPEC.md, and README before edits. Keep code, fixtures, dependencies, tests, and artifacts local. Do not import sibling cases or edit root governance.

Use Python 3.14 standard-library Decimal, CSV, statistics, dataclasses, and argparse. Preserve the complete question grammar, observed-record semantics, bounded exact sums, inclusive dates, missing-value disclosures, provenance, and host chart selection. No model or generated-code execution belongs to this contract.

Follow the root code explanation standard. Define observation unit, rounding, missing-data limits, provenance, and file authority beside code. Maintain the README reading guide.

Local commands are `uv sync --locked`, `uv run --locked data-analysis --help`, and `uv run --locked python -m unittest discover -s tests -v`. Record only actual checks. No credentials are needed. Write demo output under this case's ignored artifacts/ directory.
