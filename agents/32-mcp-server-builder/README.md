# MCP Server Builder Agent

Slug: 32-mcp-server-builder
Status: demo-ready
Runtime: Python 3.14 (uv CLI)
Library ID: 32

Build a standalone stdio MCP server from a narrow OpenAPI 3.1.1 JSON profile, required task brief, explicit read-only policy and synthetic fixtures. A constrained proposer chooses up to three operation identities and tool descriptions. Host code derives schemas/HTTP mappings, emits fixed code, runs the actual generated subprocess, then atomically publishes only verified bytes.

The supplied scenario finds customers, lists one page of their invoices, and inspects an invoice. An unrelated GET and payment write remain unavailable. The generated server needs no builder, model or repository installation. [SPEC.md](SPEC.md) owns the contract; [PLAN.md](PLAN.md) records architecture and implementation decisions.

## Run

```sh
cd agents/32-mcp-server-builder
uv sync --locked --python python3.14
uv run --locked pytest -q
uv run --locked mcp-builder build --planner replay --out artifacts/customer-invoices-new
```

Use a fresh output name each time. Existing outputs are refused. The verified bundle contains `server/` with its own dependency manifest/lock, runtime, manifest, fixed fixture gate and README; plus `tool-plan.json`, `coverage.json` and `verification.json`. A nonverified result publishes nothing and removes only its private staging directory.

The full gate requires macOS `sandbox-exec` from a process permitted to create a sandbox. The agent runtime has a temporary cwd, explicit environment, bounded pipes and outbound network access restricted to fixture port 19832. A second live loopback listener must be denied with EPERM. This is network isolation; it does not restrict filesystem reads. Nested sandbox creation denied by an outer automation sandbox is a visible verification failure. Run that check with the environment's permitted outer execution. Other operating systems and a busy fixture port fail visibly.

Replay requires no credentials. One optional provider adapter implements an explicit `--planner provider` request to OpenAI Responses using `gpt-6-luna`, `store: false`, strict structured output, one attempt and bounded output/deadline. Its key is read only after that flag is selected. Mocked-provider tests use dummy keys and no network. No live invocation is part of the documented fixture run.

The selected schema/profile restrictions, operation permissions, traversal rejection, identity-only response encoding, request/response limits, error codes, and cleanup behavior are defined in [SPEC.md](SPEC.md). The builder does not deploy, publish packages, install client configuration, or call a real upstream service.

## Source reading guide

1. [builder.py](src/mcp_builder/builder.py): public `BuildRequest`/`build`, input snapshots, deadlines, terminal outcomes, no-replace publication and CLI boundaries.
2. [openapi.py](src/mcp_builder/openapi.py): canonical `METHOD path` identity, bounded local references, supported schemas, inherited parameters/security and per-operation coverage.
3. [design.py](src/mcp_builder/design.py): replay and the one-call Responses contract; every proposal remains untrusted.
4. [compiler.py](src/mcp_builder/compiler.py): private bound plan, task accounting, source/proposal hashes and fixed package emission.
5. [runtime.py](src/mcp_builder/runtime.py): copied standalone entry point, manifest revalidation, SDK callbacks, four-call bound, one fixed-destination GET, safe encoding and sanitized errors.
6. [verification.py](src/mcp_builder/verification.py) and [check_server.py](src/mcp_builder/check_server.py): fixed command gate, bounded pipe/process-group ownership, official Client discovery, raw protocol negatives, independently authored tool-schema and HTTP expectations, and OS egress proof.
7. [tests/test_contract.py](tests/test_contract.py): contract, injection, provider, deterministic generation, timeout/cancellation, publication, CLI and broken-artifact checks.
8. [qualify_isolation.py](qualify_isolation.py): separate case-only and generated-only locked installations; [server README template](src/mcp_builder/templates/server-README.md) documents the standalone reading/run path.

The synthetic [OpenAPI](fixtures/customer-invoices/openapi.json), [policy](fixtures/customer-invoices/policy.json), [task brief](fixtures/customer-invoices/tasks.txt), [replayed proposal](fixtures/customer-invoices/proposal.json), and independent [schema/HTTP expectations](fixtures/customer-invoices/checks.json) are local data. They cannot supply commands or executable tests. Task associations prove structural coverage; their semantic correctness needs review.

## Verification evidence

Implementation verification is local. Independent review and fix verification passed for the fixture and mocked-provider scope. Dependency setup used Python3.14.8 and exact locks. Commands containing `sandbox-exec` ran with permission to create the OS sandbox; normal restricted execution failed visibly during that feasibility check.

Verified on: 2026-10-23
Verification command: `.venv/bin/python -m pytest -q --tb=short`
Verification mode: fixture
Verification result: passed
Verified scope: source/policy/proposal validation; actual emitted MCP subprocess discovery at 2026-07-28; metadata/list/call/error/cancellation behavior; exact HTTP/auth/encoding and no retry/body leakage; OS fixture-port restriction; generated-artifact gate and publication/cleanup; deterministic source; CLI failure behavior. Latest complete run: **103 passed** (macOS, Python3.14.8).

Verified on: 2026-10-23
Verification command: `.venv/bin/python -m pytest -q --tb=short`
Verification mode: mocked-provider
Verification result: passed
Verified scope: one fixed Responses request with supported model/store:false and dummy key; constrained output binding; mocked success passes the real generated-artifact gate; invalid JSON/schema/forbidden operation/injected command/timeout/overflow/redirect/refusal/incomplete output fails without retry, replay fallback or publication. Semantic live-model selection remains unverified.

Independent-install command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache .venv/bin/python qualify_isolation.py --offline`. This copies only this case to `/tmp`, installs its own lock/venv, generates a bundle, then copies only `server/` to a second directory, installs that package's lock/venv, and reruns actual protocol/mock-service/isolation checks. The cache is for explicit setup; the build performs no dependency installation. Latest run passed both installations at `/tmp/agent32-independent-s8oz1sag/builder-only` and `/tmp/agent32-independent-s8oz1sag/generated-only`; each generated protocol gate passed with 21 expected fixture calls. Exact commands/results are retained in `/tmp/agent32-independent-s8oz1sag/qualification.json`.

Live-model evaluation, real-service/target-client integration, hosted CI, deployment and production qualification: **not run**. Fixture success does not establish semantic planning quality or real service compatibility.

Independent review found four defects: advertised schemas were not compared with expected schemas, malformed containers could escape terminal handling, normalized input traversal could leave the fixture root, and unsupported path/response references were ignored. Regression checks reproduced these failures before the fixes. The gate now compares both discovered schemas with independent authored fixture expectations; all boundary cases reject. An independent fix-review run passed 103 tests and confirmed the original corrupted artifact cannot publish or retain staging. Separate locked installations were rerun after the fixes; no live-model or real-service evidence was added.
