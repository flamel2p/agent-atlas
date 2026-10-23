# Case instructions

Scope: `agents/20-audio-processing/`.

Read root `AGENTS.md`, this file, `SPEC.md`, and README before editing. Keep every runtime resource local. Preserve unrelated work and sibling cases. Follow the root code explanation standard and keep the README reading guide accurate.

This is a deterministic audio-processing baseline. Procedural tones and authored replay text demonstrate temporal evidence handling. They demonstrate neither speech recognition nor emotion inference. Only exact packaged WAV bytes may receive a replay transcript. Never add a provider, microphone, network call, or transcript override without a separately scoped contract change.

Runtime: CPython 3.14.8, POSIX. No runtime dependencies or credentials. Build backend: Hatchling 1.32.4. Local commands, once implementation exists:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -v
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline audio-processing --fixture complaint --mode clean
```

Retain honest evidence limits. Keep status `in-progress` until root integration, documented run-path checks, and independent review complete.
