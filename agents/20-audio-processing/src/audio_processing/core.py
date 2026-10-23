"""Measure original PCM and render digest-bound, authored text without I/O.

The host supplies validated immutable fixture metadata to this internal core.
A SHA-256 match establishes whole-file identity, not speech content. Integer
frame intervals own segment time. The discriminated outcomes keep unavailable
text separate from rejected audio and from explicitly simulated replay.
"""

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import math
import string
import struct
from typing import Literal

SAMPLE_RATE = 16_000
MAX_INPUT_BYTES = 1_048_576
MAX_FRAMES = 480_000
MAX_CHUNKS = 64
FULL_SCALE = 32_768


class Mode(StrEnum):
    CLEAN = "clean"
    VERBATIM = "verbatim"


class WaveError(ValueError):
    """A fixed, non-private WAV validation diagnostic."""


@dataclass(frozen=True, slots=True)
class Pcm:
    """Validated PCM bytes from one input. Samples retain their source values."""

    samples: bytes
    frame_count: int


@dataclass(frozen=True, slots=True)
class SourceSegment:
    """A package-authored half-open frame span, before text mode rendering."""

    start_frame: int
    end_frame: int
    text: str


@dataclass(frozen=True, slots=True)
class Fixture:
    """Validated replay metadata. Digest and frame count bind it to one WAV."""

    fixture_id: str
    sha256: str
    frame_count: int
    author_declared_language: str
    segments: tuple[SourceSegment, ...]


@dataclass(frozen=True, slots=True)
class Metrics:
    """Source signal values divided by 32768, without normalization or gain.

    A rail sample equals either PCM16 endpoint. It does not establish clipping.
    A zero crossing requires adjacent nonzero samples with opposite signs.
    """

    frame_count: int
    rms_full_scale: float
    peak_full_scale: float
    dc_offset_full_scale: float
    rail_sample_count: int
    zero_crossing_count: int

    def to_dict(self) -> dict:
        return {
            "sample_rate_hz": SAMPLE_RATE,
            "frame_count": self.frame_count,
            "duration_seconds": self.frame_count / SAMPLE_RATE,
            "rms_full_scale": self.rms_full_scale,
            "peak_full_scale": self.peak_full_scale,
            "dc_offset_full_scale": self.dc_offset_full_scale,
            "rail_sample_count": self.rail_sample_count,
            "zero_crossing_count": self.zero_crossing_count,
        }


@dataclass(frozen=True, slots=True)
class RenderedSegment:
    """Rendered text retaining its original source index and frame interval."""

    source_index: int
    start_frame: int
    end_frame: int
    text: str

    def to_dict(self) -> dict:
        return {
            "source_index": self.source_index,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "start_seconds": self.start_frame / SAMPLE_RATE,
            "end_seconds": self.end_frame / SAMPLE_RATE,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class ReplayTranscript:
    fixture_id: str
    author_declared_language: str
    mode: Mode
    segments: tuple[RenderedSegment, ...]

    @property
    def full_text(self) -> str:
        return " ".join(segment.text for segment in self.segments)

    def to_dict(self) -> dict:
        return {
            "kind": "replay",
            "evidence": "simulated_fixture_replay",
            "source_kind": "synthetic_tones",
            "fixture_id": self.fixture_id,
            "author_declared_language": self.author_declared_language,
            "mode": self.mode.value,
            "segments": [segment.to_dict() for segment in self.segments],
            "full_text": self.full_text,
        }


@dataclass(frozen=True, slots=True)
class TranscriptUnavailable:
    reason: Literal["silent_input", "no_exact_fixture_match"]

    def to_dict(self) -> dict:
        return {"kind": "unavailable", "reason": self.reason}


@dataclass(frozen=True, slots=True)
class Analysis:
    sha256: str
    metrics: Metrics
    transcript: ReplayTranscript | TranscriptUnavailable

    def to_dict(self) -> dict:
        return {
            "kind": "analysis",
            "sha256": self.sha256,
            "metrics": self.metrics.to_dict(),
            "transcript": self.transcript.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class Rejected:
    code: Literal["invalid_input", "invalid_wav", "invalid_assets"]
    message: str

    def to_dict(self) -> dict:
        return {"kind": "rejected", "code": self.code, "message": self.message}


type Outcome = Analysis | Rejected


def parse_wav(wav_bytes: bytes) -> Pcm:
    """Accept only the case's strict bounded RIFF/PCM16 subset.

    Walking chunk boundaries ourselves makes duplicate chunks, truncated pads,
    and RIFF-size mismatches observable instead of accepting decoder fallback.
    Unknown complete chunks are harmless within the same byte and count caps.
    """
    if len(wav_bytes) > MAX_INPUT_BYTES:
        raise WaveError("WAV exceeds the byte limit.")
    if len(wav_bytes) < 12:
        raise WaveError("WAV header is incomplete.")
    if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        raise WaveError("Expected RIFF/WAVE audio.")
    if struct.unpack_from("<I", wav_bytes, 4)[0] != len(wav_bytes) - 8:
        raise WaveError("RIFF size does not match the complete input.")

    fmt = None
    data = None
    position = 12
    count = 0
    while position < len(wav_bytes):
        count += 1
        if count > MAX_CHUNKS:
            raise WaveError("WAV exceeds the chunk limit.")
        if len(wav_bytes) - position < 8:
            raise WaveError("WAV chunk header is incomplete.")
        chunk_id = wav_bytes[position : position + 4]
        size = struct.unpack_from("<I", wav_bytes, position + 4)[0]
        start = position + 8
        end = start + size
        padded_end = end + size % 2
        if padded_end > len(wav_bytes):
            raise WaveError("WAV chunk or padding is incomplete.")
        if chunk_id == b"fmt ":
            if fmt is not None:
                raise WaveError("WAV contains duplicate format chunks.")
            fmt = wav_bytes[start:end]
        elif chunk_id == b"data":
            if data is not None:
                raise WaveError("WAV contains duplicate data chunks.")
            data = wav_bytes[start:end]
        position = padded_end

    if fmt is None or data is None:
        raise WaveError("WAV needs one format chunk and one data chunk.")
    if len(fmt) != 16:
        raise WaveError("Only the 16-byte PCM format is supported.")
    if struct.unpack("<HHIIHH", fmt) != (1, 1, SAMPLE_RATE, 32_000, 2, 16):
        raise WaveError("Only PCM16 mono 16000 Hz audio is supported.")
    if len(data) % 2:
        raise WaveError("PCM16 data must contain complete samples.")
    frame_count = len(data) // 2
    if not 1 <= frame_count <= MAX_FRAMES:
        raise WaveError("WAV frame count is outside the supported range.")
    return Pcm(data, frame_count)


def measure(pcm: Pcm) -> Metrics:
    """Accumulate integer sample statistics before the final scale conversion."""
    total = 0
    squares = 0
    peak = 0
    rails = 0
    crossings = 0
    previous = 0
    for (sample,) in struct.iter_unpack("<h", pcm.samples):
        total += sample
        squares += sample * sample
        peak = max(peak, abs(sample))
        rails += sample in (-32_768, 32_767)
        crossings += (previous < 0 < sample) or (sample < 0 < previous)
        previous = sample  # Zero intentionally interrupts sign adjacency.
    return Metrics(
        pcm.frame_count,
        math.sqrt(squares / pcm.frame_count) / FULL_SCALE,
        peak / FULL_SCALE,
        total / pcm.frame_count / FULL_SCALE,
        rails,
        crossings,
    )


def render_replay(fixture: Fixture, mode: Mode) -> ReplayTranscript:
    """Apply text-only mode rules without changing authored frame intervals."""
    segments = []
    for index, source in enumerate(fixture.segments):
        text = source.text
        if mode is Mode.CLEAN:
            text = " ".join(
                token
                for token in text.split()
                if token.strip(string.punctuation).casefold() not in {"um", "uh"}
            )
            if not text:
                continue
        segments.append(RenderedSegment(index, source.start_frame, source.end_frame, text))
    return ReplayTranscript(
        fixture.fixture_id, fixture.author_declared_language, mode, tuple(segments)
    )


def analyze_validated_assets(
    wav_bytes: bytes, mode: Mode, fixtures: tuple[Fixture, ...]
) -> Outcome:
    """Internal pure operation. Callers must first validate package metadata."""
    try:
        pcm = parse_wav(wav_bytes)
    except WaveError as error:
        return Rejected("invalid_wav", str(error))
    digest = hashlib.sha256(wav_bytes).hexdigest()
    metrics = measure(pcm)
    transcript: ReplayTranscript | TranscriptUnavailable
    if metrics.peak_full_scale == 0:
        transcript = TranscriptUnavailable("silent_input")
    else:
        # Package validation owns annotations. A filename or equivalent PCM
        # cannot grant replay authority for a different complete WAV container.
        match = next((fixture for fixture in fixtures if fixture.sha256 == digest), None)
        transcript = (
            render_replay(match, mode)
            if match is not None
            else TranscriptUnavailable("no_exact_fixture_match")
        )
    return Analysis(digest, metrics, transcript)
