# Compliance-Driven Agent specification

Slug: 14-security-and-compliance
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Problem and scope

Engineering reviewers need a reproducible local policy decision with evidence, explicit uncertainty, and advisory remediation. This learning demo assesses restricted synthetic Python snippets for sensitive values entering modeled logging calls. The reactive agent chooses a terminal policy outcome from observed source facts. It uses deterministic rules and no LLM.

The input language uses Python syntax but models annotations and a logger as reserved conventions. It is not arbitrary Python SAST, real logger identity verification, a secret detector, a prompt-injection defense, or regulatory certification. A pass applies only to this local convention and supported subset.

## Evidence and decisions

Source facts come from the [retained brief](../../agent-library-analysis/agents/14-security-and-compliance.md), Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, chapter 9, printed pages 255-265, PDF pages 286-296. The chapter describes policy enforcement, hard and soft findings, remediation proposals, review, versioned policy, and audit records. Its reference-list alias is Security-Hardened Agent. The user selected the chapter compliance scope on 22 October 2026. Preserve this discrepancy.

The brief supplies no complete AST analyzer, immutable log implementation, confidence calibration, universal remediation rule, or version-specific legal policy. The book's reported improvement metric is not independently verified. The original ebook was not reread for this build.

Selected original design decisions:

- One pure abstract interpreter owns syntax, value provenance, per-run bindings, and decision precedence. An abstract interpreter models properties of values without executing their code or retaining their contents.
- One bundled, strictly validated policy owns the version and rule identity. Source cannot replace policy, waive a finding, or grant an exception.
- The CLI reads packaged scenarios or bounded stdin and writes one JSON record to stdout. It creates no files. The caller may retain the report under case-local `artifacts/`.
- No model, provider, OPA service, retrieval layer, automatic remediation, human-identity system, or exception workflow is needed for the selected acceptance criteria.
- Two design candidates and an independent cross-judge selected transactional prefix analysis and immutable origin sets. [PLAN.md](PLAN.md) records the comparison.

## Inputs and outputs

The installed command is `compliance-agent`. Exactly one of `--scenario NAME` and `--stdin` is required. `--list-scenarios` lists packaged examples without scanning. Names and expected outcomes are documented in README. Stdin contains UTF-8 bytes for one complete snippet. The CLI reads at most 16,385 bytes to detect the 16,384-byte bound. It never imports or executes the snippet.

The supported source grammar is exact:

1. A module contains at most 64 top-level straight-line statements. Empty or comment-only input passes with zero analyzed log calls, meaning no local-rule findings.
2. A labeled declaration is `name: Sensitive = "text"` or `name: Unclassified = "text"`. The target is one simple name and the value is a string literal. These annotations are synthetic labels, not imported runtime types. Ordinary names and literal contents never imply classification.
3. A regular assignment has exactly one simple name target and a supported expression. Reassignment changes only that binding. Existing aliases keep their prior immutable properties.
4. A logging statement calls exactly `logger.debug`, `info`, `warning`, `error`, or `critical`, with 1-8 positional supported expressions and no keywords or starred arguments. The receiver `logger` is reserved modeled syntax. Each formatting argument is assessed independently.
5. Expressions are string literals, loaded names, `+` of supported expressions, and f-strings with supported substitutions, no conversion and no format specification. An unbound name yields an uncertain value at that reference location.
6. `logger`, `Sensitive`, and `Unclassified` cannot be assignment targets. Imports, function/class definitions, branches, loops, mutation beyond simple rebinding, subscripts, containers, numeric literals, ordinary calls, sanitizers, arbitrary attributes, destructuring, `%`, `print`, f-string conversions/specifications, and template strings are unsupported. Comments cannot waive rules.

The report includes schema/analyzer version, status, policy ID/version/rule/SHA-256, source SHA-256 when a complete bounded snapshot is available, coverage counts, ordered findings, and fixed remediation guidance. Each finding includes a closed reason code, kind, rule ID, sink or unsupported location, and ordered sensitive/uncertain origin spans where applicable. Spans use 1-based lines and 0-based UTF-8 byte columns, including end positions. Reports contain no source text, literals, identifiers, filenames, raw exceptions, source-derived patch text, or timestamps. Identical input and policy produce identical records.

For an oversized input, do not label the digest of a prefix as the source digest. Emit a null digest and an explicit incomplete-input indicator. A fully read malformed input may retain its exact byte digest. Operational failures produce a fixed JSON error and no policy success record.

The report fields are `source_sha256` and `input_complete`. Coverage reports `complete`, `statements_total`, `statements_analyzed`, and `log_calls_analyzed`. Label origins span their declaration's string literal. Unbound-name origins span the reference. A sink spans its complete logging call. Unsupported syntax spans the first rejected node. Unparsed source has a null total statement count and no location. Failed records contain only the report schema version, failed status, and a fixed error code/message.

JSON emission requires writable stdout. Output write or flush failure exits 3 without a retry or traceback. An absent process stdout also exits 3. Interpreter failures before the CLI starts are outside this application's error boundary.

| Status | Exit | Meaning |
| --- | --- | --- |
| `passed` | 0 | Supported scan completed without violation or uncertain logging. |
| `blocked` | 1 | At least one supported logging call contains a marked sensitive origin. |
| `review_required` | 2 | No definite violation, but uncertain logging, unsupported syntax, or a source-analysis limit prevents a pass. |
| `failed` | 3 | Invalid CLI usage, policy corruption, input read failure, or other supported operational failure. |
| `failed` | 130 | Interrupted scan. No partial policy success report. |

## Architecture and state

`assessor.py` owns immutable spans, values, findings, coverage, bounded AST evaluation, and derived status. Each abstract value contains independent sets of sensitive and uncertain origin spans. String literals have neither. Copies retain both. Concatenation and f-strings union both, so sensitivity is not lost when mixed with uncertainty.

Each supported logging call yields at most one sensitive violation and one uncertainty review item. The main status is derived from findings: blocked takes precedence over review_required, which takes precedence over passed. Complete syntax coverage can still require review because a logged value is unclassified.

`cli.py` owns bounded input reads, packaged resource loading, strict policy decoding, report serialization, and exit behavior. A small separate policy module is permitted only if it reduces duplicated boundary logic. `__main__.py` delegates to the CLI. Core API `assess(source_bytes, policy)` performs no I/O. Exact local symbol names may be chosen by the builder without changing this contract.

All state is invocation-local. There is no persistent memory or audit database. SHA-256 ties a record to exact input/policy bytes for comparison. It does not authenticate records or make retained files immutable.

## Tools and authority

The only runtime reads are the selected bundled scenario, bundled policy, or stdin. The sole output is JSON to stdout. No subprocess, network, filesystem mutation, `eval`, `exec`, source import, patch application, or runtime provider is permitted.

The bundled policy JSON has exactly `schema_version`, `policy_id`, `version`, `rule_id`, and `scope`. Selected values are schema 1, `local-sensitive-log`, `1.0.0`, `LSL001`, and the exact scope `Synthetic straight-line Python snippets with labeled values and modeled logger calls.` Reject duplicate keys, missing/extra fields, wrong types including booleans as schema integers, unsupported identifiers/versions, and altered scope. Hash the exact validated bytes. The maximum policy size is 4,096 bytes. Policy semantics cannot be changed by report text or input annotations. Changes to actual rule semantics require coordinated policy version, SPEC, code, and tests.

A finding recommends removing sensitive values from logs or replacing the whole argument with a fixed public event message. It never certifies a function named `mask`, hashing, truncation, or a comment as safe declassification. Review is a terminal escalation for a human to inspect externally; no simulated approval clears findings.

## Execution and termination

1. Validate CLI selection and bundled policy. Read one bounded input snapshot.
2. Check source size and UTF-8 decoding. Parse once with `ast.parse`. Suppress parser warnings locally so source-derived diagnostics cannot escape to stderr or alter the outcome under caller warning filters. Before interpretation, iteratively enforce at most 512 AST nodes and maximum depth 32, counting the Module as depth 1 and including operator/context nodes. Enforce at most 64 top-level statements.
3. Evaluate supported statements in source order. A statement commits bindings and findings only after its entire syntax is supported. At the first unsupported statement, record an incomplete-review finding and stop. Do not analyze its suffix using uncertain state. Keep findings from earlier committed statements.
4. Derive status, attach evidence provenance, and serialize one report. A known violation followed by unsupported syntax remains blocked with incomplete coverage.

Source size, encoding, syntax, AST/depth/statement limits, and parser recursion errors yield review_required with zero interpreted statements and fixed reason codes. An unsupported statement after a supported prefix retains that prefix's findings. Resource bounds constrain ordinary synthetic inputs; this process is not a hostile-input sandbox or a hard parser memory/time isolation boundary. No retries, external calls, or open-ended loops exist.

## Acceptance criteria

All selected criteria require fixture/local CLI evidence:

1. Direct, aliased, concatenated, and f-string sensitive logging blocks with correct rule and source/sink spans. Mixed sensitive and uncertain logging preserves both findings.
2. Supported public logs pass. Labeled or unresolved uncertain logged values require review. Reassignment clears only the current binding; earlier aliases remain sensitive.
3. Unsupported prefix, reserved-name rebinding, fake masking, imports, and control flow never pass. Unsupported statements commit no partial findings. A prior violation remains blocked with incomplete coverage.
4. No submitted code executes and source bytes remain unchanged. Canary literals, identifiers, and raw syntax errors never appear in successful or failed output.
5. Byte/node/depth/statement/argument limits are exercised at meaningful boundaries. Invalid UTF-8/syntax and Python 3.14 template strings have explicit non-pass outcomes.
6. Missing/extra/duplicate/wrong-type/unsupported policy fields and oversized policy fail closed. Policy and input digests match independent hashing; oversized input has no misleading full-source digest.
7. Repeated and separate invocations are deterministic and isolated. Actual CLI status and exit behavior match the contract, including malformed invocation and read failures.
8. Case-only installation and an installed wheel run without repository or sibling resources. Policy and scenarios are packaged. Independent review has no unresolved material findings before demo-ready.

## Dependencies and open decisions

Use Python 3.14 with standard-library runtime and unittest checks. Keep build metadata, lockfile, fixtures, tests, and scripts local to the case. Pin the selected build backend and document the actual tool/runtime versions used. No credential configuration is required. There are no unresolved material behavior decisions.

Primary documentation checked on 22 October 2026: [Python 3.14 AST](https://docs.python.org/3.14/library/ast.html), [Python execution model](https://docs.python.org/3.14/reference/executionmodel.html), and [PyPA project metadata](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/). AST parsing does not establish scoping or execution correctness; the explicit interpreter enforces this case's subset.
