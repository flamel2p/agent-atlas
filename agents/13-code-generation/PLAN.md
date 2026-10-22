# Agent 13 implementation plan

## Outcome

Build a standalone Code-Generation Agent that proposes one pure shipping function, checks fixed host-owned tests, uses actual failure feedback to repair the source, and ends explicitly on success or exhaustion. User authorization is the request to plan and build Agent 13. No publication or deployment is included.

## Design comparison and synthesis

| Candidate | Choice | Tradeoff |
| --- | --- | --- |
| A, typed expression tree with host Python emitter | Rejected as the base | Removes Python parser complexity but adds a separate proposal language and emitter, reducing direct source-generation fidelity. |
| B, restricted Python source interpreter | Selected | Accepts actual source proposals and checks their permitted semantics with host-owned code. Parser and interpreter limits must be explicit. |
| Subprocess or Docker execution | Deferred | A subprocess does not establish filesystem or network isolation. Docker access and hardening were not verified for this task. |

B is the base because the learner inspects the same function source before and after repair. Adopt A's checked-in literal expectations, feedback-directed repair rather than attempt-number replay, and explicit separation of interpreted behavior from CPython execution evidence. The custom interpreter supports only the SPEC subset. No broad Python compatibility or security sandbox claim is permitted.

Model the Domain determines immutable TestCase, TestResult, Feedback, Attempt and RunResult structures with explicit terminal statuses. Separate Before Serializing Shared State determines a single builder in an independent checkout, followed by parent integration and read-only independent review. Prove It Works determines CLI, copied-case and installed-wheel checks beyond unit tests.

The independent design judge also selected B. Its publication-order finding is resolved by using the final report as the only success authority and referring to the retained attempt source. There is no separate accepted file to survive a report-write failure. The CLI takes `--workspace`, defaults to the current case, and verifies case markers before writing. Packaging is retained to make installed-artifact isolation reproducible; direct standard-library execution can also be documented.

## Caller view and module ownership

The user runs `uv run code-generation-agent --scenario repair` from the case directory. The host produces a report and attempt artifacts beneath this case. `--scenario exhaustion` ends nonzero with retained failure evidence. Input details and source grammar are in SPEC.

- `domain.py` owns immutable shipping rules, fixed literal oracle and result records.
- `interpreter.py` owns source validation, permitted AST semantics and operation/numeric limits.
- `developer.py` owns deterministic fixture proposals and failure-driven repair.
- `runner.py` owns the bounded loop, stable evidence and terminal statuses.
- `artifacts.py` owns workspace validation and exclusive local writes.
- `cli.py` owns argument parsing, structured reporting and exit codes.

A small local equivalent layout is acceptable if ownership remains clear. The main API returns a typed terminal result from one bounded run. Neither a proposal nor its feedback can choose or mutate test expectations, limits or artifact paths.

## Throughput checkpoint

- Blocking first steps. Ground repository/source constraints, compare both designs, and freeze SPEC before implementation.
- Independent workstreams. Design proposals use separate files. One builder owns the case. Parent updates the catalogue only after integration. Independent review follows the completed diff.
- Shared mutable state. Build in an isolated checkout under `/tmp`; integrate the single owned case after the builder finishes. No sibling imports or shared application runtime.
- Smallest safe decomposition. Keep interpreter, oracle, feedback loop and artifacts with one builder because their correctness depends on one authority contract. Run independent review and verification as separate read-only work.

## Implementation and verification sequence

1. Define immutable domain values, literal boundary oracle and source language; add meaningful semantic checks.
2. Implement the bounded interpreter and feedback-driven developer, then the runner and artifact boundary.
3. Package the CLI with case-local metadata/lockfile and document source reading order, commands and limitations.
4. Run unit checks and all documented CLI scenarios. Inspect failure feedback and successful source directly.
5. Validate a copy containing only the case and an installed wheel without sibling files or credentials.
6. Obtain independent substantive review, reconcile findings, then update README/SPEC/catalogue status and run the repository structure check.

## Completion record

The case implementation now follows the six planned module boundaries. Model the Domain shaped immutable test, feedback, attempt and terminal records. Prove It Works shaped the unit, CLI and artifact-readback checks. Runtime dependencies remain empty. Hatchling 1.32.4 builds the package and includes the four source fixtures.

Accepted contract clarifications from parent review are reflected in SPEC and tests.

- Comparisons occur only as direct `if` conditions. Arithmetic, assignments and returns require integers. Chained/nested comparisons, comparison arithmetic and integer truthiness are rejected. Assignment to `__debug__` is rejected because parsing alone does not enforce that Python reserved-name restriction.
- Every developer invocation consumes an attempt. A source-contract violation ends failed with bounded metadata and null source fields. Valid source strings retain candidate.txt even when syntax or policy fails. An oversized response is never truncated and mislabeled as the original candidate.
- Exclusive atomic report linking is the completion point. An interruption immediately after the link preserves the published status. Pre-publication cancellation retains attempt evidence and publishes cancellation when possible. Tests exercise both sides of that boundary.
- The interpreter's public `step_limit` may lower the 100-step maximum for a caller and for observable fuel-exhaustion checks. It cannot raise the host maximum.
- The generated source assumes host-validated domain inputs. It is not an independently input-validating library.

Final qualification on 2026-10-22 passed 33 tests in the working case, a case-only copy and the installed wheel. The independently written verifier checked all 21,021 valid input combinations against a literal fee table and exercised 15 controlled rejections. Eleven additional installed CLI invocations checked normal, failure, cap and invalid-input behavior, persisted reports and source/feedback provenance. The source directory was moved out of the import path before installed checks. Exact commands and evidence scope are in README.

Independent substantive review identified one path-normalization defect. The final implementation rejects every `..` workspace component before normalization. Two regression tests fail against the old implementation and pass on the fix. A fresh independent reviewer also reproduced the CLI rejection and confirmed no artifacts appeared in either candidate destination. The explanation review corrected one artifact method docstring to identify the `None` sentinel accurately. No actionable findings remain.

README, SPEC and the selected root catalogue entry now record `demo-ready` for fixture/local package evidence. The root structure and whitespace checks pass. There is no runtime dependency on a sibling case. No commit, publication or deployment was requested or performed. Live-model, Docker, hosted-CI and deployment behavior remains unverified; no follow-up is required for the selected fixture scope.
