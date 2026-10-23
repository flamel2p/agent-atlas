# Audio Processing Agent

Slug: 20-audio-processing
Status: demo-ready
Runtime: Python 3.14 (uv CLI, POSIX)

## Purpose and contract

A bounded offline audio-processing lesson. It measures local PCM16 mono 16 kHz WAV and demonstrates timestamped CLEAN/VERBATIM text handling with exact-byte fixture replay. The fixture contains synthetic tones; its transcript is authored simulation. This baseline performs no speech recognition or emotion inference. See [SPEC.md](SPEC.md) and the [implementation plan](PLAN.md).

## Architecture and flow

One local invocation validates input, measures original samples, selects exact packaged replay or unavailable text, and emits one JSON report. There is no provider, network, credential, microphone, persistent state, or report-file output. The public `analyze(wav_bytes, mode=Mode.CLEAN)` operation validates the fixed package resources before analyzing supplied bytes. `analyze_fixture(fixture_id, mode=Mode.CLEAN)` selects one allowlisted package waveform. Neither operation accepts annotations or a manifest path.

The pure core returns immutable `Analysis | Rejected` outcomes. An `Analysis` contains waveform metrics and a `ReplayTranscript | TranscriptUnavailable`. Integer frame intervals own time. Segment seconds and full text are derived when publishing the report. The CLI controls file reads and stdout publication.

## Setup and run

Run from this case directory on POSIX with CPython 3.14.8 and `uv`. Runtime dependencies and credentials are absent. Hatchling 1.32.4 is the pinned build dependency. The offline commands require that interpreter and build backend in the local cache.

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline audio-processing --help
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline audio-processing --fixture complaint --mode clean
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline audio-processing --fixture complaint --mode verbatim
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline audio-processing --fixture silence
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline audio-processing --input src/audio_processing/data/complaint.wav
```

CLEAN returns `my parcel is late. please check its status.`. VERBATIM returns `Um, my parcel is late. Uh, please check its status.`. Both report 48,000 frames, 3.0 seconds, 1,349 zero crossings, and the same source SHA-256. Silence returns measurements with `{"kind":"unavailable","reason":"silent_input"}`. Unfamiliar valid audio returns `no_exact_fixture_match` with measurements.

The complaint waveform contains square tones at 200 Hz and 250 Hz. It contains no recorded speech. Its annotations span frames `[0,24000)` and `[24000,48000)`. Replay is labeled `simulated_fixture_replay` and `synthetic_tones`, with `author_declared_language: en`. An exact whole-WAV digest grants replay. Renaming a file has no effect, while changing one byte or adding container metadata removes replay eligibility.

`analysis` reports contain `sha256`, `metrics`, and `transcript`. Metrics use the original samples with divisor 32,768. `rail_sample_count` counts either PCM16 endpoint and does not prove clipping. `zero_crossing_count` requires adjacent nonzero samples with opposite signs. A zero interrupts adjacency. Replay segments retain `source_index`, `start_frame`, and `end_frame`, with derived seconds. Full text joins the retained segment texts with one space.

CLEAN splits Unicode whitespace and removes a token only when stripping surrounding ASCII punctuation and case-folding produces exactly `um` or `uh`. It preserves other tokens and punctuation, omits empty segments, and retains original indices and intervals. VERBATIM preserves authored segment text exactly. An all-filler CLEAN result remains a valid replay with no segments and empty full text.

The input cap is 1 MiB, with a 30-second frame cap and at most 64 complete WAV chunks. The strict format is RIFF/WAVE, PCM16, mono, 16 kHz. The CLI rejects final-component symlinks, directories, and special files before reading. Parent-directory symlinks are allowed. It validates the opened descriptor and still enforces the byte cap if the file grows.

Package resources also require POSIX filesystem regular files. The asset reader uses nonblocking, no-follow opens and validates the opened descriptor before capped reads. It rejects FIFO, directory, final symlink, missing, and oversized resources. The manifest cap is 64 KiB and each WAV cap is 1 MiB, including if a file grows. Source trees, case copies, and installed wheels are supported package forms. Non-filesystem traversables fail safely without extraction.

Exit 0 means analyzed, including unavailable text, or ordinary `--help` output. Help writes to stdout and succeeds only after flushing it. Exit 2 means invalid arguments, unsafe or unreadable input, or rejected WAV. Argument errors write safe usage to stderr. Other rejections write a JSON `rejected` result without metrics. Invalid packaged resources exit 3. Missing, closed, or broken stdout exits 1 for reports and help without a traceback or ignored shutdown flush error. Help never falls back to stderr. An interruption during the invocation exits 130. Error reports omit paths, raw bytes, and private operating-system details.

To regenerate the committed synthetic resources deliberately, run:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/generate_fixtures.py
```

This maintenance command writes the two WAV assets and manifest. Analysis commands create no report files.

## Source reading guide

- [Package facade](src/audio_processing/__init__.py) exposes fixed-resource operations and converts resource errors into typed rejections.
- [CLI](src/audio_processing/cli.py) owns descriptor validation, bounded reads, safe argument errors, exit codes, cancellation, and output flushing. [Module entry](src/audio_processing/__main__.py) invokes the same CLI.
- [Pure core](src/audio_processing/core.py) defines immutable outcomes, strict RIFF parsing, original-sample arithmetic, digest selection, and frame-preserving text modes. Inspect the zero-adjacency rule and whole-container identity gate.
- [Asset boundary](src/audio_processing/assets.py) acquires capped regular-file resources and validates bounded JSON, identities, safe filenames, frame intervals, and every packaged waveform. [Manifest](src/audio_processing/data/manifest.json) contains only authored simulation metadata.
- [Fixture generator](scripts/generate_fixtures.py) reproduces platform-independent integer square waves and their manifest.
- [Analytical and metadata tests](tests/test_audio.py) check hand-computed metrics, provenance, text semantics, malformed input, and package-integrity failures. [CLI tests](tests/test_cli.py) exercise real subprocesses, descriptor safety, privacy, output failures, and interruption handling.
- [Package acquisition tests](tests/test_assets.py) replace resources only in isolated temporary package copies and check typed rejection, descriptor cleanup, growth limits, and unsupported resource forms.
- [Independent CLI oracle](scripts/verify_cli.py) reconstructs the complaint waveform, checks direct signal arithmetic, and probes input, help-output, and package-resource failures without importing agent internals.

## Verification

Verified on: 2026-10-23
Verification command: `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -q && UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/verify_cli.py --package-dir src/audio_processing`
Verification mode: fixture
Verification result: passed
Verified scope: 61 tests and 80 independent CLI invocations passed in each of the checkout, standalone case copy, and installed wheel on CPython 3.14.8. Coverage includes analytical metrics, replay identity/modes, silence/unknown audio, strict bounds, metadata, privacy, descriptor safety, output failures, resource corruption, and cancellation cleanup.

`uv sync --locked --offline` completed. The complaint CLEAN, complaint VERBATIM, silence, and explicit complaint input-path CLI commands above each exited 0 with the described results. SIGINT coverage raises the real signal inside an instrumented invocation and verifies exit 130. An interrupted read check verifies descriptor cleanup.

The independent oracle constructs expected waveform bytes and measurements separately from the agent. Its package-fault checks clone the package before substituting FIFO, directory, symlink, and missing resources. The installed-wheel run checks the installed package's own bytes. The named console entry point passed, and wheel resources match the checkout exactly. Both source distribution and wheel builds passed. See the [qualification record](VERIFICATION.md) for commands and review results.

Independent review corrected help-output flushing, blocking package-resource opens, and a timing race in the independent checker. Regression checks reproduce the original failures and now pass. Fresh focused reviews found no remaining runtime or checker issues. The checker also passed with deliberate 250 ms parent delays during its three broken-pipe probes. The code-explanation review found no actionable issues. Live-model, hosted-CI, deployment, and production qualification have not run. This demo has no model or runtime network.

## Limitations and references

The [retained brief](../../agent-library-analysis/agents/20-audio-processing.md) records the source gaps in ASR initialization, confidence/language defaults, NORMALIZED handling, diarization, and placeholder sentiment extraction. This case selects a transparent deterministic baseline. General speech recognition, emotional inference, resampling, and acoustic word alignment remain outside its contract.
