# Audio Processing Agent specification

Slug: 20-audio-processing
Status: demo-ready
Runtime: Python 3.14 (uv CLI, POSIX)

## Problem and scope

Give developers a bounded lesson in temporal acoustic input, source identity, waveform measurements, and transcription-mode handling. The input is a local WAV file or a packaged synthetic fixture. The output is one JSON report. Signal measurements use supplied PCM samples. Transcript text is authored simulation available only for an exact packaged waveform. No speech recognition, emotion inference, speaker diarization, audio QA, resampling, persistent state, microphone, or runtime network exists.

## Evidence and selected decisions

The [retained source brief](../../agent-library-analysis/agents/20-audio-processing.md) records Chapter 11, printed pp. 312–320, PDF pp. 343–351. Its backend is injected, NORMALIZED has no distinct implementation, and sentiment features contain placeholders. The book was not reopened during this build. Source analysis is not runtime evidence.

Selected: CPython 3.14.8, standard-library runtime, fixed uncompressed PCM16 mono 16 kHz RIFF/WAVE, CLEAN and VERBATIM, analytical signal measurements, procedural tone fixtures, and digest-bound simulated transcripts. Original samples remain unchanged. RMS normalization is deliberately omitted because this baseline measures source audio and feeds no ASR. NORMALIZED is unsupported. No confidence, detected language, speaker, sentiment, or emotion is fabricated. Author-declared language may appear only in labeled replay metadata.

These are project decisions, not claims about the source implementation. No material product decision remains open. General ASR would require a new contract and evidence.

## Inputs and outputs

CLI: `audio-processing (--fixture complaint|silence | --input PATH) [--mode clean|verbatim]`. Default mode is clean. Fixture names form a fixed allowlist. Reject conflicting or missing sources, unknown flags, and unknown modes.

Read at most 1 MiB plus one byte. Accept only regular files, reject a final-component symlink and special files without blocking, and inspect the opened descriptor to protect against substitution. Parent-directory symlinks are allowed; this is a local file reader, not a path sandbox. Do not emit paths or raw bytes in error reports.

Require RIFF declared size to equal the entire byte length. Walk at most 64 complete chunks with padding accounted for. Require exactly one `fmt ` and one `data` chunk, a 16-byte PCM format body, format tag 1, one channel, 16,000 Hz, 16 bits, block alignment 2, byte rate 32,000, even data size, and 1–480,000 frames. Bounded unknown chunks are ignored. Reject truncated headers, chunks, padding, duplicate structural chunks, trailing bytes, unsupported formats, and conflicting sizes. No decoder fallback exists.

An analyzed report contains source SHA-256, sample rate, frame count, duration, RMS, peak, DC offset, endpoint sample count, and zero-crossing count. Values use original signed little-endian samples and full-scale divisor 32,768. RMS is `sqrt(sum(x*x)/N)/32768`. Peak is `max(abs(x))/32768`. DC offset is `sum(x)/N/32768`. Endpoints are -32,768 and 32,767; counting them does not prove clipping. A crossing is a pair of adjacent nonzero samples with opposite signs. A zero interrupts adjacency. Exactly all-zero samples mean `silent_input`; quiet nonzero samples remain measurable.

Transcript is a discriminated result: `kind: replay` with `evidence: simulated_fixture_replay`, `source_kind: synthetic_tones`, fixture ID, author-declared language, mode, and timestamped segments; or `kind: unavailable` with `silent_input` or `no_exact_fixture_match`. Full text is derived from retained segments. A replay digest identifies fixture bytes; it does not prove that the waveform contains words. Confidence and affect fields are absent because those capabilities are unsupported.

The packaged manifest is at most 64 KiB, with at most eight unique fixture IDs and digests, at most 128 segments per fixture, and at most 1,000 Unicode characters per segment. Reject duplicate JSON keys, unknown fields, nonfinite values, invalid types, booleans as integer offsets, unsafe filenames, control characters in text, and malformed metadata. Every packaged WAV must match its declared SHA-256 and frame count. Segments use integer frames with `0 <= start < end <= frame_count`, ordered and nonoverlapping. Seconds are derived as frames divided by 16,000. The fixed package owns all annotations; CLI input cannot supply a transcript or manifest.

Package resources must be POSIX filesystem regular files, as exposed by source trees, case copies, and installed wheels. Acquisition uses nonblocking, no-follow opens and inspects the opened descriptor before reading. Reject FIFO, directory, final symlink, missing, or unreadable resources as `invalid_assets`. Read at most the resource cap plus one byte, including after file growth. The manifest cap is 64 KiB and each WAV cap is 1 MiB. Unsupported non-filesystem traversables fail closed without extraction. Resource diagnostics omit paths and private operating-system details.

VERBATIM preserves each authored segment text exactly. CLEAN splits on Unicode whitespace, drops a token when stripping surrounding ASCII punctuation and case-folding yields exactly `um` or `uh`, and joins retained tokens with one space. Other punctuation and words remain unchanged. CLEAN omits segments that become empty but preserves source indices and intervals of retained segments. All-filler output is a valid empty replay. Neither mode performs acoustic cleanup, alignment, translation, or semantic rewriting.

## Architecture, state, and authority

The package facade owns fixed asset operations. A pure core owns WAV parsing, typed immutable outcomes, signal arithmetic, replay selection, and mode rendering. An asset module owns descriptor-based bounded package reads and validates package data. The CLI owns descriptor-based bounded local input reads, argument validation, exit codes, and stdout publication. A single implementation owner keeps these rules coherent; no generic ASR protocol is shipped.

Call flow: CLI acquires bytes, facade validates package assets, core validates and measures audio, core selects silence or exact-byte replay or unavailable, CLI publishes one report. State lives in one invocation. No mutable cache, persistence, user identity, tools, provider calls, retries, or side-effect loop exists. Runtime effects are reading explicitly selected local input and package resources, then writing stdout and diagnostic stderr. Fixtures contain no personal audio.

## Execution and termination

1. Parse one source and one supported mode. Read safely within the hard cap.
2. Load and validate the fixed packaged resources. Corrupt resources fail closed; no measurements-only fallback hides a broken installation.
3. Validate WAV structure and frame bounds. Invalid input produces a typed rejection without invented metrics.
4. Compute source digest and signal metrics once. Exact silence yields unavailable text. Otherwise, exact fixture identity permits replay; unfamiliar audio yields unavailable text with valid metrics.
5. Render the selected text mode and emit one finite JSON result. No run creates a file.

Exit 0 means a valid analyzed report, including a transcript-unavailable report, or ordinary `--help` output. Help writes to stdout and succeeds only after a completed flush. Exit 2 means invalid arguments, unreadable/unsafe/oversized input, or rejected WAV. Exit 3 means invalid packaged assets. Missing, closed, or broken stdout exits 1 for reports and help without a traceback or shutdown flush error. Help never falls back to stderr. Keyboard interruption exits 130. Work is bounded by input bytes, chunks, frames, fixtures, and segments. Cancellation leaves no persistent artifact. Internal defects remain failures rather than fabricated available evidence.

## Acceptance criteria

All selected criteria require fixture evidence, not live-model evidence.

1. Complaint replay in CLEAN removes only documented fillers; VERBATIM preserves authored text. Source identity, signal metrics, order, and retained frame intervals agree across modes.
2. Analytically known samples establish RMS, peak, DC offset, endpoints, duration, and the exact crossing definition.
3. Silence and valid unknown audio retain correct metrics and unavailable text. One-byte mutations and equivalent PCM in a changed WAV container never inherit transcript text.
4. Malformed, empty, oversized, unsupported, duplicate, truncated, or excessive-chunk audio fails within fixed bounds. FIFO, directory, and final symlink reads do not hang.
5. Malformed manifests, mismatched asset digests, invalid intervals, bad types, and duplicate metadata fail closed. FIFO, directory, final symlink, missing, and oversized package resources produce `invalid_assets` without hanging. No arbitrary transcript injection is available through the CLI.
6. Real CLI checks cover success, unavailable, rejection, usage, privacy, cancellation/output handling where reproducible, and no report-file writes. Help succeeds on stdout and rejects closed or broken stdout in buffered and unbuffered modes. A case-only copy and an installed wheel work without sibling files, credentials, or runtime dependencies.
7. Source-reading documentation matches implementation and independent substantive review resolves actionable findings before `demo-ready`.

## Dependencies and references

Runtime uses only the standard library. Hatchling 1.32.4 is a build dependency verified against the [official release](https://pypi.org/project/hatchling/1.32.4/) and available local cache on 23 October 2026. The [Hatch build configuration](https://hatch.pypa.io/latest/config/build/) defines source-package inclusion. The [Python 3.14 wave](https://docs.python.org/3.14/library/wave.html) and [struct](https://docs.python.org/3.14/library/struct.html) docs inform PCM and little-endian semantics. The chosen strict parser accepts less than the general WAV specification. Actual runtime compatibility is established by case checks, not documentation alone.
