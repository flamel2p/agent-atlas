# Agent 19 source notes

## Book facts and selected scope

Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, first edition, March 2026, Chapter 11, printed pp. 308-312, physical PDF pp. 339-343. The retained [Agent 19 brief](../../agent-library-analysis/agents/19-vision-language.md), [inventory](../../agent-library-analysis/agent-inventory.md), and [foundations](../../agent-library-analysis/foundations.md) supply the repository's source analysis.

The source describes visual encoding, an alignment bridge, and LLM reasoning over images and language. Its listing loads LLaVA but supplies no complete image-question inference method. The retained brief proposes synthetic diagrams and uncertainty as an unexecuted learning demo. No book listing, model weights, purchased pages, or extracted text is packaged here.

This implementation independently chooses rectangular pixel components and finite question intents. That decision produces reproducible grounding and explicit abstention while giving up learned visual-language alignment, free-form QA, and general scene understanding. [SPEC.md](SPEC.md) owns the selected behavior, including the narrower rectangular grammar.

## Current decoder and format references

Consulted 2026-10-23. These sources inform decoder integration; the local behavior tests provide execution evidence.

- [Pillow 13.0.0 Image API](https://pillow.readthedocs.io/en/stable/reference/Image.html) documents lazy `Image.open`, explicit `verify` and `load`, and flattened pixel access. The implementation verifies, reopens the same in-memory bytes, loads, and reads `get_flattened_data`. Mode and bit-depth checks prevent implicit sample conversion.
- [Pillow security guidance](https://pillow.readthedocs.io/en/stable/handbook/security.html) informs the explicit input and decompression controls. The case adds small dimension and byte ceilings and treats decompression warnings as failures. These limits do not make a general untrusted-image sandbox.
- [W3C PNG third edition](https://www.w3.org/TR/png-3/) defines chunk framing, CRCs, critical chunk handling, and ordering. The reader adds bounded structural checks for the signature, all CRCs including IEND, first unique IHDR, consecutive IDAT, optional PLTE shape and location, unknown critical chunks, and final zero-length IEND. This closes permissive Pillow behavior observed during independent review. Pillow still owns decoding; the case claims no complete PNG conformance test suite.

Pillow 13.0.0 and hatchling 1.32.4 are pinned in [pyproject.toml](pyproject.toml). Runtime package resolution is recorded in [uv.lock](uv.lock). No official sample code was copied. Case source and PNG artwork are original. Pillow declares the [MIT-CMU license](https://github.com/python-pillow/Pillow/blob/main/LICENSE); its installed wheel also retains the bundled libraries' notices. This case carries the repository [MIT notice](LICENSE).

## Evidence boundaries

Pixel tests and subprocess tests are fixture evidence. A digest binds observations to the original bytes but is not independent truth verification. Deterministic exact-color matching is a rule for the supported diagrams, not a model-confidence estimate. No live model, provider integration, CI execution, deployment, or production qualification is claimed.
