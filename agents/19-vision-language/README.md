# Vision-Language Agent

Slug: 19-vision-language
Status: demo-ready
Runtime: Python 3.14 (uv CLI, POSIX)

Agent 19 answers bounded questions about original synthetic PNG diagrams using actual pixels. It counts visible rectangular objects and checks spatial relations, preserving observations when scene uncertainty prevents an exact answer.

The selected implementation is a deterministic perception and language baseline. It uses no LLM, pretrained vision model, network, credentials, or persistent state. The [specification](SPEC.md) defines its narrow visual and question grammar. See the [plan](PLAN.md) for design choices and the [source brief](../../agent-library-analysis/agents/19-vision-language.md) for the incomplete book example.

## Run

Use Python 3.14, uv, and a POSIX system. Pillow 13.0.0 is the only runtime dependency. No credentials or environment file are required.

From this case directory:

```sh
uv sync --locked
uv run --frozen vision-language --scene clear --question 'How many objects are visible?'
uv run --frozen vision-language --scene clear --question 'Is the red object left of the green object?'
uv run --frozen vision-language --scene occluded --question 'How many objects are visible?'
uv run --frozen vision-language --image /absolute/path/to/diagram.png --question 'How many red objects are visible?'
```

The first request returns `status: answered` and `answer: 3`. The relation returns `answer: true`. The occluded scene returns `status: uncertain`, `answer: null`, and a `gray_occluder` issue. Exit code 1 is the expected outcome for uncertainty. Omitting both image options selects `clear`; omitting the question selects `How many objects are visible?`.

| Scene | Observable behavior |
| --- | --- |
| `clear` | Three separate red, green, and blue rectangles. |
| `occluded` | A gray bar splits the red rectangle. Every exact answer is blocked. |
| `repeated` | Two red rectangles and one blue rectangle. Red singular selectors are ambiguous. |
| `empty` | A white image answers count zero. |
| `swapped` | Two rectangles with different colors and geometry from `clear`. |

These are original packaged PNG bytes. Scene names only choose a resource; perception never reads their meaning, fixture-generator geometry, metadata text, or test expectations.

## Input and output reference

Supported questions have these forms. Color is `red`, `green`, or `blue`; relation is `left of`, `right of`, `above`, or `below`.

```text
How many objects are visible?
How many <color> objects are visible?
Is the <color> object <relation> the <color> object?
```

Case and repeated whitespace are normalized. One terminal `?` is optional; whitespace before it is allowed. The entire remaining question must match. Questions are limited to 256 characters; control and format characters are invalid. Other language ends as `unsupported`.

Images must be opaque, single-frame, 8-bit RGB PNGs of 8 through 256 pixels per dimension and at most 1 MiB. No color conversion, resizing, or color tolerance applies. Background is exact white. Complete red `(255,0,0)`, green `(0,180,0)`, and blue `(0,0,255)` rectangles must be at least 3 by 3 pixels, strictly inside the boundary, and separated even diagonally. Gray `(128,128,128)`, unknown colors, thin or nonrectangular regions, clipping, contact, or more than 64 nonwhite components make every exact answer uncertain. A component is a maximal four-neighbor region of one exact color.

The reader rejects final-component symlinks and special files, including FIFOs. Ancestor directories resolve normally. PNG chunk framing, critical ordering, all CRCs including IEND, and dimensions are checked before pixel materialization; Pillow owns image decoding. This bounded policy is not a full PNG conformance validator or a hard wall-clock sandbox.

One JSON object goes to stdout. Its stable fields are:

| Field | Meaning |
| --- | --- |
| `status`, `answer`, `reason` | Tagged outcome, exact integer or boolean only when answered, machine-readable decision reason. Every nonanswer is null. |
| `question`, `intent` | Original question and parsed count or relation intent when available. |
| `image` | SHA-256 of original bytes, byte count, dimensions, PNG format, and mode. Null or partial when acquisition or decoding fails. |
| `observations` | Complete measured rectangles with deterministic `object-N` IDs, colors, pixel counts, and bounding boxes. |
| `scene_issues` | Sorted issue codes that block exact answers globally. |
| `evidence_refs` | Source digest, observation IDs, and host rule references. These are local references, not independent corroboration. |
| `scope` | Visible objects in the supported diagram grammar; no claim about completely hidden objects. |

Bounds are zero-based `[left,top,right,bottom]` with exclusive right and bottom edges. IDs sort by top then left. Left means `subject.right <= reference.left`; right, above, and below use the corresponding bounding edges. False relations answer `false`. Missing, duplicate, and same-color singular selectors return uncertainty. No numerical confidence is fabricated.

| Exit | Outcome |
| --- | --- |
| 0 | An exact answer was written and flushed, or help was delivered. |
| 1 | Uncertain scene or selectors, or unsupported question. |
| 2 | Invalid input or CLI usage. |
| 3 | Stdout delivery failed. A partial write may exist, but success is never reported. |
| 130 | Keyboard interruption. |

Invalid inputs return machine-readable reasons without raw file contents, filesystem paths, or tracebacks. This process has no retry loop, model, network call, credential, history, or persistent runtime output. Installation may download dependencies; image answering does not use the network.

## Check and regenerate

```sh
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python scripts/verify_cli.py
uv run --frozen python scripts/generate_scenes.py
```

The unit tests construct their own pixels and expectations outside runtime. The separately authored subprocess verifier checks the installed command without importing perception or answer helpers. Regeneration is a development command that writes only packaged scenes inside this case; it is not exposed as a runtime tool. Keep all tests, scripts, and fixtures with the case for standalone verification.

## Source reading guide

1. [CLI entry point](src/vision_language/cli.py) owns mutually exclusive image inputs, packaged-resource selection, output delivery, exits, and interruption handling. [Module entry point](src/vision_language/__main__.py) runs the same command.
2. [Domain state](src/vision_language/domain.py) defines immutable scene observations, original-byte provenance, finite intents, tagged outcomes, and the output envelope.
3. [Perception boundary](src/vision_language/perception.py) owns descriptor checks, byte and pixel ceilings, PNG integrity, four-neighbor components, complete rectangles, and global scene issues. Inspect this before trusting exact counts.
4. [Question boundary](src/vision_language/questions.py) owns structural question checks and the full-match language grammar. [Answer policy](src/vision_language/agent.py) owns global abstention, count filters, unique selectors, and spatial predicates.
5. [Behavior tests](tests/test_agent.py) author independent image inputs and expected answers. [CLI verifier](scripts/verify_cli.py) challenges the command through subprocesses. [Artwork generator](scripts/generate_scenes.py) is development-only and never imported by runtime.
6. [Source notes](SOURCES.md) distinguish the book's incomplete VLM example, current decoder documentation, the PNG boundary policy, and this case's selected adaptation.

## Verification

Verified on: 2026-10-23
Verification command: UV_CACHE_DIR=/private/tmp/agent-atlas-uv-cache uv run --frozen --offline python -m unittest discover -s tests -v
Verification mode: fixture
Verification result: passed
Verified scope: 21 local behavior tests covering independent pixel evidence, counts, spatial predicates, provenance, rename and byte replacement, scene uncertainty, component bounds, finite grammar, invalid PNG and filesystem inputs, CLI exits, stream failures, closed descriptors, and interruption.

Environment was macOS arm64, CPython 3.14.8, and Pillow 13.0.0. `uv lock --offline` and `uv sync --frozen --offline` succeeded using the case lock and an existing dependency cache. The default `uv` cache was inaccessible in this restricted session, so actual commands set `UV_CACHE_DIR` as shown. The fixture generator and documented `clear` count command ran successfully. The CLI help command also ran successfully.

Independent CLI qualification also passed on 2026-10-23:

```sh
python3 scripts/verify_cli.py --command /Users/flame/Workspace/Rarticle/Projects/15-Agent-Atlas/agents/19-vision-language/.venv/bin/vision-language
```

The verifier passed 95 independent probes through 97 CLI processes. The same suite passed in a standalone case copy and in an installed-wheel environment. Each environment also passed all 21 behavior tests. These are three runs of the same checks, not 285 distinct acceptance criteria. `/dev/full` was unavailable on macOS and its device probe was skipped in each environment. Closed-pipe and inherited closed stdout/stderr probes passed; unit tests additionally exercised write and flush failures.

The standalone copy contained only this case, excluding its original virtualenv, build output, artifacts, and local audit checklist. Actual copy and wheel commands used `/private/tmp/atlas19-qualification.eelkcA`:

```sh
# Run from the standalone copy directory.
UV_CACHE_DIR=/private/tmp/agent-atlas-uv-cache uv sync --frozen --offline
.venv/bin/python -I -m unittest discover -s tests -v
python3 scripts/verify_cli.py --command /private/tmp/atlas19-qualification.eelkcA/case/.venv/bin/vision-language

# Build from this case directory.
UV_CACHE_DIR=/private/tmp/agent-atlas-uv-cache uv build --offline

# Run wheel checks from outside the source tree.
/private/tmp/atlas19-qualification.eelkcA/wheel-venv/bin/python -I -m unittest discover -s /Users/flame/Workspace/Rarticle/Projects/15-Agent-Atlas/agents/19-vision-language/tests -v
python3 /Users/flame/Workspace/Rarticle/Projects/15-Agent-Atlas/agents/19-vision-language/scripts/verify_cli.py --command /private/tmp/atlas19-qualification.eelkcA/wheel-venv/bin/vision-language
```

The wheel environment used a fresh Python 3.14 virtualenv. Its pinned Pillow dependency was installed with `uv sync --active --frozen --offline --no-install-project` using this case's lockfile, then the application wheel was installed with `uv pip install --offline --no-deps`. Direct offline `uv pip install` dependency resolution first failed because cached resolver metadata was unavailable, so lockfile-based dependency installation was used. No source directory was added to the wheel environment. A `python -I` import confirmed `vision_language` loaded from that environment's `site-packages` with application 0.1.0 and Pillow 13.0.0.

Independent substantive review found a PNG integrity gap in permissive decoding. The host now checks bounded chunk framing, CRCs, critical ordering, and terminal IEND before decoding. Review and regression probes verified the fix. Parent qualification also found and verified fixes for punctuation whitespace and inherited closed output descriptors. Separate comment/explanation review reported no actionable findings. The parent visually inspected the clear and occluded PNGs and confirmed their intended geometry. Root structure and final package inspection are recorded in [the completed plan](PLAN.md).

Live-model, hosted CI, deployment, and production behavior are unverified. This demo selects no live-model backend. Fixture success qualifies only the selected rectangular-diagram contract.

## Limits and attribution

This case follows the vision-question-answering learning objective in Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 11, pp. 308-312. It independently substitutes deterministic perception and a finite grammar for the visual encoder, alignment bridge, and LLM. Fixture success does not validate general VLM behavior or recover completely hidden objects. Two adjacent same-color rectangles whose union is a solid rectangle have no visible seam and are observationally one rectangle. Ordinary photographs, antialiasing, text, other shapes, and perceptually similar colors are outside the grammar.

Case code and generated artwork use the repository's [MIT license](LICENSE), preserving its copyright notice. Pillow is a separately licensed dependency; see [source notes](SOURCES.md).
