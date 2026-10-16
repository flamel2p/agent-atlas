# 20 - Audio Processing agents

- **Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 11, "Multi-Modal Perception Agents."
- **Reference ID:** 20 from the official publisher repository inventory. The exact PDF heading is "Audio Processing agents"; speech recognition and voice sentiment are subexamples within it.
- **Page convention:** printed page / 1-based physical PDF page.
- **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose and contract

**Explicitly stated:** Process temporal acoustic signals, preserving information beyond transcript text. The scenario is a recorded customer complaint; separate examples transcribe speech and infer affect from prosody. Inputs are waveforms, optionally a question and transcription mode. Outputs include timestamped transcript segments, full text, language/metadata, and a sentiment result. The text discusses CLEAN versus VERBATIM needs, while NORMALIZED is also declared (pp. 312–320 / PDF 343–351).

**Inference:** Intended users include developers building meeting/customer-service analysis tools. Success requires useful transcription with temporal metadata and an honest separation of speech content from uncertain affect interpretation. **Not specified:** Validated sentiment accuracy, ASR quality targets, supported audio formats, or production privacy/consent procedures.

## Architecture and documented flow

Figure 11.2 shows waveform, spectral features, audio encoder, transcription/speaker/emotion analysis, LLM, and output. Speaker diarization is diagrammed but not implemented in the displayed listings (p. 313 / PDF 344). STFT/mel features and Whisper-style convolution plus transformer processing are described. The ASR backend is injected; it is not fully constructed in the source. Dependencies include NumPy and the chapter's model libraries; Whisper is named without a pinned backend version.

1. Accept waveform and chosen mode; default to CLEAN.
2. Normalize RMS volume, guarding the divisor with a small minimum.
3. Call the backend transcription interface to obtain raw text and segments.
4. For CLEAN, strip selected filler words and collapse whitespace; otherwise retain segment text. NORMALIZED has no distinct normalization branch.
5. Keep nonempty segments; return concatenated text, timestamps, confidence, hardcoded `en`, and mode metadata.
6. In a separate sentiment example, extract prosodic features, normalize pitch/rate, and choose the closest heuristic emotion profile.
7. In the audio-QA example, preprocess prompt plus audio, generate greedily, parse expected answer markers, and fall back to raw answer text if the marker is absent (pp. 314–320 / PDF 345–351).

These are separate illustrative paths, not one complete integrated service. No ongoing memory, bounded retry loop, or human review branch is implemented.

## Implementation evidence and constraints

**Explicitly stated:** The sentiment feature extractor returns fixed placeholders; production would need a trained classifier. The result therefore cannot demonstrate actual emotional inference from supplied sound (pp. 319–320 / PDF 350–351). The discussion introduces continuous VAD dimensions, but code chooses categorical profiles using pitch/rate rather than returning a learned VAD estimate.

**Inference:** Defaults such as confidence 1.0, language `en`, and missing duration/sample-rate validation can misrepresent backend evidence. The audio-QA excerpt expects a compatible processor/model but does not initialize an audio-capable backend; it should not be assumed to work with the preceding LLaVA initializer. The text acknowledges malformed-output parsing needs additional robustness (p. 316 / PDF 347). Noise, overlapping sources, and temporal dependencies motivate the architecture; operational recovery is not specified.

## Proposed minimal learning demo - unexecuted

Use synthetic speech fixtures plus an interchangeable ASR backend and a visibly labeled sentiment simulation. Return transcript evidence separately from heuristic affect labels; do not make claims about a real person's emotions.

- **Normal-path acceptance:** CLEAN removes fixture fillers while VERBATIM preserves them and both retain valid segment times.
- **Failure/limit acceptance:** An empty/silent or unsupported waveform returns a typed unavailable result; no invented transcript, confidence, or emotional conclusion.

**Missing decisions:** Sample rates, resampling, backend/language support, segmentation limits, real prosodic extraction, uncertainty calibration, diarization, timeouts, retention, and error schema.
