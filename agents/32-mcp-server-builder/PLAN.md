# Agent 32 implementation plan

Status: demo-ready. The implementation sequence below has local fixture and mocked-provider evidence; independent review and fix verification passed. [SPEC.md](SPEC.md) owns behavior and authority. The reconciliation section records exact implemented commands and choices.

## Problem and caller experience

An integration developer supplies an OpenAPI contract and describes useful tasks. The output is a portable MCP server with a readable operation mapping and evidence from checks against a synthetic service. The agent's judgment is selecting and describing tools. Host code owns API semantics and executable effects.

Implemented CLI (after `uv sync --locked --python python3.14`):

```text
mcp-builder build --spec fixtures/customer-invoices/openapi.json \
  --brief fixtures/customer-invoices/tasks.txt \
  --policy fixtures/customer-invoices/policy.json \
  --fixtures fixtures/customer-invoices/checks.json \
  --planner replay --out artifacts/customer-invoices
```

The developer reviews `tool-plan.json`, `coverage.json`, and `verification.json`, then copies `server/` into an empty directory and follows that package's README. No extra confirmation step is required for reversible generation and fixture checks. Connecting to a real service is a separate execution scope.

Conceptual call sites:

```python
result = build(request, replay_planner)
result = build(request, configured_model_planner)
```

Both paths return the same outcome contract. Replay proves generator behavior. A model run adds evidence about actual tool-selection behavior. A failed model call never falls back to replay.

## Shape and responsibility

Design vocabulary used by the implementation (private representations remain internal):

```text
BuildRequest = input paths + planner mode + new case-local destination
OperationKey = HTTP method + canonical source path
OperationCatalog = supported operations + exclusions + source digest
ServicePolicy = permitted operations + required selections + destination + limits
ToolProposal = selected operation keys + names/descriptions + task coverage
BoundToolPlan = private validated binding of source, policy, and proposal
BuildResult = Verified(bundle, evidence)
            | NeedsInput(gaps) | Rejected(issues) | Failed(stage, code)
            | Timeout(stage) | Cancelled(stage)

build(request: BuildRequest, planner: Planner) -> BuildResult
read_contract(snapshot: InputSnapshot) -> OperationCatalog
propose(catalog: EligibleCatalog, brief: TaskBrief) -> ToolProposal
bind(catalog, policy, proposal) -> BoundToolPlan
emit(plan: BoundToolPlan, staging: FreshDirectory) -> StagedBundle
verify(bundle: StagedBundle, fixtures: FixtureSet) -> VerificationReport
```

Only `build` is public. Its implementation hides source normalization, policy binding, generated packaging, subprocess management, and atomic publication. `SPEC.md` defines the five ownership areas. The generated server owns a copied runtime and manifest; it has no runtime dependency on the builder.

## Synthesis decision

Two independent design candidates converged on a constrained proposal plus deterministic compiler. Both considered a generic OpenAPI gateway with an editable manifest and a free-form coding agent. Independent cross-review favored the first candidate because one build operation keeps orchestration and failure handling inside the case. The second candidate contributes explicit source/policy hash binding, a reviewable plan artifact, and cancellation checks. Review also corrected the distinction between malformed protocol requests and invalid tool arguments. YAML and a mandatory inspect-then-emit checkpoint were rejected as unnecessary scope.

The synthesis strengthens both candidates by making generated-server execution a mandatory gate before publication. Static emission alone cannot return `verified`. Semantic review happens against the emitted plan and held-out task expectations; it does not create a separate permission ritual for local generation.

Applied principles are Boundary Discipline, which keeps source/model validation at the authority boundary; Laziness Protocol, which keeps one public build operation and one runtime language; and Prove It Works, which requires checking the generated subprocess and standalone package.

## Tradeoffs and alternatives

- Accept a narrow OpenAPI 3.1.1 profile to make serialization and rejection behavior explicit. Broader spec support is future work.
- Accept copied runtime code in each output so the generated server stands alone. Template and dependency versions are recorded for later maintenance.
- Accept one proposal with no repair loop to keep failed selection and unsupported requirements visible. A future repair loop cannot edit policy or acceptance checks.
- A generic runtime plus manifest reduces emitted code, but puts more OpenAPI interpretation into every running server. Reconsider it if a stable, broad adapter runtime becomes the objective.
- A free-form coding agent can handle custom integrations, but requires a larger execution sandbox, dependency policy, and independent test authority. It is outside this first demo.
- TypeScript with its official SDK is a viable language alternative. Python keeps builder, verifier, and generated server in one toolchain for this case.

## Implementation sequence

1. **Freeze the fixture and verify feasibility.** Create the synthetic OpenAPI/task/policy/check inputs inside this case. Include three allowed reads, an unrelated read, and a payment write. Fix expected HTTP requests independently of generated mappings. Select exact Python/SDK/dependency pins and a concrete process/network isolation mechanism. Prove a minimal stdio server supports the chosen protocol revision and that the verifier cannot reach a non-fixture destination. Stop and resolve compatibility gaps before building the generator.
2. **Implement the source contract.** Add bounded JSON parsing, operation identity, inherited parameters/security, the exact supported schema profile, serialization rules, and coverage reasons. Verify valid examples and meaningful unsupported cases. No model call or service access is needed for this unit.
3. **Bind proposals and compile a server.** Start with deterministic replay. Validate proposals against host policy and derive all executable mappings. Emit fixed templates, a standalone dependency lock, dummy configuration, and source reading guide. Verify safe serialization, deterministic output, source-hash binding, fresh-directory behavior, and no hidden builder imports.
4. **Verify the actual generated artifact.** Run a real MCP client and local fixture service against the generated subprocess in the selected isolation boundary. Cover discovery, request metadata, tool schema/list/call behavior, exact HTTP encoding, auth, errors, limits, cancellation, and output cleanliness. Publish only verified bytes. A deliberately broken generated artifact must fail the gate.
5. **Add one bounded model adapter.** Select the provider from current documentation and define its data, endpoint, timeout, token/output, and retry contract. Send only allowed normalized catalogue data and the task brief. Add mocked-provider tests for malformed output, forbidden operations, injection attempts, timeout, and no replay fallback. Keep live invocation opt-in.
6. **Qualify and document.** Run case-only installation/generation, then a separate generated-server-only installation outside the repository. Complete independent review, reconcile SPEC/code/checks/README, and record actual evidence per root `CONTRIBUTING.md`. Mark `demo-ready` only for the demonstrated fixture and mocked-provider scope. If a live model is run, evaluate held-out briefs and report that evidence separately.

Each unit ends with its stated observable check. Update this plan with accepted deviations before handing dependent work to another implementer. Do not create a second behavior contract in test fixtures or templates.

## Deferred extensions

The next practical extension is one named existing service with a supported OpenAPI document and an explicitly authorized read-only test account. Confirm the intended MCP client's supported revision first. Report fixture behavior, model selection, actual upstream responses, and client compatibility separately.

Broader OpenAPI versions, YAML, richer schemas, custom field projections, write tools, OAuth, Streamable HTTP, deployment packaging, source-code ingestion, and automated repair are separate expansions. The implemented demo is a narrow fixture-backed converter; no production integration qualification is claimed.

## Implementation reconciliation

Implemented in `src/mcp_builder/`: source parsing, constrained replay/Responses proposals, private binding, fixed emission, mandatory artifact gate and atomic publication. `runtime.py` and `check_server.py` are copied unchanged into the standalone package. `tests/test_contract.py` covers source/policy/proposal rejection, deterministic output, lifecycle and CLI failures, mocked provider success/failures, generated protocol/HTTP/isolation behavior, and deliberately broken generated bytes.

Selected Python is 3.14; exact direct pins and transitive hashes live in `uv.lock` and `templates/server-uv.lock`. The SDK API is v2 callbacks `(ctx, params)` and official `Client` with discovery; actual negotiation selected `2026-07-28`. The verifier supplies bounded pipes to the official Client so server descendants stay in its kill group.

Selected isolation is macOS `sandbox-exec` deny-network plus one allowed loopback fixture port. It is explicitly network isolation, not filesystem isolation. A second listening loopback port is checked for EPERM; nested sandbox restrictions cause a visible failed build. The selected first fixture uses port 19832; a busy port is a failure.

The bounded provider adapter uses fixed `https://api.openai.com/v1/responses`, supported `gpt-6-luna`, `store: false`, strict structured output, 4,096 output tokens, 45 seconds, and zero retries. Tests inject MockTransport without real credentials. The obsolete `gpt-5-mini` candidate was discarded during implementation because its current official model page marks it deprecated. No live-model or real-service call occurred.

Routine operational selections: parsed JSON nesting 64; normalized manifest cap of 64 KiB; upstream identity encoding only; macOS exclusive atomic rename; fixtures input root; one `task_id: description` per brief line; clean CLI handling for closed output and missing planner inputs. None removes a mandatory acceptance gate.

Local independent builder-only and generated-only installations are exercised by `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache .venv/bin/python qualify_isolation.py --offline`; each uses its own lock/venv and actual artifact gate. README records the latest actual run. A real target service remains unselected and unnecessary for the synthetic MVP.

## Review reconciliation

Independent review found an incomplete discovered-schema check, malformed-container exceptions, fixture-root traversal, and ignored path/response references. Parent regression tests reproduced the failures, then fixed the authority boundaries and added independently authored expected tool schemas to the declarative fixture data. Full suite passed 103 tests; a separate reviewer repeated the suite and original probes with no remaining actionable findings. Fresh builder-only and generated-only locked installations passed after the fixes. README owns exact commands, paths, modes, and limits.
