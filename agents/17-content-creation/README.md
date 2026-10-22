# Content Creation Agent

Slug: 17-content-creation
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

Compose a synthetic product email and documentation announcement from exact approved facts. A deterministic reviewer drives bounded revisions and keeps failed drafts visibly unapproved. Mechanical validation does not grant human approval. See [SPEC.md](SPEC.md), [PLAN.md](PLAN.md), and [SOURCES.md](SOURCES.md).

## Architecture and flow

The public operation is `create_content(brief: Brief) -> RunResult`. It validates the brief, reads one immutable fixture snapshot, and creates email then documentation. Each artifact begins with required facts, audience-ranked optional facts, and preferred copy. Pure review examines the actual text, block structure, exact evidence spans, brand rules, and word count.

Review feedback selects the next legal content change. Brand repair tries an untried copy alternative or removes an offending optional fact. Length repair removes the lowest-priority optional fact before shortening copy. Required facts and their qualifiers stay intact. Each artifact has at most three reviewed drafts. A passing channel freezes while the other finishes; failed artifacts retain their attempts and have `validated_text: null`.

There is no LLM, runtime network, publishing, media, analytics, credential discovery, or persistent state. The application reads packaged resources and an optional caller-selected brief, and writes only stdout/stderr. Shell redirection remains the caller's choice.

## Source reading guide

1. [cli.py](src/content_creation/cli.py) owns mutually exclusive input options, deterministic JSON serialization, sanitized diagnostics, exit codes, and output-flush failure handling.
2. [domain.py](src/content_creation/domain.py) defines immutable briefs, plans, blocks, evidence, attempts, and reports. Follow `create_content`, `_compose`, `render`, `review`, and `repair` to inspect controller authority, exact provenance, actual feedback, and the three-draft bound.
3. [boundary.py](src/content_creation/boundary.py) owns bounded UTF-8 JSON parsing, duplicate-key rejection, regular-file/no-follow reads, fixed resource names, fixture validation, and the digest of the exact fixture bytes.
4. [content.json](src/content_creation/data/content.json) contains the six synthetic LumenBoard facts, their source IDs, curated copy alternatives, and audience priorities. [Packaged briefs](src/content_creation/data/briefs/) change only inputs.
5. [Domain tests](tests/test_domain.py), [boundary tests](tests/test_boundary.py), and [CLI tests](tests/test_cli.py) cover real adaptations, counterfeit assertions/evidence, malformed inputs, terminal failures, repeat isolation, and stdout errors.
6. [Independent CLI verifier](scripts/verify_cli.py) reads raw fixture JSON and drives the installed command from temporary working directories. It independently checks source spans, fact order, counts, revisions, malformed files, and broken pipes without importing runtime validators.

## Setup and run

Use Python 3.14 and uv on a POSIX environment. The runtime and tests use only the Python standard library. Hatchling 1.32.4 is the pinned build backend. Windows has not been qualified.

From this case directory:

```sh
uv sync --locked
uv run --locked content-creation
uv run --locked content-creation --scenario exhausted
uv run --locked content-creation --brief src/content_creation/data/briefs/launch.json
uv run --locked python -m unittest discover -s tests -v
```

If the default uv cache is unwritable, prefix commands with `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache`. No environment variables or credentials are required by the application.

| Scenario | Expected exit | Email / documentation reviewed drafts | Observed behavior |
| --- | --- | --- | --- |
| `launch` (default) | 0 | 2 / 2 | Rejects `seamless`, then changes the opening and validates. |
| `relaxed` | 0 | 1 / 1 | Preferred drafts pass immediately. |
| `exhausted` | 1 | 3 / 3 | Every opening alternative is banned; both remain unapproved. |
| `length-repair` | 0 | 2 / 2 | A 70-word ceiling removes the lowest-priority optional fact, reducing 71 words to 63. |
| `impossible-length` | 1 | 3 / 3 | Six required facts cannot fit one word; no validated text is released. |
| `mixed` | 1 | 1 / 3 | Email passes once; documentation exhausts its budget. |

`--brief` accepts exactly `audience`, `required_fact_ids`, `forbidden_phrases`, `email_max_words`, and `docs_max_words`; see the packaged launch JSON and [SPEC input contract](SPEC.md#inputs-and-outputs). File input is bounded to 16 KiB. Final-file symlinks, directories, and special files are rejected. Directory aliases such as macOS `/tmp` are allowed. Ordinary space, tab, newline, and carriage return are accepted in forbidden phrases; matching uses Unicode casefolding and whitespace collapse. Phrases that normalize to the same value are rejected.

Reports contain `status`, `approval: "not_granted"`, `fixture_sha256`, and an `artifacts` array in email/documentation order. Each attempt records its text, actual word count, fact evidence, violations, and concrete changes before a further attempt. Evidence offsets are zero-based, end-exclusive Python character positions in that attempt's text. Exit 0 means both artifacts validated, 1 means unapproved content, 2 means invalid input/fixture or output I/O failure, and 130 means interruption.

Python callers import `Brief` and `create_content` from `content_creation`. Supply tuples for `required_fact_ids` and `forbidden_phrases`; nested mutable lists are rejected. API calls receive the same validation and frozen reports as the CLI.

## Verification

Qualification on 2026-10-22 used macOS, CPython 3.14.8, and uv 0.12.23.

```text
Verified on: 2026-10-22
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -q
Verification mode: fixture
Verification result: passed
Verified scope: 44 tests covering actual feedback-driven revisions, exact provenance, independent fact-order validation, strict JSON/API/file boundaries, immutable inputs, bounded attempts, partial success, and CLI output errors.
```

The same 44 tests passed in a copied case at `/tmp/agent17-standalone-20261022/agents/17-content-creation`, installed with `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline`. That directory contains no root runtime or sibling cases. They also passed against the installed wheel from `artifacts/outside`, with an absolute interpreter path and Python's `-I` isolation mode. The imported package path was confirmed inside `artifacts/wheel-env/lib/python3.14/site-packages`.

The independent CLI verifier passed 82 subprocess invocations in each environment, 246 in the final qualification set. It checks all six scenarios, both audiences, required-fact permutations, word boundaries, optional-content order, exact source spans/digest, malformed JSON, final-file symlinks, FIFOs, and buffered/unbuffered broken pipes. Child processes clear `PYTHONPATH` and `PYTHONHOME` and disable user site packages. Rerun it from this case directory:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/verify_cli.py \
  --fixture src/content_creation/data/content.json \
  --brief src/content_creation/data/briefs/launch.json \
  -- "$(pwd)/.venv/bin/content-creation"
```

`UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv build --offline` built the source distribution and a wheel from it. The wheel was installed with `uv pip install --offline --reinstall --python artifacts/wheel-env/bin/python dist/agent17_content_creation-0.1.0-py3-none-any.whl`. Tests and the independent verifier then ran from an unrelated working directory using that installed command. The packaged evidence digest was `aeff42159f7f110e7828c3beffefd1ec0dd7f7b5bb1fc18456551dc10dc7200d` in all three environments.

Independent review found a validation gap where reordered facts could pass despite valid citations. The reviewer now derives required order from the brief and optional order from audience priority. Adversarial reflow and forged-renderer checks cover the fix. Independent recheck passed with no remaining actionable findings. It checked 20,928 valid required-order and optional-subset combinations across both audiences and channels, accepted reversed evidence-record order for those cases, and rejected 20,904 invalid textual reorderings. The reviewer also ran 784 bounded malformed-fixture mutations without an unexpected exception type. Earlier explanation review corrected a resource read bound and per-artifact stopping wording.

The root structure check and whitespace checks passed during integration. An earlier online metadata rebuild could not resolve PyPI in the restricted environment. Cached offline installation, builds, and all subsequent application checks passed. Cold dependency installation with network access remains untested in this session.

Fixture evidence does not establish live-model, hosted-CI, deployment, or production qualification. No provider or external service was invoked.

## Limitations and references

The narrow grammar checks consistency with synthetic approved content. It does not verify real-world truth, tone, persuasion, or legal compliance. The bounded repair heuristic can stop without finding an existing valid combination; it is not an exhaustive solver. Source attribution and current packaging references are in [SOURCES.md](SOURCES.md). The standalone case retains the repository's [MIT license](LICENSE) and copyright notice.
