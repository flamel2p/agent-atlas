# Case instructions

Scope: `agents/09-agentic-workflow/`.

Read root `AGENTS.md`, `CONTRIBUTING.md`, this file, `SPEC.md`, and README before edits. Keep dependencies, fixtures, tests, runtime state, and code local. Do not import sibling cases or add a shared workflow framework.

Use Python 3.14 standard-library dataclasses, enums, SQLite, and argparse. Keep one transaction owner for commands. Assessment and fulfillment are deterministic simulations. Do not add model calls, real procurement, inventory updates, payments, or messaging.

Reviewer labels are synthetic attribution, not authentication. Preserve deadline-first guards, terminal immutability, atomic command receipts, bounded persistent retries, and the unique local fulfillment record. Update the specification if a selected contract needs revision, with the parent owning material decisions.

Follow the repository code explanation standard. Define transaction ownership, replay semantics, simulation limits, and non-obvious guards alongside code. Maintain the linked README reading guide.

Expected local commands are `uv sync --locked`, `uv run --locked python -m unittest discover -s tests -v`, and `uv run --locked agentic-workflow --help`. Record only commands actually run in the README. No credentials are needed.
