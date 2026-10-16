# 19 - Vision-Language agents

- **Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 11, "Multi-Modal Perception Agents."
- **Reference ID:** 19 from the official publisher repository inventory. The PDF heading is plural, "Vision-Language agents"; the ID is an external inventory mapping, not a number printed beside this heading.
- **Page convention:** printed page / 1-based physical PDF page. All locators below use this convention.
- **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose and contract

**Explicitly stated:** Combine raw images and natural-language questions so answers are grounded in visual content rather than a lossy textual description. The practical example is a `VisionQuestionAnsweringAgent`. Inputs are an image and question; the architectural output can include text, tool calls, or action plans. Intended users of the example are builders of visual QA systems; counting, spatial relationships, and scene interpretation illustrate tasks ("Vision-Language agents," pp. 308–310 / PDF 339–341; Figure 11.1, p. 309 / PDF 340).

**Inference:** Success means an answer supported by the supplied image, with ambiguous evidence handled explicitly. **Not specified:** An evaluation dataset, numerical accuracy target, abstention threshold, or downstream action authorization contract.

## Architecture and documented flow

The source separates visual encoder, alignment mechanism, and LLM. Image patches become visual tokens; a projection/MLP/Q-Former-like bridge makes embeddings usable by the language model. Adapter integration, cross-attention, and early fusion are alternatives, not all implemented together. The example names Hugging Face `transformers`, PyTorch, Pillow, and LLaVA 1.5 (`llava-hf/llava-1.5-7b-hf`). Chapter requirements specify Python 3.10+ and recommend a CUDA GPU with at least 16 GB VRAM (pp. 307–312 / PDF 338–343).

1. Receive image and question; processor preprocesses image and tokenizes text.
2. Encode image and align its representation with language tokens.
3. LLM jointly reasons over text and visual evidence, then generates an answer.
4. In the production discussion, optionally cross-check claims against a dedicated vision model before propagation.
5. Return output. **Not specified:** A complete QA method, retry/stop loop, or explicit human review branch for this particular listing.

The initializer creates `conversation_history`, but its update, retrieval, and persistence are not shown. Embedding caching is a deployment proposal in the text, not implemented memory (pp. 310–312 / PDF 341–343).

## Implementation evidence and limits

**Explicitly stated:** The model-loading code is illustrative and requires external weights/access and computational resources. It loads processor and model with float16 and automatic device mapping (pp. 310–311 / PDF 341–342). It does not show image inference. The subsequent `answer_question` methods appear inside the audio section and take audio arrays; they cannot be treated as a verified image-QA implementation (pp. 314–316 / PDF 345–347).

Latency, token growth with high-resolution images, distribution shifts, and confident visual errors are discussed. Resolution scaling, pruning, speculative decoding, caching, and deterministic validation are suggested mitigations. These are book-era suggestions, not currently verified technology recommendations. No exception handling or loading-failure recovery is supplied.

## Proposed minimal learning demo - unexecuted

Use a tiny set of original synthetic diagrams with known object counts and spatial relations. An image/question adapter returns structured answer, supporting observation, and uncertainty; a deterministic fixture checker evaluates claims. No consequential actions.

- **Normal-path acceptance:** A fixture with three distinct shapes returns the expected count and identifies the relevant image observation.
- **Failure/limit acceptance:** An intentionally occluded fixture produces uncertainty or a visible validation mismatch, rather than silently publishing a confident count.

**Missing decisions:** Current model/license and hardware choice; image-size policy; output schema; evaluation/abstention thresholds; backend timeout; malformed-output handling; persistent history policy; and whether independent validation is mandatory.
