# Vision-Language Agent specification

Slug: 19-vision-language
Status: demo-ready
Runtime: Python 3.14 (uv CLI, POSIX)

## Objective and source boundary

Demonstrate image-grounded question answering with inspectable observations and host-owned abstention. Input pixels determine object counts and spatial answers. Language chooses a bounded question; it cannot authorize effects or bypass perception checks.

Source facts come from Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 11, printed pp. 308-312, physical PDF pp. 339-343. The retained [source brief](../../agent-library-analysis/agents/19-vision-language.md) describes a visual encoder, alignment bridge, LLM, counting, and spatial questions. The listing loads LLaVA but does not implement image inference. The book supplies no tested uncertainty threshold or complete QA method.

Selected adaptation: deterministic pixel perception and a finite language grammar, rather than model weights or a remote API. This is a restricted visual QA baseline, not a learned VLM, general scene understanding, or reproduction of the incomplete listing. No current model, license, hardware, or provider claim is needed.

## Inputs and visual grammar

One local PNG image and one question per invocation. The image is either a selected packaged original synthetic scene or an explicit regular local file. Do not accept URLs, follow final-component symlinks, read special files, or infer image content from names or metadata. Ancestor directories follow normal filesystem resolution; local paths are user-selected reads, not a sandbox or authentication system.

Read at most 1 MiB. Accept only single-frame, opaque 8-bit RGB PNG, with each dimension from 8 through 256 inclusive. Higher bit depths are rejected before Pillow can reduce their samples to 8-bit values. Verify PNG signature, bounded chunk framing, all CRCs, critical chunk order, terminal zero-length IEND, and dimensions before pixel materialization. Reject duplicate IHDR, nonconsecutive IDAT, malformed or misplaced PLTE, unknown critical chunks, trailing bytes, unsupported modes, animation, bad encoding, oversized input, and invalid paths. These checks plus Pillow decoding are a bounded input policy, not a full PNG conformance validator. Keep decoder decompression warnings as failures. Bound questions to 256 characters and reject control characters.

Supported images have a white background `(255,255,255)` and separated, solid, axis-aligned rectangular objects in red `(255,0,0)`, green `(0,180,0)`, or blue `(0,0,255)`. Each object has width and height at least 3 pixels, lies strictly inside the image boundary, and does not touch another colored object even diagonally. Gray `(128,128,128)` denotes a possible opaque occluder. No color tolerance or resizing applies. All other nonwhite pixels, thin regions, fragments, boundary clipping, object contact, or gray pixels make the scene uncertain. Pixels cannot reveal objects completely hidden by another object; no answer claims a total of hidden objects.

A component is a maximal four-neighbor region of one exact color. At most 64 nonwhite components may be processed. A complete object fills every pixel of its axis-aligned bounding box. Object IDs are deterministic in top-to-bottom, left-to-right order. Bounds use zero-based `[left,top,right,bottom]` coordinates with exclusive right and bottom edges. Evidence contains measured pixel counts, bounding boxes, and original-byte SHA-256 provenance.

## Question and output contract

Normalize case and whitespace and allow one optional terminal question mark, including whitespace immediately before it. Full-match the following grammar, where colors are red, green, or blue and relations are left of, right of, above, or below:

- `How many objects are visible?`
- `How many <color> objects are visible?`
- `Is the <color> object <relation> the <color> object?`

No free-form generation, synonym expansion, OCR, image instructions, or hidden actions. Unsupported questions end explicitly without guessing.

Return one JSON object. The result is a tagged outcome with `status`, `answer`, machine-readable `reason`, input question, parsed intent when available, image provenance, observations, scene issues, rule/evidence references, and a visible-object scope statement. Use `answered` only with an exact integer count or boolean relation. All other outcomes have `answer: null`. Status `uncertain` preserves visible observations and explains a scene or selector ambiguity. Status `unsupported` identifies an unsupported question. Status `invalid` identifies structural input failure without exposing file contents or tracebacks. Do not return numerical confidence.

Counts include all complete objects matching the requested color, or all colors when unfiltered. An empty valid scene answers zero. Any scene issue blocks every exact answer, including apparently unaffected colors. A spatial selector must identify exactly one complete object for each color. Missing or multiple matches yield uncertainty. For a supported scene with unique selectors, left means `subject.right <= reference.left`, right means `reference.right <= subject.left`, above means `subject.bottom <= reference.top`, and below means `reference.bottom <= subject.top`. A false predicate answers false. Same-color singular selectors are uncertain because the objects cannot be distinguished.

CLI exits with 0 for answered, 1 for uncertain or unsupported, 2 for invalid or CLI usage errors, and 3 for an output failure. Operational errors terminate cleanly. No answer is reported as delivered when stdout fails. Keyboard interruption terminates without a misleading answer.

## Architecture, state, tools, and effects

The main interface accepts a path and question and returns a structured result. Typed immutable observations, parsed count/relation intents, and tagged outcomes organize domain state. The image/perception boundary owns bytes, format validation, pixels, rectangular integrity, and scene issues. The question boundary owns the finite grammar. The answer owner applies host gates and relation predicates. The CLI owns argument validation, safe JSON emission, and exit status.

Request state lasts for one invocation. There is no conversation history, learning, database, model proposal, credential, persistent memory, or runtime network. Permitted effects are one bounded image read and stdout/stderr output. Fixture generation is a separate development command with case-local destinations; it is not a runtime tool. No output report files, shell tools, publication, or downstream actions.

## Execution, stopping, and failures

Validate the question, acquire bounded image bytes, decode and inspect the scene once, resolve the question, and stop. No retries or agent loop. Components, input bytes, decoded pixels, and question length have executable ceilings. A byte limit and pixel limit bound work, not a hard wall-clock security sandbox.

Never convert an incomplete scene into a confident count. Preserve issues, observations, and available provenance on uncertain outcomes. Invalid image input never produces an exact answer. Runtime never imports test expectations. Missing dependencies and installation failures remain environment failures rather than successful acceptance.

## Acceptance criteria

1. A packaged scene with three complete colored rectangles returns count 3 with exact pixel evidence and source-byte digest. Color counts and all four relation predicates match independently authored examples.
2. Renaming identical bytes preserves semantic results and digest. Replacing bytes under an unchanged filename changes the observed answer and digest. Runtime never reads truth labels or text metadata.
3. A known gray occluder splitting a rectangle returns uncertainty with no exact answer. Unknown colors, malformed rectangles, clipping, contact, and excess components stop conservatively.
4. Empty valid images answer zero. Missing or duplicate singular selectors and unsupported language end explicitly.
5. Corrupt/truncated PNGs, unsupported modes or animation, oversized bytes/dimensions, symlinks, special files, excessive/control-character questions, and stdout failures terminate as documented.
6. Documented CLI commands, meaningful local tests, an independently authored subprocess verifier, standalone copied-case installation, built-wheel installation outside the source tree, package data/license checks, and independent substantive review pass before demo-ready.
7. Documentation and catalogue distinguish fixture evidence from unverified live-model, CI, deployment, and production behavior.
