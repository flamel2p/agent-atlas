# General Problem Solver

Slug: 12-general-problem-solver
Status: demo-ready
Runtime: Python 3.14 (uv CLI, POSIX)

## Purpose and contract

A bounded scheduling puzzle demonstrates decomposition, proposal, constraint evaluation, strategy revision, and run-scoped memory. Independent starts form the baseline. Actual violations select tasks for local repair. The evaluator alone accepts a schedule. Read [SPEC.md](SPEC.md) for exact contracts and [PLAN.md](PLAN.md) for the design.

This deterministic demo has no LLM, runtime network, persistent learning, or real execution. Analogy cards are illustrative heuristics. Local minima can leave feasible puzzles unsolved.

## Architecture and flow

Parse bounded JSON into immutable records, decompose constraints, propose independent starts, evaluate, and repair tasks implicated by failures. Stop on feasibility, either work budget, or a local minimum. All history belongs to one invocation.

## Source reading guide

- [Public package entry](src/general_problem_solver/__init__.py) exposes `solve_document`, `InputError`, and the immutable `Report` type.
- [Domain and evaluator](src/general_problem_solver/domain.py) define immutable records, strict JSON parsing, reference validation, and per-tick constraint evaluation.
- [Solver](src/general_problem_solver/solver.py) defines the two illustrative strategy cards, conflict selection, deterministic ties, and both work budgets.
- [CLI](src/general_problem_solver/cli.py) owns bounded regular-file reads, packaged examples, report serialization, and exit codes. The [module entry](src/general_problem_solver/__main__.py) uses the same CLI.
- [Packaged examples](src/general_problem_solver/examples/) contain seven complete input documents. The feasible [local-minimum example](src/general_problem_solver/examples/local-minimum.json) exposes the search limitation.
- [Domain tests](tests/test_domain.py), [solver tests](tests/test_solver.py), and [CLI tests](tests/test_cli.py) check the input boundary, exact evaluator deficits, independent feasibility, feedback, budgets, and input/output behavior.
- [Installed CLI checker](scripts/check_installed.py) exercises an installed executable using [ten independently derived puzzles](tests/acceptance_cases.json). Its separate oracle checks scores and enumerates feasible schedules without importing the solver.

## Setup and run

Use Python 3.14.8 and uv. Run these commands from this directory:

```sh
uv sync --locked
uv run --locked general-problem-solver --example revision
uv run --locked general-problem-solver --example impossible
uv run --locked python -m unittest discover -s tests -v
```

The `impossible` example intentionally exits with code 1. Use `--input path/to/problem.json` for your own UTF-8 JSON regular file. The [revision example](src/general_problem_solver/examples/revision.json) is a complete input template. [SPEC.md](SPEC.md#inputs-and-outputs) defines all fields, bounds, and validation rules.

No credentials or runtime environment variables are required. In the development sandbox, prefix uv commands with `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache`. If build dependencies are already cached and network access is unavailable, `uv sync --locked --offline` can use that cache.

The CLI emits one JSON report. Exit codes are 0 for solved or help, 1 for unsolved, 2 for input, usage, or I/O errors, and 130 for interruption. Errors go to stderr. Pipes, devices, and directories are rejected. The application creates no output files and makes no runtime external calls. Output failure or interruption during writing can leave truncated stdout. Accept a solved schedule only with complete JSON and exit 0.

## Reading a report

`best.candidate.starts` follows the task IDs in `decomposition.windows`, sorted by ID. A best candidate is accepted only when `status` is `solved`. Every violation reports its kind, affected task IDs, positive excess, and resource or tick when applicable.

`history` contains the initial proposal and selected revisions. Each revision includes its prior triggering violations and the evaluations consumed by its scan. Rejected neighbors affect the total `evaluations` counter. A scan with no selected revision can increase the total without adding a history entry. `iterations` equals the number of recorded proposals.

The repair score sums positive constraint excesses. It combines tick and demand units, so it is uncalibrated search guidance. `input_sha256` hashes the exact supplied bytes. Identical input bytes produce identical report bytes.

Observed packaged examples on 22 October 2026:

| Example | Status and stop reason | Iterations | Evaluations | Best starts | Score |
| --- | --- | ---: | ---: | --- | ---: |
| `revision` | solved, feasible | 2 | 3 | `[2, 0]` | 0 |
| `already-valid` | solved, feasible | 1 | 1 | `[0, 2]` | 0 |
| `impossible` | unsolved, local_minimum | 1 | 1 | `[0]` | 2 |
| `dependency` | solved, feasible | 2 | 5 | `[0, 2]` | 0 |
| `iteration-limit` | unsolved, iteration_limit | 1 | 1 | `[0, 0]` | 2 |
| `evaluation-limit` | unsolved, evaluation_limit | 2 | 2 | `[1, 0]` | 1 |
| `local-minimum` | unsolved, local_minimum | 1 | 7 | `[2, 1, 1]` | 1 |

The local-minimum puzzle has a feasible schedule `[3, 2, 1]`. No allowed single-task move strictly improves the failed candidate. The solver therefore stops without claiming that the puzzle is impossible.

## Verification

Verified on: 2026-10-22
Verification command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v`
Verification mode: fixture
Verification result: passed
Verified scope: 35 tests cover strict parsing, exact constraint deficits, independently checked feasibility, immutable state, feedback, deterministic ties, both budgets, local minima, seven CLI examples, regular-file enforcement, injected interruption, closed output pipes, and read-only stdout descriptors.

The final suite passed in the workspace and a case-only copy at `/tmp/agent12-caseonly`, without repository or sibling resources. Both used separate case environments installed with `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline`. Environment was macOS, CPython 3.14.8, and uv 0.12.23. The initial online sync failed on sandbox PyPI DNS resolution. Cached offline installation succeeded; a fresh dependency download was not validated.

Verified on: 2026-10-22
Verification command: `.audit/venv/bin/python scripts/check_installed.py --executable .audit/venv/bin/general-problem-solver --cases tests/acceptance_cases.json`
Verification mode: fixture
Verification result: passed
Verified scope: 42 installed-wheel CLI invocations cover ten independent puzzles, repeatable output and unchanged input, seven bundled examples, malformed/oversized/missing/nonregular input, help, and closed or read-only stdout for solved, unsolved, and help output. The independent oracle enumerates 424 schedule combinations across the ten inputs and checks selected schedules, violation facts, scores, feedback links, budgets, and expected stopping reasons.

The checker runs subprocesses from a temporary directory outside the checkout and removes `PYTHONPATH` and `PYTHONHOME`. The installed package path was confirmed under `.audit/venv/lib/python3.14/site-packages/`. Build/install commands actually run from this case:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv build --offline --wheel --out-dir .audit/dist
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv venv --python 3.14.8 .audit/venv
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv pip install --python .audit/venv/bin/python --no-index --no-deps .audit/dist/general_problem_solver-0.1.0-py3-none-any.whl
```

These commands built the final source and installed its wheel into a fresh environment. The direct command `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline general-problem-solver --example revision` returned solved with exit 0, two iterations, three evaluations, and starts `[2, 0]`.

Independent review found buffered stdout failures that surfaced at interpreter shutdown, an overstated output-atomicity claim, and a race in the installed checker's closed-pipe setup. The CLI now handles write and flush errors together, discarding pending bytes through the null device only after output failure. The contract explains possible truncated output, and the solver explanation identifies the current candidate as each scan's feedback source. The checker closes the pipe reader before launching the child. Fresh independent review found no actionable issues and passed all ten CLI test methods against the installed package plus the 42-invocation checker. Root `python3 scripts/check_structure.py` passed. These checks qualify the documented fixture demo.

No mocked-provider, live-model, hosted CI, deployment, or production qualification was performed. Runtime uses no model or network. Source analysis and official documentation establish provenance and choices, not provider evidence.

## Limitations and references

The heuristic is neither complete nor optimal. Bounded failure is not an infeasibility proof. Scores are search guidance, not confidence. Source caveats are in the [brief](../../agent-library-analysis/agents/12-general-problem-solver.md). Attribution is Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 8. This implementation does not reproduce predetermined scores or validate scientific analogies.
