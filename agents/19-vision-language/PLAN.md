# Agent 19 implementation plan

## Selected design

Build a CPU-only PNG-question demo with real pixel consumption, typed observations, finite question intents, host-owned uncertainty gates, and stdout JSON. A gray occluder or unsupported region blocks all exact answers. There is no persistent state or runtime network.

Two independent design candidates compared pixel segmentation against local pretrained models, remote APIs, and proposal-plus-verifier designs. Both recommended a deterministic baseline for reproducible local acceptance. The selected candidate restricts visual objects to complete colored rectangles. The other candidate's shape classifier would require raster-shape tolerances and more ambiguity rules. Bounding boxes, measured pixels, source-byte digests, and tagged null-answer uncertainty are retained from both designs.

The independent cross-judge scored the rectangle design higher on uncertainty, interface size, and independent verification, but recommended multiple shapes for closer source alignment. Parent synthesis selects rectangles because the retained brief is an unexecuted proposal, while SPEC owns the implemented scope. Three differently colored rectangles satisfy the selected count/evidence criterion. Multiple geometric categories would expand the visual grammar without changing the grounding or abstention lesson. No heuristic shape classifier is grafted into the exact-component design.

| Choice | Pixel grounding | Uncertainty | Local cost | Interface | Decision |
| --- | --- | --- | --- | --- | --- |
| Exact rectangular components | Actual pixels | Global abstention for scene issues | Pillow and CPU | Image + finite question | Selected |
| Multiple shape classifier | Actual pixels | More partial-shape ambiguity | Pillow and CPU | More selectors and raster rules | Deferred |
| Pretrained local or remote VLM | Learned inference | Requires independent evaluation | Weights/hardware or provider | Free-form questions | Separate future scope |

The Model the Domain principle selects immutable scene observations, count/relation intents, and tagged outcomes. The Prove It Works principle requires a subprocess verifier and standalone/wheel runs. Separate Before Serializing Shared State assigns implementation to one builder and review qualification to a separate file owner.

## Units and evidence

1. Contract and design. Read root governance, inventory, foundations, and Agent 19 brief. Record supported pixels, questions, state, effects, bounds, failures, and selected adaptation.
2. Implementation. One builder owns the case runtime, packaging, fixtures, tests, source explanations, and run documentation. Keep test truth outside runtime. Parent owns root catalogue and final readiness.
3. Independent qualification. A qualifier writes a standalone CLI verifier without importing implementation helpers. A separate reviewer inspects behavior, authority, independently constructed images, and failure cases.
4. Closeout. Run local tests and verifier, isolated copied-case and installed-wheel checks, inspect generated fixtures, resolve review findings, run root structure/diff checks, then synchronize readiness and actual evidence.

## Throughput checkpoint

- Blocking first steps. Contract and design selection finish before code.
- Independent workstreams. Grounding and designs run independently; implementation has one owner; review starts after the runtime is stable.
- Shared mutable state. No concurrent edits to the same files. Builder owns implementation, tests, and docs until handoff. A separate qualifier owns only its verification script. The substantive reviewer is read-only. Parent integrates root and final docs after builder handoff.
- Smallest safe decomposition. One builder keeps coupled visual grammar, decoder, question parsing, tests, and documentation consistent. A separate reviewer challenges those assumptions.

## Implementation evidence

The domain-first module map is implemented. Immutable observations, count and relation intents, and tagged outcomes live in `domain.py`. Perception owns bytes and pixel knowledge, questions owns the finite grammar, answer policy owns exact-answer gates, and the CLI owns delivery and exits. Packaged original PNGs are selected by name but interpreted only through bytes. Test truth lives outside runtime.

Offline locking and sync succeeded with CPython 3.14.8 and Pillow 13.0.0. The documented clear-scene count returned 3 with measured bounding boxes and source digest. Twenty-one independently authored local tests pass as of 2026-10-23. See the README verification record for the exact command and limits.

Local tests and independent review exposed permissive decoder behavior around PNG end-chunk integrity and critical framing. A bounded chunk check now validates CRCs and critical ordering before Pillow decoding. The exact-color contract also rejects 16-bit RGB so Pillow cannot silently reduce nearby samples to supported 8-bit values. These are input-policy checks, not a replacement PNG decoder or a complete conformance guarantee.

## Completed qualification

On 2026-10-23, all 21 local tests and 95 independently authored CLI probes passed in the working checkout, standalone case copy, and installed wheel. Each verifier run used 97 CLI processes. The `/dev/full` device probe was skipped because that device is unavailable on macOS; closed-output and injected write/flush failure checks passed. See [the exact commands and scope](README.md#verification).

Parent and independent qualification found and verified punctuation-whitespace and inherited closed descriptor fixes. The parent confirmed installed-wheel imports came from the fresh wheel environment's site-packages and visually inspected the clear and occluded PNGs. A separate comment/explanation review found no actionable issues. Substantive code, authority, isolation, contract, and documentation review found no unresolved findings.

Final integration passed on 2026-10-23. `python3 scripts/check_structure.py` and `git diff --check` passed at the repository root. Additional whitespace checks covered every new case text file. Wheel inspection confirmed all runtime modules, five PNG resources, the MIT license, and ready-status metadata. Source archive inspection confirmed local code, tests, scripts, docs, lockfile, runtime selector, and license, with no local virtualenv or audit artifacts. Byte comparisons confirmed the installed-wheel runtime and images match the final source. Regenerating all five scenes in the standalone copy produced identical original PNG bytes.

All selected acceptance criteria have evidence. No live model, hosted CI, deployment, general vision accuracy, or production qualification is claimed.
