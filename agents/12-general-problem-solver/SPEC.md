# General Problem Solver specification

Slug: 12-general-problem-solver
Status: demo-ready
Runtime: Python 3.14 (uv CLI, POSIX)

## Problem and scope

Teach developers how a controller revises a proposed solution using actual evaluator feedback. The scenario is a synthetic scheduling puzzle. A schedule is a hypothesis about integer start times, not an instruction to execute work. Decompose the constraints, propose independent starts, evaluate, select conflict repair, revise, and record a bounded history.

Success establishes feasibility only under the supplied discrete constraints. It does not establish general intelligence, optimality, operational safety, persistent learning, or scientific validity. A local minimum can leave a feasible puzzle unsolved.

## Evidence and decisions

Source facts come from the retained [Agent 12 brief](../../agent-library-analysis/agents/12-general-problem-solver.md), [inventory](../../agent-library-analysis/agent-inventory.md), and [foundations](../../agent-library-analysis/foundations.md). Imran Ahmad's *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 8 describes decomposition, analogy, hypothesis, testing, and adaptation on printed pp.215-220, PDF pp.246-251. Its example on printed pp.226-232, PDF pp.257-263 uses an in-memory log and predetermined scores. Those scores do not demonstrate empirical improvement. The retained analysis was read; the purchased PDF was not re-examined.

Selected decisions are original implementation choices. Use the brief's proposed scheduling domain, actual evaluation, two fixed strategy cards, run-scoped history, and deterministic Python. Independent starts are the baseline. Failed evaluations select bottleneck repair and determine which tasks may move. Cards are marked `illustrative_heuristic`, not retrieved analogies or evidence. No LLM or orchestration framework is required. See [PLAN.md](PLAN.md).

## Inputs and outputs

The public interface is `solve_document(document: bytes) -> Report`. It validates before solving and raises `InputError` for invalid input. Internal parser, evaluator, and controller functions are not re-exported as public package APIs.

Input is a UTF-8 JSON object of at most 65,536 bytes. Every listed field is required. Reject unknown fields, duplicate keys, non-finite numbers, non-integer numeric values, and booleans as integers. IDs match `[a-z][a-z0-9_-]{0,31}`. No free-form instructions are accepted.

```json
{
  "horizon": 4,
  "resources": [{"id": "bench", "capacity": 1}],
  "tasks": [
    {"id": "a", "duration": 2, "earliest_start": 0,
     "latest_finish": 4, "requires": {"bench": 1}, "after": []},
    {"id": "b", "duration": 2, "earliest_start": 0,
     "latest_finish": 4, "requires": {"bench": 1}, "after": []}
  ],
  "budget": {"iterations": 5, "evaluations": 200}
}
```

Bounds are 1-8 tasks, 1-4 resources, horizon 1-24 ticks, duration 1-horizon, capacity and positive demand 1-8, iterations 1-16, and evaluations 1-1024. Task requirements may be empty. Windows satisfy `0 <= earliest_start < latest_finish <= horizon`. IDs are unique within their task/resource namespace. Requirements and dependencies refer to known IDs. Dependency lists are unique, exclude self, and form an acyclic graph. Duration above a task's window, demand above capacity, and jointly impossible dependencies/windows remain valid inputs that can yield `unsolved`.

The immutable report contains status, stop reason, input SHA-256, decomposition, selected-attempt history, total iterations/evaluations, and the best evaluated schedule with its violations. Decomposition lists task windows, dependency edges, and resource groups. A complete candidate has one integer start per task in stable task-ID order. Every history entry records strategy ID, illustrative analogy label, prior triggering violations, candidate/evaluation, and evaluations consumed. History contains the initial proposal and selected revisions, not rejected neighbors. Total counters include rejected neighbors. No timestamps or random values appear.

Status is `solved` only when evaluation has no violations; otherwise `unsolved`. Reasons are `feasible`, `iteration_limit`, `evaluation_limit`, or `local_minimum`. Unsolved output exposes the best schedule as a failed candidate, never an accepted solution or impossibility proof. A scan that selects no revision still contributes to total evaluations and termination reporting.

CLI accepts exactly one of `--example NAME` or `--input PATH`. Packaged examples are `revision`, `already-valid`, `impossible`, `dependency`, `iteration-limit`, `evaluation-limit`, and `local-minimum`. Read only the explicit regular file with a bounded read; pipes/devices fail without waiting. Serialize the complete report before writing it to stdout, and create no output files. Exit codes are 0 solved/help, 1 unsolved, 2 input/usage/I/O error, and 130 interruption. Errors go to stderr and omit full input contents and tracebacks. Validation, solving, and serialization finish before output begins. Output failure or interruption during writing may leave truncated stdout. Consumers must require complete JSON and the expected exit code, with exit 0 required to accept a solved schedule. No credentials or runtime configuration variables exist.

## Architecture and state

`domain.py` owns frozen records, strict parsing, and independent evaluation. `solver.py` owns strategy cards, the public document operation, decomposition, deterministic repair, run counters, and history. `cli.py` owns regular-file I/O, packaged examples, JSON serialization, and exit codes. Thin entry modules expose the operation and CLI. State lives in one call, with no shared cache or durable memory.

Core records are `Task`, `Problem`, `Candidate`, `Violation`, `Evaluation`, `Attempt`, and `Report`, with tuples for nested collections. Violation kinds are `window_start`, `window_finish`, `dependency`, and `capacity`. They contain affected task IDs, relevant resource/tick where applicable, and positive excess. Feasibility derives from an empty violation tuple. Repair score sums excesses. Mixing tick and demand deficits makes this an uncalibrated search heuristic, not confidence or an optimization objective.

The evaluator checks windows, dependencies, and resource use independently of proposals. Intervals are half-open, `[start, start + duration)`, so touching tasks do not overlap. Dependencies require predecessor finish <= successor start. For each resource/tick, sum active demands and compare with capacity. Every active positive-demand contributor appears in a capacity violation. Candidate starts range from zero through `horizon - duration`, inclusive. Thus every candidate fits the horizon even if its task window fails.

## Tools and authority

The solver's only tools are parsing, candidate construction, and pure evaluation. The controller cannot change tasks, constraints, budgets, or evaluator results. Proposals cannot grant feasibility. Source text/cards grant no permissions. The application makes no network, subprocess, database, provider, or real scheduling calls and creates no output files. On a stdout write or flush error, the CLI may redirect that failed descriptor to the POSIX null device solely to discard pending bytes during shutdown. This cleanup grants no arbitrary output-path authority or persistent writes. Input failures do not redirect healthy stdout.

## Execution and termination

1. Bound/decode input and validate all fields/references before constructing immutable records. Sort tasks/resources by ID.
2. Decompose constraints. Propose each task at `min(earliest_start, horizon - duration)`. This baseline ignores coupling.
3. Evaluate the initial candidate, consuming one iteration and one evaluation. Stop immediately if feasible.
4. Before repair, stop if the iteration ceiling is reached, then if the evaluation ceiling is reached.
5. Current violations determine the tasks eligible for repair. Enumerate them by ID and all alternative horizon-valid starts in ascending order. Each neighbor changes one start from the current candidate. Skip unchanged starts. Check the evaluation budget before every evaluation.
6. Select a feasible neighbor immediately, record one revision/iteration, and return solved even if that evaluation exactly uses the budget. Otherwise retain the candidate with a strictly smaller score than the current candidate. Break equal improved scores by lexicographically smallest full starts tuple.
7. At scan completion, select/record the best improving candidate, consuming one iteration. If none exists, stop at `local_minimum`. If the evaluation ceiling interrupts a scan, retain any best improvement already evaluated and stop at `evaluation_limit`. Incomplete scans cannot establish a local minimum. The selected candidate is always the best selected so far because revisions strictly reduce score.
8. Repeat until success or stopping. No retries, random escapes, restarts, constraint relaxation, or global-search fallback. Cancellation reaches CLI interruption handling without persistent partial state.

Iterations bound recorded proposals. Evaluations bound every schedule test, including rejected neighbors. Input bounds cap each evaluation's work. An exhaustive one-step neighborhood is not an exhaustive search of all schedules.

## Acceptance criteria

All criteria require deterministic fixture evidence, not mocked-provider, live-model, or deployment evidence.

1. The revision fixture starts infeasible, repairs tasks implicated by actual capacity failures, and returns an independently verified feasible schedule.
2. An initially feasible schedule uses one proposal/evaluation. Repeated calls produce identical report bytes and share no history.
3. Independent evaluator checks cover exact window, dependency, multi-unit/multi-resource capacity violations, and half-open boundaries. Score equals actual positive excesses.
4. Impossible input returns unsolved with violations. A feasible local-minimum fixture may return unsolved without claiming impossibility. Both budget fixtures stop without extra work, and feasibility on the last evaluation is accepted.
5. Strict parsing rejects duplicate/unknown fields, wrong numeric types, invalid IDs/references, cycles, oversize/deep/malformed input, and bound violations. Well-formed impossible puzzles remain distinguishable.
6. Checks cover feedback-linked revision, stable ties, mid-scan budget preservation, error reporting, CLI codes, input immutability, and independent state. No model/network is needed.
7. Documented commands pass in this case and a case-only copy. An installed wheel runs packaged examples and custom input outside source, without siblings or `PYTHONPATH`.
8. Independent review resolves behavior, authority, isolation, and explanation findings. README/SPEC/catalogue agree with actual evidence. Structure checking passes.

## Dependencies and open decisions

Use Python 3.14.8, `hatchling==1.32.4` for packaging, uv lockfile, and standard-library runtime/tests. These match available local tools, not a claim of newest releases. Official documentation inspected on 22 October 2026 confirms [JSON custom decoding and permissive defaults](https://docs.python.org/3.14/library/json.html), [Hatch package selection](https://hatch.pypa.io/latest/config/build/), [the pinned Hatchling release](https://pypi.org/project/hatchling/1.32.4/), and [uv project/environment/lockfile layout](https://docs.astral.sh/uv/concepts/projects/layout/). Override JSON duplicate/nonfinite defaults. No external API/runtime packages are selected. No material decision remains open.
