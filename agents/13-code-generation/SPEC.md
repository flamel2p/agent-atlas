# Code-Generation Agent specification

Slug: 13-code-generation
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Problem and scope

A learning demo for developers shows one generated pure shipping-rule function failing fixed host tests, receiving the failures, and repairing the function within a bounded loop. It generates inspectable Python source using a deterministic fixture developer. It is not a general coding assistant, arbitrary Python sandbox, LLM demonstration, repository editor, or deployment tool.

## Evidence and decisions

The retained [source brief](../../agent-library-analysis/agents/13-code-generation.md) describes Chapter 9, printed pp.239-255, PDF pp.270-286. Its test-first narrative, code-first walkthrough, threshold inconsistency, missing test updates/checkpointer, and exhaustion routing are source-analysis observations, not executed findings. This implementation independently selects fixed host tests, explicit exhaustion, run-local state and artifacts, and a narrow interpreter. No LangGraph, Docker, model, or persistent service is required.

Selected rule: `shipping_fee(weight_kg, subtotal_rm)` accepts exact built-in integers, excluding bool, with weight 0..20 and subtotal 0..1000. It returns integer RM: base 8, plus 3 per kg above 2, minus 5 only when subtotal is strictly greater than 100. Thus (2,100)=8, (2,101)=3 and (3,101)=6. These are synthetic rules, not a real courier tariff. Host input validation precedes interpretation. Tests, specification, evaluator and limits are owned by the host and cannot be changed by candidate source.

## Inputs and outputs

CLI accepts a named bundled scenario and an optional attempt cap in 1..3. Default scenario is repair. Mandatory scenarios are repair, exhaustion, policy-rejection and syntax-error. A candidate is bounded Unicode Python source for exactly one unannotated function named `shipping_fee(weight_kg, subtotal_rm)` with no defaults, decorators, variadics, positional-only parameters, keyword-only parameters, type parameters or extra top-level statements.

Allowed statements are assignment to one local name, if/else, and return. Arithmetic expressions contain exact integer constants, parameter/local names, and addition/subtraction/multiplication. Single integer comparisons (`==`, `!=`, `<`, `<=`, `>`, `>=`) occur only as direct `if` conditions. Comparison values cannot be assigned, returned, nested or used in arithmetic. Integer truthiness and chained comparisons are rejected. Parameter reassignment is local to one invocation. `__debug__` cannot be an assignment target. Unary operators are unsupported; a negative intermediate can be formed by subtraction, but a returned fee must be nonnegative. Comments and whitespace are accepted. Docstrings are string expressions and are rejected.

All other syntax is rejected before evaluating any branch, including unreachable forbidden constructs. No calls, attributes, imports, indexing, loops, strings, collections, exceptions, function nesting, assertions, environment, filesystem, network, shell or dynamic execution. The generated function assumes host-validated inputs. Its source is not a standalone input-validating library.

Fixed host oracle contains 20 cases from weights (0,1,2,3,20) and subtotals (0,100,101,1000). Expected values are checked-in literal values with stable test IDs, frozen before any proposal; do not derive expectations from the candidate or a shared shipping implementation. Independent unit tests check hand-calculated values. Reports include mode=fixture, terminal status, attempt count, specification/oracle digests, source digests, each case result or policy/syntax error, prior feedback and selected artifact. Passing means these checks passed, not arbitrary input correctness.

## Architecture and state

Use immutable typed test cases, feedback and attempt results. A single run owns the history and terminal status. `run(scenario, max_attempts, ...)` is the main entry point. A developer receives the fixed spec plus prior feedback and returns source only. It has no artifact writer or mutable oracle. Repair must be selected from observed threshold failures, not attempt number alone. Exhaustion intentionally repeats a wrong candidate. No optional provider integration in this scope.

The interpreter defines the permitted source subset. Parse and reject unknown nodes; evaluate explicitly with no `exec`, `eval`, candidate import or compilation to executable code. Its result is a restricted-language result, not direct CPython execution evidence. A module docstring defines AST as the parser's syntax tree and documents semantic restrictions.

## Tools and authority

The host owns evaluation and artifact writes. The candidate cannot select paths, tests, limits, tool names or output filenames. Write only within this case's `artifacts/<unique-run-id>/`; reject symlinked artifact roots, existing run destinations and escapes. Support installed-wheel runs from a standalone copy of the case without sibling resources. The CLI accepts `--workspace PATH`, defaulting to the current working directory, which must be a physical case workspace with matching SPEC Slug and pyproject project name. Installed wheels write to this explicit/current workspace, never the installed package. Validate workspace markers before creating artifacts; parent-traversal (`..`) components are rejected before normalization, and symlink workspace/root components are refused. This is an ownership check, not authentication against a malicious local operator. No overwrites, publication, Git operation or production merge occurs.

Retain source-contract strings as attempt-N/candidate.txt and structured feedback as attempt-N/feedback.json. Syntax and policy failures retain the complete source. Invalid type, oversized or invalid UTF-8 developer responses consume one invocation and terminate failed with a bounded metadata-only attempt. These have null source digest and source artifact, and no candidate.txt. A developer exception or interruption also has metadata-only feedback when no valid source has been received. Never truncate a proposal and label the prefix as the full source. Each JSON artifact is limited to 262144 bytes. Every proposal invocation counts toward attempt_count; the attempts array contains fully written records, so an artifact failure can leave fewer records than invocations.

Do not make a separate shipping.py or accepted-source copy. The final report is the single success authority: accepted_source is a run-directory-relative path to a passing attempt only for completed; otherwise it is null. Publish report.json by exclusively linking a bounded temporary file after source and feedback files are flushed and synced. The atomic link is the completion point. An interruption after publication must preserve the published status. An interruption before publication ends cancelled and writes cancellation evidence when possible. Temporary-file cleanup errors after publication cannot relabel the run.

If writing/finalizing the report fails, exit failed without claiming publication; retained attempt files and temporary data carry no success authority. Individual completed attempt records survive later failures. report_path is null when publication did not succeed. No crash recovery or concurrent hostile local-filesystem guarantee is claimed.

## Execution and termination

1. Validate CLI inputs and workspace before any proposal or write.
2. Freeze the host specification and oracle; establish a fresh run directory.
3. Request one candidate, apply syntax/policy validation, then check the complete fixed oracle.
4. Record candidate, results and bounded feedback. Stop completed on all-pass and select that attempt source in the final report.
5. Otherwise supply feedback to the developer and repeat until max_attempts, then exhausted. Policy and syntax failures consume attempts. Unexpected developer/host errors end failed. Keyboard interruption ends cancelled when it is possible to report, with completed attempts retained. No fallback success.

Hard bounds: at most 3 proposals; source at most 2048 UTF-8 bytes before parsing; at most 80 AST nodes and depth 12; at most 100 interpreter steps per case; exact integers and intermediate magnitude at most 1,000,000; returned fee 0..100. Node counting includes arguments, operators and name contexts. The module root has depth 1. Each visited statement or expression consumes one interpreter step. The public interpret API accepts a lower step_limit in 1..100 for bounded callers and limit checks; it cannot raise the host limit. Unsupported constants and unbound local reads are rejected or reported as evaluation failures. Apply bounds at all relevant public boundaries, not only argparse. Parse errors and recursion issues must be normalized without leaking arbitrary exception content. These limits are educational controls, not a proof that the Python parser is hardened against hostile inputs.

Exit 0 only for completed. Exit 3 means exhausted, 4 failed, 130 cancelled, and 2 invalid input. Terminal status must agree with the finalized report and accepted_source selection. Input errors occur before proposals or artifact creation. A hard process termination or interruption outside the host run cannot promise a final report.

## Acceptance criteria

- Fixture repair shows threshold failures in attempt 1 and all 20 checks passing in attempt 2, with stable oracle digest and a completed report selecting the successful attempt source.
- Without qualifying feedback the fixture developer cannot jump to repaired code. Exhaustion ends after exactly the selected cap, retains attempts, and has no accepted source in the terminal report.
- Syntax/policy failures consume bounded attempts; imports, calls, loops, decorators, annotations, forbidden dead branches and wrong signatures cannot execute.
- Malformed/oversized/deep source, large integers, intermediate overflow, wrong output type/range, unbound reads, invalid inputs and operation bounds produce honest failure feedback.
- Attempts cannot mutate tests or reuse prior-run local variables; repeated runs are isolated.
- Workspace escape, symlink roots and existing output paths cannot overwrite unrelated data. Artifact I/O failure and cancellation cannot report success.
- Actual CLI normal/failure runs, unit suite, a case-only copy and installed wheel run without sibling resources or credentials. Independent review reconciles behavior and explanations. Root structure check passes.

## Dependencies and open decisions

Python 3.14.8 is locally available. Runtime uses the standard library. Use a case-local pyproject, `.python-version`, uv.lock and pinned Hatchling 1.32.4 build backend; unittest needs no test dependency. Hatchling version and build metadata were checked against https://pypi.org/project/hatchling/1.32.4/ on 2026-10-22. Python AST behavior and parser limits are documented at https://docs.python.org/3.14/library/ast.html. No provider credentials, live API, CI, Docker or deployment evidence is claimed. No material product decision remains open.
