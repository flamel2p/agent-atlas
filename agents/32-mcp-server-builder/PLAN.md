# Agent 32 implementation plan

Status: planned. This document sequences future work. [SPEC.md](SPEC.md) owns behavior and authority. No command or API sketch below is implemented.

## Problem and caller experience

An integration developer supplies an OpenAPI contract and describes useful tasks. The output is a portable MCP server with a readable operation mapping and evidence from checks against a synthetic service. The agent's judgment is selecting and describing tools. Host code owns API semantics and executable effects.

Proposed usage, subject to exact packaging commands during implementation:

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

Proposed domain types and signatures, not runnable code:

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

Broader OpenAPI versions, YAML, richer schemas, custom field projections, write tools, OAuth, Streamable HTTP, deployment packaging, source-code ingestion, and automated repair are separate expansions. The output of this plan is not a universal converter or a production integration platform.

## Implementation reconciliation

No runtime implementation exists and no implementation deviations have been accepted. The current task creates planning documentation only. Open gates are dependency compatibility, concrete isolation, and provider selection. A real target service is unnecessary for the synthetic MVP and remains unselected.
