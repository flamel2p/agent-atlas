# Agent 20 implementation plan

## Selected design

Build the immutable pure-core candidate. Keep fixed package acquisition behind the public `analyze(wav_bytes, mode=Mode.CLEAN)` operation, with a thin CLI for bounded local reads and one JSON report. The core may accept a validated internal fixture set for meaningful tests, but the public operation and CLI cannot select arbitrary annotations.

The named data shape is `Analysis(metrics, transcript: ReplayTranscript | TranscriptUnavailable) | Rejected`. Frozen records and tuples own invocation state. Integer frame spans own time; seconds and full text are derived. This follows Model the Domain. Prove It Works requires direct CLI and installed-resource checks before readiness.

## Design comparison and synthesis

Two independent designs were compared by a third reviewer. The pure-core design scored 14/15; an adapter/controller design scored 13/15. Scores compare designs against provenance, input bounds/effects, interface, testability, and maintainability. They are design judgments, not measured quality.

Selected the pure-core design for its shorter call chain and single fixed backend. Removed public fixture injection and retained the other candidate's explicit unsupported confidence/affect semantics. Rejected the generic transcriber protocol because the shipped demo has one replay backend and no hostile provider boundary. The cross-judge agreed. No contested design remains.

A local macOS `say` probe exited 0 but produced a WAV with zero frames under the sandbox. This failed the real-artifact check. Portable procedural tones avoid an unverified speech-generation dependency. They must remain visibly paired with simulated text, with no claim that words occur in the waveform.

## Throughput checkpoint

- Blocking first steps: governance, source brief, contract, two candidates, and independent design comparison precede implementation.
- Independent workstreams: research and designs used disjoint temporary outputs. One builder owns all runtime and unit checks. Root owns independent CLI qualification and catalogue integration.
- Shared mutable state: the builder uses an exclusive temporary case copy. Root does not edit or test that copy while it is owned. Integration occurs after completion.
- Smallest safe decomposition: keep the coupled WAV/asset/transcript contract with one builder. Review and independent CLI checks begin against the integrated artifact.

## Verifiable units

1. Implement strict PCM/WAV boundaries and analytical signal checks.
2. Add fixed assets, metadata validation, replay provenance, and mode behavior.
3. Add real CLI boundaries, package metadata, local run instructions, and a linked reading guide.
4. Integrate, run documented checks, exercise an independent CLI oracle, verify a standalone case copy and installed wheel.
5. Complete substantive and code-explanation review. Resolve findings and synchronize evidence/status/catalogue.

Deliver reviewed working-tree changes. No commit, PR, deployment, provider delivery, or production claim is requested.

## Implementation record

The builder implemented units 1 through 3 in an exclusive temporary case copy. The core uses frozen dataclasses and tuples. `assets.py` owns bounded metadata and complete-WAV validation. The package facade exposes `analyze` and a fixed-name `analyze_fixture` convenience operation. The latter avoids reading and validating the same package twice for a fixture run. It adds no annotation injection or provider seam.

The CLI validates the opened POSIX input descriptor with `O_NOFOLLOW`, `O_NONBLOCK`, and `fstat` before bounded reads. The asset boundary applies the same descriptor policy locally to fixed package resources, with separate manifest and WAV byte caps. It supports filesystem package paths and rejects other traversables without extraction. It keeps resource diagnostics private and closes its descriptor on rejection or cancellation.

The CLI treats a completed stdout flush as part of success for reports and help. It deliberately handles argparse's successful help exit and preserves its usage exit 2. Help writes directly to stdout so argparse cannot suppress a write failure or fall back to stderr. A failed buffered write redirects its descriptor to `/dev/null` to prevent a second failure during interpreter shutdown from changing exit 1. This creates no file. An absent or closed stdout stream also returns exit 1.

Portable integer square tones generated the selected 48,000-frame complaint and 32,000-frame silence assets. The complaint annotations use the two agreed half-open intervals and text. The generator is retained with an exact-byte regeneration check. No external speech tool was used for the committed assets.

The first 48-test run had one test setup error. A maximum-text check reused a waveform with a different frame count, and the implementation correctly rejected its metadata. The test now supplies matching waveform metadata. That initial suite passed 48 tests. Actual complaint CLEAN, complaint VERBATIM, and silence CLI examples each exited 0. These were fixture results from the builder's editable install before root qualification.

The bounded fix round reproduced buffered help broken-pipe exit 120 with an ignored flush error, unbuffered exit 0, and closed stdout exit 0 with help on stderr. It also reproduced five-second subprocess timeouts for FIFO replacements of each package resource and false success for final symlinks. Thirteen regression tests now cover help output, isolated package-resource faults, read growth, unsupported resource forms, private acquisition failures, and descriptor cleanup. The full documented suite passed 61 tests on CPython 3.14.8. Ordinary help and complaint CLEAN commands each exited 0 after the fix. No real package assets were modified by the fault tests.

Root completed units 4 and 5. The corrected runtime passed 61 tests and 80 independent CLI invocations in each of the checkout, standalone case copy, and installed wheel. Exact installed runtime bytes match the wheel and source. Both source and wheel builds passed, including fixture/resource inclusion.

Fresh review accepted the runtime fixes and found a timing race in the oracle. Root replaced post-spawn reader closure with a pipe whose reader closes before spawn. A final independent review found no issues; normal and deliberately delayed-parent oracle runs each passed 80 invocations. The code-explanation review also passed. All findings are resolved.

Status is `demo-ready` for the selected fixture contract. See the [qualification record](VERIFICATION.md). No sibling cases or root governance changed. No commit, publication, live-model, hosted-CI, deployment, or production result is claimed.
