# Compliance-Driven Agent

Slug: 14-security-and-compliance
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

Assess a restricted synthetic Python snippet against a versioned sensitive-logging policy. The command reports `passed`, `blocked`, or `review_required`, with source locations and fixed remediation guidance. It never executes the snippet or applies a fix. [SPEC.md](SPEC.md) defines the supported grammar and behavior. [PLAN.md](PLAN.md) records the design choice.

This case follows the book chapter's Compliance-Driven pattern. Its reference-list alias is Security-Hardened Agent. The selected implementation is a deterministic reactive policy agent with no LLM, provider, credentials, or runtime network dependency.

## Install and run

Run these commands from this case directory. Python 3.14 and uv must be available. Initial installation may download the Python runtime and the pinned Hatchling build backend. Runtime dependencies use only the standard library.

```sh
uv sync --locked --python 3.14
uv run --locked compliance-agent --list-scenarios
uv run --locked compliance-agent --scenario clean
uv run --locked compliance-agent --scenario blocked
```

`clean` returns exit 0. `blocked` deliberately returns exit 1 with a violation. The command writes one JSON record to stdout. Review outcomes return exit 2, operational failures return exit 3, and interruptions return exit 130.

To assess a snippet through stdin, use shell redirection or a pipe. The application reads a bounded byte snapshot and does not open a caller-supplied path.

```sh
printf 'token: Sensitive = "synthetic-token"\nlogger.info(token)\n' | uv run --locked compliance-agent --stdin
```

The example returns `blocked`. Replace the logged argument with a fixed public string to obtain `passed`. A function named `mask` does not grant an exception and produces an unsupported-syntax review.

In a restricted development environment, set `UV_CACHE_DIR=/tmp/agent14-uv-cache` before uv commands. This changes uv's build cache, not the demo's runtime behavior.

## Packaged scenarios

| Name | Expected outcome | Demonstrated behavior |
| --- | --- | --- |
| `clean` | passed, exit 0 | Public literals and supported logs. |
| `blocked` | blocked, exit 1 | Direct sensitive logging. |
| `alias` | blocked, exit 1 | Aliasing, concatenation, and f-strings retain sensitivity. |
| `ambiguous` | review_required, exit 2 | Labeled uncertainty and an unbound name. |
| `mixed` | blocked, exit 1 | One value retains sensitive and uncertain origins. |
| `reassigned` | blocked, exit 1 | Rebinding clears the current name but not an older alias. |
| `unsupported` | review_required, exit 2 | An import stops analysis before subsequent logs. |
| `masking` | review_required, exit 2 | An ordinary function cannot certify declassification. |
| `prior-block` | blocked, exit 1 | An earlier violation survives a later unsupported statement. |
| `syntax-error` | review_required, exit 2 | Invalid syntax receives a fixed reason without source excerpts. |

## Interpret the report

`Sensitive` and `Unclassified` are synthetic annotation conventions. The `logger` receiver models five logging methods. Ordinary identifiers and literal contents never infer sensitivity, and the analyzer does not resolve real Python runtime objects.

Each value carries independent immutable sets of sensitive and uncertain source origins. Assignments copy those sets. Concatenation and f-strings union them. Reassigning a name replaces only that binding. Origins point to a labeled declaration's string literal or an unbound-name reference, using 1-based lines and 0-based UTF-8 byte columns.

A logging call produces at most one sensitive finding and one uncertainty finding. The analyzer validates the entire statement before committing either. The first unsupported statement stops interpretation, preserves earlier findings, and leaves the suffix unexamined. `blocked` takes precedence over `review_required`. Complete syntax coverage can still require review when a logged value is uncertain.

The report contains the rule identity, policy digest, source digest, coverage counts, and ordered findings. `input_complete` is false and `source_sha256` is null for oversized inputs. Other preflight rejections interpret zero statements. A digest compares exact bytes; it does not authenticate the report or make saved files immutable.

Reports omit source text, identifiers, literals, filenames, timestamps, and raw exceptions. Parser warnings are suppressed locally. The CLI creates no application files. If stdout is unavailable or fails, the command exits 3 without retrying emission or printing a traceback. Python startup failures before the CLI runs remain outside that boundary.

## Source reading guide

1. [cli.py](src/compliance_agent/cli.py) owns command selection, allowlisted resource reads, bounded stdin, fixed operational errors, JSON output, and process exit codes.
2. [policy.py](src/compliance_agent/policy.py) validates exact policy fields and types, rejects duplicate keys, and hashes the validated bytes. [policy.json](src/compliance_agent/resources/policy.json) supplies the bundled identity.
3. [assessor.py](src/compliance_agent/assessor.py) defines spans, immutable provenance values, findings, derived status, AST limits, expression interpretation, and statement commits.
4. [__main__.py](src/compliance_agent/__main__.py) delegates `python -m compliance_agent` to the same CLI.
5. [test_assessor.py](tests/test_assessor.py), [test_policy.py](tests/test_policy.py), and [test_cli.py](tests/test_cli.py) check semantic behavior, policy integrity, real process outcomes, and injected operational failures.
6. [verify_cli.py](scripts/verify_cli.py) independently checks the installed public CLI against 33 stdin examples, repeated runs, byte provenance, warning filters, ten scenarios, and invalid invocations. It runs the executable from a temporary directory without repository imports.
7. [Packaged scenarios](src/compliance_agent/resources/scenarios/) contain synthetic source text with `.py.txt` extensions. The application reads them as data.

## Verification

```sh
uv run --locked python -m unittest discover -s tests -v
```

The 42 checks cover sensitive and uncertain propagation, alias lifetime, exact spans, transactional stopping, no source execution, source-free output, deterministic runs, all ten scenarios, policy tampering, and exact resource boundaries. Actual subprocess checks cover CLI exits, closed stdin, SIGINT, and broken stdout. Parser-warning checks run with default, always, and error warning filters. POSIX descriptor and signal checks skip on other platforms.

Verified on: 2026-10-22
Verification command: UV_CACHE_DIR=/tmp/agent14-uv-cache uv run --locked --offline python -m unittest discover -s tests -v
Verification mode: fixture
Verification result: passed
Verified scope: All 42 semantic, policy, resource-boundary, and CLI checks passed on the integrated case and again in a case-only copy. No tests were skipped on macOS arm64 with CPython 3.14.8, uv 0.12.23, and Hatchling 1.32.4.

Verified on: 2026-10-22
Verification command: UV_CACHE_DIR=/tmp/agent14-uv-cache uv run --locked --offline python scripts/verify_cli.py --cli .venv/bin/compliance-agent
Verification mode: fixture
Verification result: passed
Verified scope: 86 real CLI invocations passed across 33 independent stdin examples and ten packaged scenarios, with deterministic replays, exact source digests, output redaction, no source execution, and failure exits.

Standalone qualification copied only this case to `/var/folders/ng/_t8gp_q11sqfcy3hch1zdj780000gn/T/agent14-qualification-__25fg1i/case`, excluding environments and generated artifacts. The check cleared `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV`, and provider credential variables. The following commands passed in that copy with `UV_CACHE_DIR=/tmp/agent14-uv-cache`:

```sh
uv sync --locked --offline --python 3.14
uv run --locked --offline python -m unittest discover -s tests -v
uv build --no-sources --offline --out-dir artifacts/dist
```

The build produced a source distribution and built the wheel from it. A fresh environment installed only that wheel with `uv pip install --offline`. Import inspection confirmed the installed module came from that environment's `site-packages`. The independent CLI checker then passed all 86 invocations outside the copied case. ZIP inspection confirmed the exact policy bytes, all ten scenario resources, and the unchanged MIT notice were present. These are local package checks, not deployment evidence.

The initial build-backend download required authorized network access after a DNS failure in the restricted environment. Subsequent integration and standalone checks ran offline. The demo itself has no runtime network calls.

Independent correctness and explanation reviews found no actionable issues. The correctness reviewer independently reran all 42 tests and additional CLI probes. The explanation reviewer checked the contract, source attribution, authority comments, reading guide, and documentation links. Final `python3 scripts/check_structure.py` and whitespace checks passed at repository root.

No mocked-provider, live-model, hosted-CI, deployment, regulatory, or general Python security qualification is claimed.

## Limits and references

The supported input has at most 16,384 bytes, 64 top-level statements, 512 AST nodes, depth 32, and eight positional arguments per log call. These bounds constrain ordinary synthetic examples. They are not a hostile-input sandbox or hard parser memory/time isolation.

The demo provides no regulatory certification, general Python SAST, secret detection, or prompt-injection defense. It does not prove actual logging behavior, recognize sanitizers, persist an audit database, or provide an approval workflow. A human must inspect a review outcome outside this demo. A pass establishes only that the supported subset has no local-rule findings.

Source: Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, chapter 9, printed pages 255-265. See the [retained source brief](../../agent-library-analysis/agents/14-security-and-compliance.md), [foundations](../../agent-library-analysis/foundations.md), and primary documentation links in [SPEC.md](SPEC.md). No external source code is copied. The original ebook was not reread for this build. The case preserves the repository [MIT license](LICENSE).
