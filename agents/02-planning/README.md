# Planning Agent

Slug: 02-planning
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

Build and adapt a synthetic documentation-release task graph. The planner proposes dependencies and worker assignments; host validation and a bounded simulator enforce prerequisites, capacity, completed-work preservation, and completion. See [SPEC.md](SPEC.md) for the selected behavior and [PLAN.md](PLAN.md) for the build sequence. Replay is a deterministic baseline; optional model planning remains separately evidenced.

## Architecture and flow

Validate scenario → propose DAG → validate → schedule synthetic work → observe feedback → revise pending assignments or stop → report. All state lives within one run. No files are published or real workers contacted.

The domain has six required tasks grouped into research, authoring, review, and release. Two research tasks precede drafting; two reviews precede packaging. Tasks can overlap when dependencies, worker availability, and the two-task concurrency limit allow it. A reviewer departure after drafting invalidates pending assignments; a new validated plan can move work to the backup. Removing both reviewers blocks the run.

The planner chooses ordering, additional dependency edges, and qualified worker assignments within this known domain. It cannot invent task completion or bypass mandatory prerequisites. The simulator owns timestamps and task evidence; the release artifact is an in-memory report object emitted only after all six tasks succeed.

## Reading the implementation

Start with [contracts.py](src/planning_agent/contracts.py) for the fixed task vocabulary, proposal/result shapes, and budgets. [controller.py](src/planning_agent/controller.py) contains the agent loop and owns scheduling, observations, revisions, and termination. A DAG is a directed acyclic graph of task dependencies; a tick is simulated time, while the wall budget measures real elapsed time.

Read [validation.py](src/planning_agent/validation.py) for cycle detection, required ancestry, and immutable completed/running records. [backends.py](src/planning_agent/backends.py) supplies replay or model proposals through that same gate. [simulator.py](src/planning_agent/simulator.py) creates synthetic evidence; [fixtures.py](src/planning_agent/fixtures.py) and [cli.py](src/planning_agent/cli.py) define the reproducible entry paths. Source comments explain the authority boundaries and non-obvious scheduling rules alongside the code.

## Setup and run

From this directory, with [uv](https://docs.astral.sh/uv/) installed:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked planning-agent --example normal
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked pytest -q
```

Python 3.14.8 is selected by the case's `.python-version`; dependencies are pinned in `pyproject.toml` and `uv.lock`. The temporary cache location accommodates this workspace's permissions and can be changed. Fresh installation needs package access; replay uses only bundled synthetic data and needs no credentials, sibling installation, or provider SDK.

| Example | Verified replay outcome | Exit |
| --- | --- | --- |
| `normal` | Parallel research and reviews, then release | 0 |
| `reviewer-unavailable` | Visible revision; backup performs remaining reviews | 0 |
| `no-reviewer` | Both reviewers unavailable; blocked without a release | 2 |
| `deadline` | Simulated deadline reached without a release | 2 |
| `task-failure` | Review failure prevents packaging | 2 |

The CLI defaults to `normal` and `replay`. Reports are stdout JSON with terminal status/reason, plan history, task states/evidence, schedule trace, elapsed ticks, and planning counts. No artifact files or persistent state are written. Cancellation exits 130; argument/configuration/validation/provider failures exit 2.

For optional model planning, install the local extra and set `OPENAI_API_KEY` in the invoking shell:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --extra live
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --extra live planning-agent --mode live --example normal
```

`.env.example` lists the variable; `.env` files are never discovered or loaded. Live mode uses `gpt-6-luna` with strict Responses structured output, no tools, `store=false`, 2500 output tokens per proposal, no retries, and at most three proposals including revisions. The official endpoint is explicit; ambient proxy/base-URL overrides do not grant another destination. Provider calls have an overall 20-second timeout and the host run has a 90-second wall budget. Failures do not fall back to replay. Live model behavior remains unverified.

## Verification

On 2026-10-19, the source-comment and reviewer-guide update was checked locally with `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline pytest -q`: **98 passed in 0.39s** (fixture and mocked-provider modes; no API requests). An ad hoc Python AST comparison against `HEAD`, removing only module/class/function docstrings, matched all nine runtime modules. Generated JSON Schemas matched exactly for all six Pydantic models, and `git diff --check -- agents/02-planning` passed from the repository root. Runtime logic, model prompts, and request schemas were preserved; no live-model or deployment validation was performed.

Executed on 2026-10-18, locally on macOS arm64 with CPython 3.14.8 and uv 0.12.23:

- Case-local offline lock and installation succeeded, including resolution/installation of the optional live dependency. This establishes package availability, not provider connectivity.
- `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline pytest -q`: **98 passed in 0.26s**. The suite contains 66 fixture/controller/validation checks, 12 CLI/replay-import checks, and 20 mocked-provider checks. No API requests were made.
- Parent integration independently exercised all five CLI examples with provider credentials and `PYTHONPATH` unset. Normal completed in **6 simulated ticks** with one planning call; reviewer departure completed in **7 ticks** with one revision. No-reviewer blocked at tick 4; deadline terminated at tick 4; task failure terminated at tick 5. Expected exit codes, dependency order, maximum concurrency, per-worker capacity, successful evidence, once-only execution, and completed-work preservation all passed.
- Parent isolation copied only this case to `/private/tmp/agent-atlas-02-isolation-rziodmfi/02-planning`, excluding environments, caches, private configuration/data, and artifacts. With provider variables and `PYTHONPATH` unset, `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline` and `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline pytest -q` succeeded: **98 passed in 0.49s**. Import resolved within the copied case; normal, recovery, and blocked CLI paths matched. This used a populated dependency cache; it does not prove an uncached network installation.
- Independent review examined graph/revision invariants, authority, resource scheduling, evidence gates, failure/stop behavior, optional provider boundaries, isolation, and case CI. Its final run passed **98 checks in 0.22s**, with no remaining actionable findings. Final evidence/doc catalogue updates were integrated by the parent afterward.
- `python3 scripts/check_structure.py` passed from repository root; selected local Markdown links and the new workflow's YAML parsed successfully. These are governance/static checks. The scoped [runtime CI workflow](../../.github/workflows/planning.yml) is configured; hosted CI has not run in this task.

The selected acceptance criteria have fixture and mocked-provider evidence. Status is `demo-ready` for this modeled offline scenario. Live account access, SDK transport/provider compatibility, model planning quality, hosted CI, deployment, and production qualification remain unverified. Each mode record below refers to its stated subset of the same executed 98-check suite.

Verified on: 2026-10-18
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline pytest -q
Verification mode: fixture
Verification result: passed
Verified scope: 78 fixture/controller/CLI checks covering normal scheduling, parallel/resource invariants, availability-driven revision, fixed completed/running records, blocked resources, graph/input/result rejection, failures, deadlines/budgets, cancellation, state isolation, CLI exits/preflight, and replay import without the provider SDK. The other 20 suite checks use mocked-provider mode below.

Verified on: 2026-10-18
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline pytest -q
Verification mode: mocked-provider
Verification result: passed
Verified scope: 20 fake-SDK checks covering strict schema/request context, revision observations, fixed endpoint and environment controls, no tools/store/retries, async timeout/cancellation, refusals/incomplete/malformed output, semantic host rejection, sanitized transport failures, missing prerequisites, and no replay fallback. These checks exercise no real SDK transport or model.

## Limitations and references

This modeled six-task domain demonstrates planning and adaptation, not arbitrary-goal decomposition, optimal scheduling, real document generation, durable learning, or production reliability. Inspired by the [retained planning brief](../../agent-library-analysis/agents/02-planning.md), Chapter 5 of Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; the source supplies conceptual architecture rather than an executed implementation.

The current fixed task durations make worker loss during another task's in-flight execution unreachable through the bundled scenarios. The controller guards that condition and validation preserves running records; the demos establish adaptation between execution batches. A terminal wall timeout can discard an uncooperative injected planner thread; that thread has only proposal context and cannot execute work or change the returned report. The implemented live backend additionally bounds its own async request lifetime.

Current API references checked on 2026-10-18: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Python SDK](https://developers.openai.com/api/reference/python), and [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna). These documentation checks establish the selected API shape, not account access, provider connectivity, or this case's live planning quality.
