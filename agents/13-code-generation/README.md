# Code-Generation Agent

Slug: 13-code-generation
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

A deterministic fixture developer proposes a shipping function, receives fixed host test failures, and repairs the source within three attempts. The first proposal wrongly discounts subtotal RM100. Five threshold failures select the repaired proposal, which discounts only subtotals greater than RM100. See [SPEC.md](SPEC.md) for the exact rules and authority boundary, and [PLAN.md](PLAN.md) for the design choices.

## Architecture and flow

The host freezes 20 literal expected results before requesting source. It validates the entire syntax tree, interprets each test with fresh locals, persists the candidate and feedback, and supplies observations to the next proposal. Successful verification stops the loop. Failed checks consume the selected attempt cap.

The restricted language accepts one unannotated `shipping_fee(weight_kg, subtotal_rm)` function. Statements are single-name assignments, `if` with an optional `else`, and `return`. Expressions contain integers, local names, addition, subtraction, and multiplication. A single comparison is allowed only as an `if` condition. Every other construct is rejected, including forbidden syntax in an unreachable branch.

The host owns tests, bounds, input validation and artifact paths. The generated function assumes host-validated inputs and is not a standalone input-validating library. No candidate source is executed as general Python or sent to a subprocess. `ast.parse` creates a syntax tree; the host interprets permitted nodes itself.

## Source reading guide

| Source | Reviewer focus |
| --- | --- |
| [cli.py](src/code_generation_agent/cli.py) | CLI arguments, JSON output, and distinct exit codes. |
| [domain.py](src/code_generation_agent/domain.py) | Frozen shipping specification, 20 literal oracle values, immutable feedback and terminal records. |
| [interpreter.py](src/code_generation_agent/interpreter.py) | Whole-tree allowlist, exact signature, expression semantics, fresh locals, and source/numeric/step bounds. |
| [developer.py](src/code_generation_agent/developer.py) | Proposal-only interface and the five observed failures required to choose repaired source. |
| [fixtures](src/code_generation_agent/fixtures/) | Before/after shipping source and the policy/syntax failure proposals packaged in the wheel. |
| [runner.py](src/code_generation_agent/runner.py) | Attempt counting, feedback history, terminal statuses, and report failure/cancellation behavior. |
| [artifacts.py](src/code_generation_agent/artifacts.py) | Physical workspace markers, exclusive files, atomic report publication, and ownership limits. |
| [verify_contract.py](scripts/verify_contract.py) | Independent literal fee table across the full input domain and controlled rejection probes, using the installed package and packaged fixture. |
| [tests](tests/) | Shipping boundary expectations, malformed proposals, parser and operation limits, isolation, I/O failure, publication interruption, and actual CLI processes. |

## Setup and run

Use Python 3.14 and uv from this case directory. There are no runtime dependencies, credentials or environment variables. Hatchling 1.32.4 is the pinned build dependency. The commands below use the existing local cache. On a fresh machine, omit `--offline` for the initial setup so uv can fetch Python and the build backend.

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline code-generation-agent --scenario repair
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline code-generation-agent --scenario exhaustion
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline code-generation-agent --scenario policy-rejection
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline code-generation-agent --scenario syntax-error
```

`repair` is the default. It exits 0 after two attempts. The three failure scenarios exit 3 after three attempts. Use `--max-attempts 1`, `2` or `3` to lower the cap. A cap of 1 prevents the repair scenario from reaching its second proposal. Invalid input exits 2, an unexpected host/developer/artifact failure exits 4, and a handled cancellation exits 130.

`--workspace PATH` selects the physical case workspace and defaults to the current directory. The workspace must contain the matching `SPEC.md` slug and pyproject project name. Parent-traversal components (`..`), symlinked workspace components, markers, artifact roots and reused run directories are refused. Parent traversal is checked before normalization so `symlink/..` cannot select a different workspace. Use a physical path from `pwd -P` when an operating-system alias such as `/tmp` is a symlink. An installed wheel uses this workspace for output, never its installation directory.

Each run creates `artifacts/<unique-run-id>/`. Every source-contract proposal, including syntax or policy rejection, has `attempt-N/candidate.txt` and `attempt-N/feedback.json`. Invalid type, size or UTF-8 responses get metadata-only feedback with null source fields. They consume one invocation and end failed. No truncated proposal is presented as a complete candidate.

`report.json` contains the terminal result. Only a completed report selects `accepted_source`, a path relative to that run directory. Attempt files and `.report.tmp` have no acceptance authority. The report is published atomically after attempt files are flushed and synced. A later cleanup interruption does not change a published result. An artifact failure can retain incomplete attempt files, and `report_path` is null when report publication fails.

Digests use SHA-256. `specification_digest` identifies the fixed shipping-rule text in `domain.py`; it does not hash the Markdown specification. `oracle_digest` identifies the serialized literal oracle, and `source_digest` identifies the complete proposal's UTF-8 bytes. `attempt_count` counts developer invocations; `attempts` includes fully written records.

The Python API is `code_generation_agent.runner.run(scenario, max_attempts, workspace=...)`. `code_generation_agent.interpreter.interpret(source, weight_kg, subtotal_rm)` interprets one validated input. Its optional `step_limit` can lower the limit to 1..100. Caller input validation applies to these APIs as well as the CLI.

## Verification

Verified on: 2026-10-22
Verification command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v`
Verification mode: fixture
Verification result: passed
Verified scope: 33 local unittest tests under CPython 3.14.8, including all four CLI scenarios, fixed oracle boundaries, feedback-directed repair, interpreter rejection/limits, workspace isolation, invalid responses, I/O failure and cancellation before/after atomic publication.

All four setup/run CLI commands above were also executed directly on 2026-10-22. Repair completed after 2 attempts with exit 0. Exhaustion, policy rejection and syntax error each exhausted after 3 attempts with exit 3. Their stdout JSON matched their finalized reports.

Additional fixture qualification on 2026-10-22 passed:

- `.venv/bin/python scripts/verify_contract.py` checked the repaired fixture against an independent literal fee table for all 21,021 allowed input combinations and 15 rejection probes. The overflow, unbound-name, invalid-input and step-limit probes assert their rejection reasons.
- A fresh copy containing only this case passed the same 33 tests. `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv build --offline` built the source distribution and wheel there.
- `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv venv --python 3.14.8 artifacts/wheel-venv` and `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv pip install --offline --python artifacts/wheel-venv/bin/python dist/agent_atlas_13_code_generation-0.1.0-py3-none-any.whl` installed that wheel separately.
- With `src/` moved out of the import path, `artifacts/wheel-venv/bin/python -I -m unittest discover -s tests -q` passed all 33 tests. `artifacts/wheel-venv/bin/python -I scripts/verify_contract.py` repeated the 21,021-input and 15-rejection checks successfully. The imported package path was inside the wheel environment's `site-packages`.
- Eleven installed `artifacts/wheel-venv/bin/code-generation-agent` invocations checked all four scenarios, repair with cap 1, exhaustion with caps 1 and 2, invalid caps 0 and 4, an unknown scenario and an invalid workspace. Checks compared exit codes, stdout and persisted reports, exact attempt counts, source hashes, feedback files and accepted-source selection. Invalid calls wrote nothing. Those CLI processes received a minimal environment without provider credentials. The local ignored evidence summary is `artifacts/verification/installed-wheel-verification.json`.
- The root `python3 scripts/check_structure.py` and `git diff --check` passed. Structure evidence concerns repository layout and metadata only.

Independent substantive review found a workspace normalization defect. The fix rejects `..` before normalization; two regressions verify no proposals or writes to either possible workspace. Independent fix review confirmed both regressions fail against the pre-fix code, all 21 runner tests pass on the fix, and an actual CLI reproduction rejects the path with no artifacts. No actionable review findings remain. `demo-ready` covers the fixture and local package evidence above.

## Limitations and references

This is fixture evidence for a restricted interpreter. A passing result proves the 20 fixed tests passed; it is not a general correctness proof or evidence of direct CPython candidate execution. The deterministic developer demonstrates one feedback rule, not LLM reasoning. The in-process parser and interpreter are not a production security sandbox. Workspace markers prevent accidental ownership mistakes and do not authenticate a malicious local operator. Crash recovery and hostile concurrent filesystem changes are outside scope.

No live-model, provider, Docker, hosted-CI or deployment checks were run. No arbitrary repository editing, test generation, publication or production merge is provided.

Inspired by [source brief 13](../../agent-library-analysis/agents/13-code-generation.md). Selected source deviations are recorded in SPEC and PLAN. Runtime parsing follows the [Python 3.14 AST API](https://docs.python.org/3.14/library/ast.html). Build metadata pins [Hatchling 1.32.4](https://pypi.org/project/hatchling/1.32.4/). The source brief's observations remain analysis evidence, not claims that the book example was executed.
