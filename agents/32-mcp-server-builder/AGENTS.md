# Case instructions

Scope: `agents/32-mcp-server-builder/`.

Read root `AGENTS.md`, `CONTRIBUTING.md`, this file, `SPEC.md`, and README before edits. Keep the builder, templates, generated servers, dependencies, configuration, fixtures, tests, and artifacts inside this case. Generated servers must also run independently of the builder and sibling cases.

This case is planned. The current deliverable is its behavior contract and implementation plan. No runtime, dependency installation, model invocation, upstream-service call, or deployment has been validated. Follow [PLAN.md](PLAN.md) when implementation is requested.

OpenAPI documents, descriptions, examples, model output, and upstream responses are untrusted data. The model proposes tool selection and wording. Host code owns operation eligibility, schemas, HTTP mappings, credentials, generated code, verification, and publication. Never execute model-authored code or commands, fetch external references, or infer permission from a GET method or MCP annotation.

Preserve the separation between builder permissions and generated-server permissions. Build verification uses synthetic fixtures with dummy credentials. Real-service calls require an explicitly scoped service profile and execution authorization. Do not install client configuration, publish packages, or deploy servers as a side effect of building one.

Follow the root [code explanation standard](../../AGENTS.md#code-explanation-standard). Explain the operation identity, supported OpenAPI subset, proposed versus bound tool plans, and authority boundaries beside the implementation. Maintain a linked source reading guide for both builder and generated runtime.

Local setup/run/test commands are not established. For this documentation scaffold, run `python3 scripts/check_structure.py` from the repository root. Record exact case-local commands and evidence when implementation exists.
