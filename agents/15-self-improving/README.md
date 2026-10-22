# Self-improving agent

Slug: 15-self-improving
Status: demo-ready
Runtime: Python 3.14, uv, standard library runtime, unittest

## Purpose and contract

Observe synthetic FAQ failures, propose one topic-scoped retrieval revision tie-breaker, and test it against an unchanged baseline. Passing produces `review_required`; a regression rejects the candidate. Every outcome keeps the baseline serving. Read [SPEC.md](SPEC.md) for authority, input bounds, and gate rules and [PLAN.md](PLAN.md) for the selected design.

## Architecture and flow

The loader validates separate selection, host curator, and holdout files. The pure experiment replays corrections, requires two independent failures for exactly one topic, freezes one candidate, checks development controls, and evaluates heldout cases once. Reports are immutable run-scoped records printed to stdout. The runtime does not persist, approve, activate, train, deploy, retry, or call a provider.

## Source reading guide

1. [CLI](src/self_improving/__main__.py) parses the allowlisted scenario and prints one terminal JSON report.
2. [Fixture boundary](src/self_improving/scenarios.py) defines hard caps, exact schemas, reference checks, and query split separation. Inspect the distinction between malformed host data and ineligible feedback.
3. [Experiment domain](src/self_improving/experiment.py) defines frozen snapshots, positive-overlap retrieval, curator-backed evidence, proposal identity, development checks, and the heldout gate. Follow `run_experiment` and `_select` to inspect authority and stopping behavior.
4. [Synthetic fixtures](src/self_improving/fixtures/improvement/selection.json), [host curator manifest](src/self_improving/fixtures/improvement/curators.json), and [heldout cases](src/self_improving/fixtures/improvement/holdout.json) make the partition and local label authority visible.
5. [Experiment tests](tests/test_experiment.py), [schema tests](tests/test_scenarios.py), and [CLI tests](tests/test_cli.py) contain independent expected choices and malformed-input checks. [Qualification script](scripts/qualify.py) checks a copied standalone case and an installed wheel. The [independent oracle](scripts/verify_independent.py) enumerates query combinations, derives expected ranking choices, recomputes lineage digests, and checks heldout-label isolation through the experiment interface.

## Setup and run

Prerequisites are Python 3.14, uv, and cached `hatchling==1.32.4` for offline installation. No environment secrets or `.env` file are needed. Run these commands from this case directory:

```sh
export UV_CACHE_DIR=/tmp/agent-atlas-uv-cache
uv sync --locked --offline
uv run --locked --offline self-improving-agent --scenario improvement
uv run --locked --offline self-improving-agent --scenario regression
uv run --locked --offline self-improving-agent --scenario insufficient
uv run --locked --offline self-improving-agent --scenario poisoned
uv run --locked --offline self-improving-agent --scenario development-rejection
uv run --locked --offline self-improving-agent --scenario no-gain
uv run --locked --offline python -m unittest discover -s tests -v
uv run --locked --offline python scripts/qualify.py
uv run --locked --offline python scripts/verify_independent.py
```

Completed experiments exit 0, including rejections. Invalid CLI arguments or malformed fixtures exit 2 without a report. `improvement` returns `review_required` with 4/7 baseline and 7/7 candidate correct. `regression` returns `rejected_regression` despite a gain from 5/8 to 7/8, because `stable-legacy-window` becomes wrong. `insufficient` and `poisoned` return `no_proposal_insufficient`. The focused scenarios return `rejected_development` and `rejected_no_gain`.

The JSON report includes baseline/candidate lineage, full supporting evidence, feedback exclusions, per-case retrieval rankings, exact-ID correctness, group counts, and reproducible SHA-256 digests. Candidate creation receives no holdout queries or labels. A Python caller uses the same operation:

```python
from self_improving import ScenarioName, load_scenario, run_experiment

report = run_experiment(load_scenario(ScenarioName.IMPROVEMENT))
assert report.serving_version_id == report.baseline.version_id
print(report.to_json())
```

To retain a report, create a case-local `artifacts/` directory and redirect stdout there. That is user-owned persistence and does not create an immutable file registry. Offline setup fails if the Python runtime or build backend is absent from the local cache. The same pinned setup can populate that cache with network access through `uv sync --locked`.

## Verification

Verified on: 2026-10-22
Verification command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v`
Verification mode: fixture
Verification result: passed
Verified scope: six terminal scenarios, authority exclusions, deduplication/conflicts/ambiguity, relevance and topic limits, frozen baseline, deterministic lineage and digests, heldout-label isolation, malformed input/resource bounds, CLI arguments, and I/O failures.

The local environment was CPython 3.14.8 and uv 0.12.23. `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/qualify.py` also passed a copied-case suite and a built, separately installed wheel. Installed checks exercised all six outcomes, independent improvement/regression counts, report digests, byte determinism, and the module CLI from an empty directory with Python path overrides removed.

The parent separately ran the 28-test suite and qualification in the primary checkout. `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/verify_independent.py` passed six terminal scenarios and 372 enumerated queries with 744 independently derived baseline/candidate choices. It recomputed corpus, selection, holdout, version, and report digests and confirmed that changing heldout labels preserves the proposal. Qualification also passed these oracle checks against the installed wheel with isolated Python from an empty directory. The bounded queries derive from up to eight fixture tokens, subsets of at most three tokens, and all corpus topics plus an unknown topic. They are synthetic contract checks, not a representative traffic sample.

Direct CLI runs observed improvement at 4/7 to 7/7 correct and regression at 5/8 to 7/8 with one lost correct answer. These are complete finite-fixture counts, with per-case choices in the report, rather than statistical or production estimates. Every heldout case in those two scenarios is evaluated for both versions.

Independent review found no actionable issues across the contract, runtime, all six fixture bundles, tests, packaging, and qualification scripts. The reviewer separately passed all 28 tests and the independent oracle, plus canonical-order and empty-record mutation probes. Parent integration updated only this case and its root catalogue entry. Root `python3 scripts/check_structure.py` passed in the primary checkout. No live-model, provider, CI, deployment, or production qualification was performed. Status is `demo-ready` for this fixture contract.

## Limitations and references

This fixture-only case measures exact document-ID correctness, not semantic answer quality or real-world safety. Curator records are synthetic local author assertions. Revision numbers indicate synthetic order. Digests identify contents; they are not signatures. Reusing public heldout cases does not provide statistically fresh evaluation. Baseline retention is not a deployed rollback.

Inspired by Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 9, "The Self-Improving agent," printed pp.265-277 / physical PDF pp.296-308. Source architecture, feedback, support case, and safeguards appear respectively at printed pp.265-268 / PDF pp.296-299; pp.269-271 / pp.300-302; pp.272-275 / pp.303-306; and pp.276-277 / pp.307-308. The source does not supply a complete pipeline, trusted-feedback mechanism, numeric evidence floor, stopping bound, or deployment recipe. Its case-study gains are not reproduced here. See the retained [source analysis](../../agent-library-analysis/agents/15-self-improving.md). Implementation is covered by the local [MIT license](LICENSE).
