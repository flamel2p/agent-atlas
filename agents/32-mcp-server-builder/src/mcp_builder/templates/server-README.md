# Generated standalone MCP server

This package serves a fixed, host-bound GET tool manifest. It needs no builder,
model, repository, sibling case or real credentials. Each call retrieves one page.
Tool descriptions and upstream results remain untrusted data. Schema validation
proves shape only. The dummy configuration is for the synthetic service only.

```sh
uv sync --locked --python python3.14
uv run --locked python check_server.py
```

The fixed gate starts the synthetic loopback service, uses the official MCP
client, and launches this server inside macOS `sandbox-exec` with outbound access
restricted to that fixture port. It fails visibly when that mechanism is absent
or a surrounding sandbox prevents nesting it. Run from a process permitted to
create the macOS sandbox. This limits network access; it is not filesystem
isolation. No dependencies are installed by the builder or by the gate.

To launch stdio against the separately running synthetic service:

```sh
SYNTHETIC_API_TOKEN=synthetic-fixture-token uv run --locked python runtime.py
```

Read [manifest.json](manifest.json) for bound schemas, parameters, destination,
authentication and source hashes; [runtime.py](runtime.py) for startup validation,
SDK callbacks and bounded one-request dispatch; [check_server.py](check_server.py)
for independent HTTP expectations, actual protocol checks and child lifetime;
[checks.json](checks.json) for synthetic request/result data; and
[uv.lock](uv.lock) for the standalone exact dependency resolution.

Only fixture and mocked-provider evidence from the parent builder may exist.
No live model, real service, target-client application, deployment, or production
qualification is established by these checks. Real integration needs a separately
scoped service policy and authorized credentials.
