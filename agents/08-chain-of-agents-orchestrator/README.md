# Chain-of-Agents Orchestrator

Slug: 08-chain-of-agents-orchestrator
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

Coordinate deterministic release-note, test, and feedback specialists. The manager validates typed handoffs, shares accepted context, and preserves contradictions and evidence gaps for review. Every source directly asserts the same synthetic `works` proposition for a release, feature, and environment. This is a fixture simulation, not a natural-language analyst or release-approval tool. See [SPEC.md](SPEC.md) and the [implementation plan](PLAN.md).

## Architecture and flow

Validate the fixture, accept release context, run tests and feedback concurrently, validate replies, and reconcile scoped assertions. Run memory belongs to the manager. Specialists receive frozen requests containing only their assigned records and the accepted feature catalogue. Every assigned record must be represented exactly once. The manager verifies the run/task identity, assigned role, source/record reference, byte hash, scope, and literal assertion before accepting a result.

Contradictions retain both sides. Repeated positive records cannot outvote a negative record. Negative observations and missing per-feature role coverage require review. A failed run can still carry accepted evidence and review items. `complete` means full positive and consistent fixture coverage; it does not establish real software quality.

The workflow makes at most three specialist calls, with no retries. Default deadlines are one second per specialist and three seconds per run. The manager enforces deadlines while collecting results, then cancels unfinished work once and drains every started child before return or cancellation propagation. Cleanup can extend wall-clock duration beyond a deadline. Late results cannot update terminal state. No model, network service, shell tool, persistent memory, or deployment capability exists.

## Source reading guide

Read these files in order.

1. [CLI](src/chain_orchestrator/cli.py) owns arguments, JSON output, interruption handling, and exit codes. [The module entry point](src/chain_orchestrator/__main__.py) uses the same CLI.
2. [Contracts](src/chain_orchestrator/contracts.py) defines frozen snapshots, requests/replies, provenance references, task outcomes, and review items. A hash identifies source bytes, not source truth.
3. [Evidence boundary](src/chain_orchestrator/evidence.py) validates exact JSON fields, record identity, string/type limits, and the closed set of packaged resource names.
4. [Specialists](src/chain_orchestrator/specialists.py) transforms assigned records into proposals. It neither schedules work nor changes manager memory.
5. [Manager](src/chain_orchestrator/manager.py) owns dependency gating, concurrent fan-out, exact result acceptance, cancellation/drainage, and reconciliation. `_validate_reply` and `_Run._accept` are the authority boundary.
6. [Manager checks](tests/test_manager.py), [input checks](tests/test_evidence.py), and [CLI checks](tests/test_cli.py) exercise the contract with fixtures, fake specialists, and real CLI subprocesses.

## Setup and run

From this case directory, with Python 3.14 and uv available.

```sh
uv sync --locked
uv run --locked chain-orchestrator consistent
uv run --locked chain-orchestrator contradictory
uv run --locked chain-orchestrator scoped --target-release v0.9
uv run --locked python -m chain_orchestrator --help
uv run --locked pytest -q
uv build --wheel
```

Setup downloads pinned development/build dependencies. Runtime uses only the Python standard library and bundled JSON fixtures. No environment variables, credentials, provider configuration, or sibling installation are required. The console entry point and `python -m chain_orchestrator` are equivalent.

The CLI accepts only the following packaged scenario names and an optional `--target-release` already present in that snapshot. It accepts no input/output path. JSON reports go to stdout; input errors emit a bounded diagnostic on stderr without a partial report or traceback.

| Scenario | Result | Exit | Demonstrates |
| --- | --- | --- | --- |
| `consistent` | `complete` | 0 | Full positive coverage across two features |
| `contradictory` | `review_required` | 2 | Negative feedback retained despite repeated positive records |
| `negative` | `review_required` | 2 | Agreement on a negative assertion still requires review |
| `missing-evidence` | `review_required` | 2 | Missing feedback for one feature remains unknown |
| `prerequisite-failure` | `failed` | 1 | Release exception blocks both dependents |
| `downstream-failure` | `failed` | 1 | Test exception preserves accepted release and feedback findings |
| `timeout` | `timed_out` | 1 | Feedback deadline preserves accepted release and test findings |
| `scoped` | `complete` | 0 | Other releases/environments cannot affect target coverage |

`scoped --target-release v0.9` returns `review_required` with exit 2. Invalid arguments and unsupported releases exit 1. Help exits 0. Keyboard interruption exits 130 after cleanup. The failure/timeout scenarios are manager-owned synthetic controls; source records cannot activate them.

The Python interface is one asynchronous operation returning an immutable `Report`.

```python
import asyncio
from chain_orchestrator import analyze_release

report = asyncio.run(analyze_release("contradictory"))
print(report.status, report.review_items)
```

The underscored `_specialist` and `_limits` keyword arguments exist for trusted local fault testing. They are not plugin-loading or CLI capabilities. Test-facing deadline values must be finite, greater than zero, and at most 60 seconds.

## Verification

Local implementation, standalone qualification, and independent review passed for the selected fixture contract.

Verified on: 2026-10-21
Verification command: `UV_CACHE_DIR=/tmp/agent08-uv-cache uv run --locked pytest -q`
Verification mode: fixture
Verification result: passed
Verified scope: Strict input parsing; exact provenance/completeness; disagreement, negative, and missing evidence; dependency gating and concurrent progress; deadline/late-result rejection; partial failures; cancellation and child drainage; run isolation; all bundled CLI scenarios, argument/help behavior, and POSIX SIGINT exit 130.

The final local suite passed with 104 tests in 2.46 seconds. Review regressions cover cleanup outlasting specialist and run deadlines after external cancellation, sibling failure, timeout, or an existing cancellation. Huge integer deadline inputs are rejected as input errors. All eight scenarios also passed direct `uv run --locked chain-orchestrator <scenario>` status/exit checks after the fixes.

Independent review initially found a second cancellation interrupting asynchronous cleanup and an overflow in validation of enormous timeout integers. Both were fixed and covered by regression checks. A fresh reviewer re-ran all 104 checks and separate cancellation/limit probes against a frozen final snapshot. Cleanup completed in every probe, each child received one cancellation, and no specialist tasks remained. No actionable findings remained. Main-checkout source, tests, and dependency files matched the reviewed snapshot. The root structure checker also passed after catalogue integration.

Environment used for local checks was macOS arm64, CPython 3.14.8, uv 0.12.23, and pytest 9.1.1. `uv lock` and `uv sync --locked` resolved the case's dependencies. The initial offline setup lacked cached pytest; an approved PyPI fetch completed installation. `UV_CACHE_DIR=/tmp/agent08-uv-cache uv build --wheel --offline` built the wheel using pinned Hatchling 1.32.4. A successful build alone does not verify an isolated installed wheel.

### Standalone qualification

On 21 October 2026 the parent copied only this case to `/tmp/agent08-standalone-xzdd9h4g/case`, excluding environments, caches, and build output. The subprocess environment removed `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV`, `OPENAI_API_KEY`, and uv project overrides. No sibling case or root runtime configuration was present.

With `UV_CACHE_DIR=/tmp/agent08-uv-cache`, the following commands passed from the copied case.

```sh
uv sync --locked --offline
uv run --locked --offline pytest -q
uv build --no-sources --offline --out-dir /tmp/agent08-standalone-xzdd9h4g/dist
```

The copied-case suite passed all 104 checks in 2.39 seconds. The build produced an sdist and built its wheel from that sdist. A fresh environment then installed only that wheel.

```sh
uv venv --python 3.14 /tmp/agent08-standalone-xzdd9h4g/wheel-env
uv pip install --python /tmp/agent08-standalone-xzdd9h4g/wheel-env/bin/python --no-deps --offline /tmp/agent08-standalone-xzdd9h4g/dist/chain_of_agents_orchestrator-0.1.0-py3-none-any.whl
```

All eight scenarios ran through the installed `wheel-env/bin/chain-orchestrator` executable from the temporary parent directory, outside the source case. Their JSON statuses and exit codes matched the table above. The installed runtime had no third-party dependencies. The documented `uv run --locked --offline chain-orchestrator consistent` command also passed in the main checkout with three accepted specialists and no review items. These are fixture and packaging results, not hosted CI or deployment evidence.

## Limitations and references

Inspired by the [retained Chapter 7 brief](../../agent-library-analysis/agents/08-chain-of-agents-orchestrator.md) for Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026. Original implementation. Source examples are not runtime evidence.

Provenance is exact record/byte identity, not factual verification. The shared `works` proposition is deliberately synthetic; real test results and user sentiment would need a different interpretation contract. There is no confidence score, source hierarchy, majority vote, automatic conflict resolution, or release authorization.

Deadlines use cooperative asyncio cancellation. Built-in specialists are bounded and cooperative; arbitrary injected Python can block the event loop or suppress cancellation indefinitely. Frozen dataclasses and validation do not sandbox hostile Python. No live model/provider, hosted CI, or deployment validation was performed. The purchased book was not re-read for this build; source claims use the retained brief.
