# MCP Server Builder Agent

Slug: 32-mcp-server-builder
Status: planned
Runtime: Python (uv CLI; planned)
Library ID: 32

## Purpose and contract

Build a reviewable, standalone MCP server for an existing REST service from its OpenAPI specification and a description of desired tasks. The agent proposes useful tool selections and wording. Host code validates the plan, derives HTTP mappings, generates a fixed server implementation, and verifies the generated artifact.

The selected first demo covers a synthetic customer-and-invoice service with up to three explicitly allowed GET operations. The generated server uses stdio and needs no model to run. It includes its own dependencies, setup instructions, mapping/coverage reports, and verification evidence. See [SPEC.md](SPEC.md) for the behavior contract and [PLAN.md](PLAN.md) for architecture, tradeoffs, and implementation steps.

## Architecture and flow

Planned flow: validate OpenAPI/tasks/policy → obtain one tool proposal → bind it to supported operations → generate a staged standalone server → run MCP client and mock-service checks → publish the verified bundle.

The model cannot invent endpoints, write executable code, grant permissions, select dependencies, or alter tests. Unsupported API behavior and uncovered tasks produce explicit outcomes. Failed checks, timeout, or cancellation prevent publication. There is no automatic repair, retry, deployment, or client configuration change.

The first input profile is deliberately restricted to OpenAPI 3.1.1 JSON, scalar path/query parameters, bounded JSON schemas, same-document schema references, and no auth or one HTTP bearer scheme. Remote references, write tools, OAuth, and remote transport are deferred. Full details and limits are in [the supported profile](SPEC.md#deliberate-openapi-profile).

## Source reading guide

No source implementation exists yet. Review these documents in order:

1. [SPEC.md](SPEC.md) defines input/output contracts, supported semantics, authority, stopping rules, and acceptance criteria.
2. [PLAN.md](PLAN.md) explains the proposed public interface, module ownership, alternatives, and sequence of verifiable implementation units.
3. [AGENTS.md](AGENTS.md) records case-local development boundaries.

When implementation exists, replace this planning guide with links to the actual entry point, OpenAPI parser, proposal boundary, compiler/templates, and verification code. Include a separate source reading guide inside every generated server package.

## Setup and run

No runnable implementation, package manifest, lockfile, or provider configuration exists. Commands in [PLAN.md](PLAN.md#problem-and-caller-experience) are proposed interfaces, not working instructions. No credentials are required to review this plan.

The next implementation step is a synthetic fixture plus an official-SDK and process/network-isolation feasibility check. Exact dependency pins and the optional model provider must be selected before their paths are implemented. A real service is not required to build the first fixture demo.

## Verification

Runtime behavior has not been implemented or run. Fixture generation, mocked-provider behavior, generated-server interoperability/isolation, live-model selection, real-service integration, hosted CI, and deployment are all unverified.

Documentation verification on 2026-10-21, local macOS: `python3 scripts/check_structure.py` and `git diff --check` from the repository root passed. A scoped Python check passed all 54 local Markdown targets/anchors across the root README and four case documents, and checked whitespace in the new files. These are documentation checks only; they do not establish runtime readiness.

Independent planning review found no actionable contract, authority, isolation, or evidence-reporting issues. Dependency compatibility, concrete process/network isolation, and provider selection remain implementation gates.

## Limitations and references

#32 is an Agent Atlas extension. The retained book inventory and supplemental integration pattern keep their identities. The [Code Generation brief](../../agent-library-analysis/agents/13-code-generation.md) provides conceptual background, not an MCP implementation contract.

The design targets [MCP 2026-07-28](https://modelcontextprotocol.io/docs/2026-07-28/learn/versioning), including [server discovery](https://modelcontextprotocol.io/specification/2026-07-28/server/discover) and current [tool behavior](https://modelcontextprotocol.io/specification/2026-07-28/server/tools). Official sources were inspected on 2026-10-21. The narrower [OpenAPI 3.1.1](https://spec.openapis.org/oas/v3.1.1.html) profile is a design choice; it is not the latest published OpenAPI version. Recheck compatibility when pinning dependencies.

Read-only policy does not follow automatically from GET or tool annotations. A real service can violate its documented behavior. Fixture checks establish only the behavior actually exercised, and schema validity does not establish model understanding or business safety.
