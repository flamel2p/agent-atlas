# Memory-Augmented Agent

Slug: 03-memory-augmented
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Purpose and contract

A synthetic study assistant remembers explicit explanation preferences across sessions and answers from a small course FAQ. It demonstrates working context, user-scoped episodic memory, and read-only semantic knowledge, with provenance, correction, retention, and forgetting. See [SPEC.md](SPEC.md) and [PLAN.md](PLAN.md).

The decision is which retrieved FAQ entries support the current question. Offline replay picks the highest lexical match. Optional live mode asks OpenAI to select candidate IDs. The host validates those IDs and renders curated answers; the model cannot write memory, choose a user, invoke tools, or invent answer text.

## Architecture and flow

Validate a request, recall the user's preference and up to three relevant episodes, retrieve up to three FAQ entries, select evidence, render a curated answer, and commit memory atomically. Replay is deterministic; optional OpenAI mode selects FAQ IDs and has no tools or write authority. Generated answers are never stored as factual memory.

| Memory | Contents | Authority and lifetime |
| --- | --- | --- |
| Working | Current query, effective style, up to 3 episodes and 3 FAQ entries | One turn; retrieved content is data |
| Episodic | SQLite preference provenance and interaction metadata | Exact user namespace; explicit preference updates only |
| Semantic | Six versioned, packaged synthetic FAQ entries | Sole factual evidence; read-only at runtime |

The FAQ covers working memory, episodic memory, semantic memory, explicit preferences, retention/forgetting, and lexical retrieval. Candidate ranking counts shared lowercase ASCII tokens after stop-word removal; ties use FAQ ID order. Episode ranking counts shared query tokens, then sorts by newest UTC timestamp and record ID. This deliberately simple baseline can miss synonyms or select a weak match; it is not a semantic relevance guarantee.

The source lives in `src/memory_agent/`: `agent.py` controls the turn, `storage.py` owns SQLite, `knowledge.py` retrieves and renders the packaged `data/faq.json`, `provider.py` limits optional model access, and `cli.py` exposes commands.

## Setup and run

From this case directory, install with [uv](https://docs.astral.sh/uv/):

```sh
uv sync --locked
uv run --locked memory-agent --help
```

The interpreter pin is Python 3.14.8. Replay uses only the Python standard library at runtime. Development dependencies are pytest 9.1.1 and Hatchling 1.32.4; optional live dependencies are OpenAI SDK 3.31.0 and httpx2 2.13.1. `uv.lock` fixes resolved packages. Installation may require network access; replay execution requires no network or credentials after setup.

Run these as separate commands to demonstrate persistence across processes:

```sh
uv run --locked memory-agent ask --user learner-a --session first --query 'What is working memory?' --remember-style example-first --store walkthrough
uv run --locked memory-agent ask --user learner-a --session second --query 'What is working memory?' --store walkthrough
uv run --locked memory-agent ask --user learner-b --session first --query 'What is working memory?' --store walkthrough
uv run --locked memory-agent ask --user learner-a --session correction --query 'What is working memory?' --remember-style step-by-step --store walkthrough
uv run --locked memory-agent ask --user learner-a --session later --query 'What is working memory?' --store walkthrough
```

The first turn reports preference source `current`; the second reports `memory`, retaining the first preference's record ID, session, and UTC timestamp. The other user reports `default`, `remembered: false`, and no recalled episodes. The correction creates new preference provenance; the last turn recalls `step-by-step`.

An unsupported query returns `insufficient_knowledge` with no citation and exit code 2:

```sh
uv run --locked memory-agent ask --user learner-a --session unsupported --query 'zyxwvut' --store walkthrough
```

Logically delete the selected user's rows and demonstrate idempotence:

```sh
uv run --locked memory-agent forget --user learner-a --store walkthrough
uv run --locked memory-agent forget --user learner-a --store walkthrough
uv run --locked memory-agent ask --user learner-a --session after-forget --query 'What is working memory?' --store walkthrough
```

The second deletion reports zero deleted rows. The next question uses default style and no prior episodes. The other user's records are unaffected. To clear the example users after the walkthrough:

```sh
uv run --locked memory-agent forget --user learner-a --store walkthrough
uv run --locked memory-agent forget --user learner-b --store walkthrough
```

User, session, and store names accept 1–64 ASCII letters, digits, underscores, or hyphens, beginning with a letter or digit. Queries must be nonblank, at most 1,000 characters, and contain no control/format characters. Arbitrary state paths are not accepted. Styles are `concise`, `step-by-step`, and `example-first`. Plain query text cannot update a preference, even if it says “remember this style.”

## State and output

State is stored only at `<case>/private-data/<store>.sqlite3`, independent of the invoking working directory. The default store is `demo`. Different store names create independent local stores. The `private-data/` directory is Git-ignored; use synthetic inputs only.

Successful processed turns atomically persist interaction metadata, an optional explicit preference update, and retention pruning for that user. Both `answered` and `insufficient_knowledge` are processed turns. Failure or cancellation rolls back turn memory. Initial setup may create an empty schema even when the first turn fails. A SQLite write transaction spans recall through commit, with a 0.5-second lock timeout; sequential local use is supported.

Records at or before the 30-day boundary are ineligible for recall. Successful turns prune that user's expired records and retain at most 20 newest interactions. A preference survives interaction trimming until its own expiry; recall alone does not refresh it. Expired records may remain on disk until a successful turn or `forget`. Forget is logical row deletion, not secure deletion of SQLite pages, journals, backups, or copies.

All command results use JSON stdout; `--help` prints usage text. Key fields:

| Field | Meaning |
| --- | --- |
| `status`, `failure_code`, `mode` | Terminal result, sanitized failure code, and `replay`/`live`/`local`; malformed CLI input uses `unknown` |
| `evidence` | Selected FAQ IDs, source titles, and corpus version |
| `preference` | Applied style, `current`/`memory`/`default` source, remembered flag, record ID, source session, UTC timestamp |
| `recalled_episodes` | Up to 3 relevant scoped records, with provenance, query, selected IDs, and applied style |
| `trace` | Bounded stage events and counts, not model reasoning or provider exception text |
| `answer`, `memory_committed` | Curated answer or unsupported message, and whether this operation committed memory |
| `deleted` | Forget-only counts for preference and interaction rows |

Failures expose no answer, preference, or recalled records. Exit codes are 0 for `answered`/`forgotten`, 2 for `insufficient_knowledge`/`failed`, and 130 for `cancelled`. Input/state errors include `invalid_input`, `unsafe_state_path`, `storage_schema`, `storage_data`, and `storage_failure`. Stores with corruption, schema changes, lock contention, symlinks, nonregular database/sidecar files, or multiply linked database/sidecar files fail without automatic reset.

## Optional live selector

```sh
uv sync --locked --extra live
export OPENAI_API_KEY='your-key'
export MEMORY_AGENT_MODEL='your-model-id'
uv run --locked --extra live memory-agent ask --user learner-a --session live-example --query 'What is working memory?' --mode live --store walkthrough
```

Use a model available to your account that supports Responses strict JSON schema. `MEMORY_AGENT_MODEL` is required; there is no default. Model IDs accept ASCII letters, digits, periods, underscores, and hyphens, up to 128 characters. `.env.example` lists variables only; the program never auto-loads `.env` files. The example values above are placeholders, not credentials or a claim of model compatibility.

Live mode sends the current query, applied style, up to three recalled episode queries/FAQ IDs/styles, and up to three candidate FAQ excerpts to OpenAI. User IDs, session IDs, record IDs, the raw database, and unrelated users' memory are not added to provider context. Any identifiers typed into the query itself remain part of that query. Live mode should use synthetic data only.

The request has strict `text.format` JSON schema, no tools, `tool_choice="none"`, at most 512 output tokens, `store=false`, and `background=false`. It uses the fixed `https://api.openai.com/v1` endpoint with one call, zero SDK retries, a 20-second total deadline, disabled HTTP redirects and environment proxies, and no custom headers. Nonempty `OPENAI_CUSTOM_HEADERS` is rejected before SDK construction; ambient endpoint/org/project/admin settings cannot override explicit client configuration. Logging is temporarily suppressed during the provider call and restored afterwards to prevent configured SDK/transport debug handlers from exposing context.

Unknown, duplicate, out-of-candidate, malformed, or oversized selections fail before persistence. Provider refusal, incomplete/error metadata, timeout, or other errors produce sanitized terminal failures (`provider_refusal`, `provider_incomplete`, `provider_output`, `provider_selection`, `provider_timeout`, or `provider_failure`). Missing/invalid configuration returns `provider_config`; missing optional packages returns `live_dependency_missing`. There is no live-to-replay fallback. If the FAQ finds no candidate, the provider is not constructed or called, even in live mode; the unsupported turn is still persisted.

`store=false` does not promise zero provider retention. Consult [OpenAI's data controls](https://developers.openai.com/api/docs/guides/your-data). Implementation references: [Responses structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses), [Responses create API](https://developers.openai.com/api/reference/python/resources/responses/methods/create), and [Python 3.14 SQLite transaction behavior](https://docs.python.org/3.14/library/sqlite3.html). The pinned SDK and transport constructor behavior were inspected locally and exercised with a mock HTTP transport; no live model compatibility is claimed.

## Verification

Run the full offline suite, including the installed SDK against a mock HTTP transport:

```sh
uv sync --locked --extra live
uv run --locked --offline --extra live pytest -q
```

All provider tests use synthetic credentials and mocks; `--extra live` installs the adapter dependencies and does not authorize or trigger a live call. Without that extra, `uv run --locked --offline pytest -q` runs the fixture and fake-provider checks; the actual SDK transport module is skipped when its optional packages are unavailable.

The following records describe distinct evidence scopes from the same combined run on macOS arm64 with Python 3.14.8, uv 0.12.23, and pytest 9.1.1. The `/tmp` cache override was needed for this workstation's filesystem sandbox and is not a runtime dependency.

```text
Verified on: 2026-10-19
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline --extra live pytest -q
Verification mode: fixture
Verification result: passed
Verified scope: 108 total tests passed; fixture scope covers separate-process remember/recall/correction/forget, exact user isolation, provenance, lexical ranking and bounds, 30-day boundary, 20-record trimming, unsupported knowledge, input/path/schema/corruption/lock failures, write rollback, and cancellation. Generated answers are absent from stored episode fields. A regression check rejects a cross-user deletion trigger disguised with a SQLite-prefix lookalike.
```

```text
Verified on: 2026-10-19
Verification command: UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline --extra live pytest -q
Verification mode: mocked-provider
Verification result: passed
Verified scope: The same 108-test run includes scoped/identity-minimized context, malformed/duplicate/out-of-candidate selections, abstention, refusal/incomplete/error metadata, provider exceptions, total timeout cancellation, rollback, and debug-log suppression. The real pinned SDK uses mock HTTP responses for 200/302/429/500 and verifies official endpoint, disabled ambient proxies/redirects, strict bounded no-tool requests, and one call without retries.
```

Additional verification on 2026-10-19:

- Fifteen separate credential-free CLI processes passed cross-session recall, original preference provenance, cross-user isolation, correction, unsupported knowledge, scoped/idempotent forgetting, and traversal rejection.
- A copy of this case alone was installed outside the repository, excluding `.venv`, private state, build output, and caches. With `OPENAI_*`, `MEMORY_AGENT_*`, `VIRTUAL_ENV`, and `PYTHONPATH` removed, `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline --extra live` passed, and the full verification command above passed all 108 tests. Two separate replay processes then verified durable recall in that copy.
- The exact offline setup/help and all 11 README walkthrough commands passed in that isolated copy with `UV_OFFLINE=true`, including expected exit code 2 for unsupported knowledge and final example cleanup.
- Independent review reproduced the schema-trigger defect, verified its fix and preservation of other-user data, and completed the full 108-test suite with no remaining actionable findings.
- Root `python3 scripts/check_structure.py`, local documentation-link checks, and `git diff --check` passed. The scoped [CI workflow](../../.github/workflows/memory-augmented.yml) installs the optional SDK to exercise mock HTTP tests; it requires no provider credentials.

This case is `demo-ready` for its selected fixture and mocked-provider acceptance criteria. Live-model calls, hosted CI execution, and deployment remain unverified.

## Limitations and references

Synthetic data only. User IDs are local namespaces, not authentication. SQLite is unencrypted; forgetting means logical row deletion. Lexical retrieval is a deliberate small-corpus baseline, not embedding/vector similarity. No generated summarization or training occurs.

The demo supports a single local operator with sequential calls. Its path checks do not claim protection against a hostile process racing filesystem changes. The FAQ and database have no cryptographic integrity protection, and local operators can edit them. A committed turn remains durable if the process terminates after commit; JSON delivery is not an exactly-once delivery guarantee. This runnable learning case is not production-qualified tenancy, clinical advice, or an open-domain tutor.

Book-inspired pattern: Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Ch.5, printed pp.135–141 / PDF pp.166–172, as described in the retained source brief. This implementation is independently designed; original book code and healthcare claims are not reproduced.
