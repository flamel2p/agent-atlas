# Agent 20 qualification record

Date: 2026-10-23
Runtime: CPython 3.14.8 on macOS arm64, POSIX
Mode: fixture, including visibly simulated transcript annotations

## Current runtime checks

| Environment | Unit tests | Independent CLI invocations | Result |
| --- | --- | --- | --- |
| Working checkout | 61 | 80 | passed |
| Standalone case copy | 61 | 80 | passed |
| Installed wheel | 61 | 80 | passed |

Run from the checkout or copied case directory:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv sync --locked --offline
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python -m unittest discover -s tests -q
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --locked --offline python scripts/verify_cli.py --package-dir src/audio_processing
```

The standalone copy was `/var/folders/ng/_t8gp_q11sqfcy3hch1zdj780000gn/T/agent20-qualification-hdu7vdi0/case`. It contains only this case, with a new local environment. Qualification removed `PYTHONPATH`, `OPENAI_API_KEY`, and `ANTHROPIC_API_KEY` from the normal subprocess environment. Fault probes set `PYTHONPATH` only to their deliberately isolated package clones. No sibling case or runtime dependency is needed.

The oracle imports no agent internals. It independently constructs the published integer square waveform, verifies the exact source digest and transcript modes, checks direct sample arithmetic, and probes limits, unsupported WAVs, unsafe input types, unavailable text, help output, and package corruption. Its 80 CLI invocations are separate from the unittest suite's own subprocess checks. All invocation counts are observed script output.

SIGINT tests raise the real signal within an instrumented invocation and verify exit 130. Interrupted-read checks verify owned-descriptor cleanup. They do not establish a deadline for every possible operating-system filesystem failure.

## Build and installed-wheel checks

The following commands were run from the working case directory:

```sh
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv build --offline
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv venv --python 3.14 /var/folders/ng/_t8gp_q11sqfcy3hch1zdj780000gn/T/agent20-qualification-hdu7vdi0/wheel-env
UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv pip install --offline --reinstall --python /var/folders/ng/_t8gp_q11sqfcy3hch1zdj780000gn/T/agent20-qualification-hdu7vdi0/wheel-env/bin/python dist/agent20_audio_processing-0.1.0-py3-none-any.whl
```

Run from the qualification directory outside the repository, with `PYTHONPATH` and the two provider-key variables removed:

```sh
/var/folders/ng/_t8gp_q11sqfcy3hch1zdj780000gn/T/agent20-qualification-hdu7vdi0/wheel-env/bin/python -m unittest discover -s /var/folders/ng/_t8gp_q11sqfcy3hch1zdj780000gn/T/agent20-qualification-hdu7vdi0/case/tests -q
/var/folders/ng/_t8gp_q11sqfcy3hch1zdj780000gn/T/agent20-qualification-hdu7vdi0/wheel-env/bin/python /var/folders/ng/_t8gp_q11sqfcy3hch1zdj780000gn/T/agent20-qualification-hdu7vdi0/case/scripts/verify_cli.py --package-dir /var/folders/ng/_t8gp_q11sqfcy3hch1zdj780000gn/T/agent20-qualification-hdu7vdi0/wheel-env/lib/python3.14/site-packages/audio_processing
```

The loaded package path was inside the wheel environment's `site-packages`. The runtime modules, manifest, and both WAV files matched the built wheel and working checkout byte for byte. The wheel contains no tests, private state, or sibling resources. The source distribution includes the independent oracle. The installed `audio-processing --fixture complaint --mode clean` command also returned the expected report.

## Review and corrections

The initial 48 tests and 63 independent CLI checks passed before substantive review. Review then reproduced two gaps that those checks missed:

- `--help` returned exit 120 or 0 on failed output because argparse bypassed controlled flushing.
- Replacing package resources with FIFOs blocked acquisition. Final symlink resources also bypassed the selected regular-file policy.

Thirteen unit tests and 17 additional oracle invocations cover the corrected boundaries. The expanded oracle failed against the old runtime with an actual closed-help exit 0 before the fix. The fixed runtime returns exit 1 on failed report/help output and exit 3 on invalid resources, with bounded nonblocking acquisition and private diagnostics.

The independent code-explanation review reported no actionable findings. The first substantive review's two findings are resolved in code and regression checks. A fresh focused review verified those runtime fixes and found a scheduling race in the oracle's broken-pipe setup. The oracle now closes the pipe's read end before spawning and closes the parent's write end in `finally`.

A final independent review reported no actionable findings. Both the ordinary oracle and an instrumented run with a 250 ms parent delay after each of its three broken-pipe spawns passed all 80 invocations. The corrected oracle was rerun successfully against the checkout, standalone copy, and installed wheel. There are no unresolved review findings.

Root `python3 scripts/check_structure.py`, `git diff --check`, and local documentation-link and whitespace checks passed. The repository-root command `UV_CACHE_DIR=/tmp/agent-atlas-uv-cache uv run --project agents/20-audio-processing --locked --offline audio-processing --fixture complaint --mode clean` returned the expected report. After documentation closeout, the final distributions were rebuilt and their runtime bytes were confirmed equal to the qualified installed code. The source distribution contains this record and the corrected oracle.

## Evidence limits

All runtime evidence is local fixture evidence. Transcript words and times are authored simulation paired with synthetic tones. They establish no speech-recognition, language-detection, word-alignment, confidence, speaker, sentiment, or emotion accuracy. No live model, hosted CI, deployment, or production qualification ran.
