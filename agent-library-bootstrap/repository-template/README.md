# AI Agent Demo Library

Independently runnable learning demos with explicit architecture, tool boundaries, execution flow, and validation evidence.

## Catalogue

| Case | Pattern | Status | Runtime | Evidence |
| --- | --- | --- | --- | --- |
| [Tool-Using Agent](agents/tool-using/README.md) | Tool selection and guarded execution | planned | Undecided | Not implemented or run |

## Use a demo

Open its directory and follow its README. Each case owns its dependencies, configuration, fixtures, tests, and artifacts. There is no shared application runtime or global credential configuration.

## Development

Read [repository rules](AGENTS.md), [contribution workflow](CONTRIBUTING.md), and [Codex workflow](docs/CODEX_WORKFLOW.md). Use the [case template](templates/agent/) for additions. Run the common structure check with `python3 scripts/check_structure.py`.

Patterns may be inspired by *30 Agents Every AI Engineer Must Build* by Imran Ahmad, Packt, March 2026. Source facts and implementation choices remain distinct. The collection can grow beyond the book; it does not need to preserve book numbering in directory names.

## Status and license

This initial scaffold contains governance and a planned Tool-Using case. It does not contain a runnable Agent implementation. The implementation language, backend, scenario, license, and copyright owner remain to be selected.
