"""Validate the fixed package's replay annotations and every packaged waveform.

The manifest is data, never an instruction or a runtime configuration source.
Validation rejects ambiguous JSON and binds each annotation to complete WAV
bytes. Acquisition accepts only capped POSIX regular files and never extracts
non-filesystem resources. No invocation cache survives a call. Tests can validate
damaged bytes through this boundary without a public annotation override.
"""

from dataclasses import dataclass
import hashlib
from importlib import resources
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Callable
import unicodedata

from .core import Fixture, MAX_FRAMES, MAX_INPUT_BYTES, SourceSegment, WaveError, parse_wav

MAX_MANIFEST_BYTES = 65_536
FIXTURE_IDS = ("complaint", "silence")


class AssetError(ValueError):
    """A safe package-integrity failure, with no paths or package contents."""


@dataclass(frozen=True, slots=True)
class Assets:
    """One invocation's verified annotations and their immutable WAV bytes."""

    fixtures: tuple[Fixture, ...]
    waveforms: tuple[tuple[str, bytes], ...]

    def waveform(self, fixture_id: str) -> bytes:
        for name, wav_bytes in self.waveforms:
            if name == fixture_id:
                return wav_bytes
        raise ValueError("Unknown packaged fixture.")


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise AssetError("Packaged metadata contains duplicate keys.")
        result[key] = value
    return result


def _float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise AssetError("Packaged metadata contains a nonfinite number.")
    return value


def _constant(_text: str) -> None:
    raise AssetError("Packaged metadata contains a nonfinite number.")


def _fields(value: object, expected: set[str]) -> dict:
    if type(value) is not dict or set(value) != expected:
        raise AssetError("Packaged metadata has invalid fields.")
    return value


def _integer(value: object, lower: int, upper: int) -> int:
    # bool is an int subclass, but it cannot own a frame offset or a version.
    if type(value) is not int or not lower <= value <= upper:
        raise AssetError("Packaged metadata has an invalid integer.")
    return value


def _matches(value: object, pattern: str) -> str:
    if type(value) is not str or re.fullmatch(pattern, value) is None:
        raise AssetError("Packaged metadata has an invalid identifier.")
    return value


def validate_assets(manifest_bytes: bytes, read_waveform: Callable[[str], bytes]) -> Assets:
    """Internal boundary for bounded metadata plus bounded package WAV reads.

    The callback is supplied only by fixed package acquisition or local tests.
    It cannot be selected by the public operation or CLI. The returned records
    contain no mutable metadata shared with the JSON decoder.
    """
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise AssetError("Packaged metadata exceeds the byte limit.")
    try:
        decoded = json.loads(
            manifest_bytes.decode("utf-8"),
            object_pairs_hook=_object,
            parse_float=_float,
            parse_constant=_constant,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        if isinstance(error, AssetError):
            raise
        raise AssetError("Packaged metadata is not valid JSON.") from None
    root = _fields(decoded, {"version", "fixtures"})
    _integer(root["version"], 1, 1)
    raw_fixtures = root["fixtures"]
    if type(raw_fixtures) is not list or not 1 <= len(raw_fixtures) <= 8:
        raise AssetError("Packaged metadata has an invalid fixture count.")

    fixtures = []
    waveforms = []
    ids = set()
    digests = set()
    for raw in raw_fixtures:
        item = _fields(raw, {
            "fixture_id", "filename", "sha256", "frame_count",
            "author_declared_language", "source_kind", "segments",
        })
        fixture_id = _matches(item["fixture_id"], r"[a-z][a-z0-9_-]{0,31}")
        filename = _matches(item["filename"], r"[a-z][a-z0-9_-]{0,63}\.wav")
        digest = _matches(item["sha256"], r"[0-9a-f]{64}")
        if fixture_id in ids or digest in digests:
            raise AssetError("Packaged metadata repeats a fixture identity.")
        ids.add(fixture_id)
        digests.add(digest)
        frame_count = _integer(item["frame_count"], 1, MAX_FRAMES)
        language = _matches(
            item["author_declared_language"], r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8}){0,4}"
        )
        if item["source_kind"] != "synthetic_tones":
            raise AssetError("Packaged metadata has an unsupported source kind.")
        raw_segments = item["segments"]
        if type(raw_segments) is not list or len(raw_segments) > 128:
            raise AssetError("Packaged metadata has an invalid segment count.")
        segments = []
        previous_end = 0
        for raw_segment in raw_segments:
            segment = _fields(raw_segment, {"start_frame", "end_frame", "text"})
            start = _integer(segment["start_frame"], 0, frame_count - 1)
            end = _integer(segment["end_frame"], start + 1, frame_count)
            if start < previous_end:
                raise AssetError("Packaged segment intervals overlap or are unordered.")
            text = segment["text"]
            if type(text) is not str or len(text) > 1_000:
                raise AssetError("Packaged segment text has an invalid type or length.")
            if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in text):
                raise AssetError("Packaged segment text contains control characters.")
            segments.append(SourceSegment(start, end, text))
            previous_end = end

        try:
            wav_bytes = read_waveform(filename)
        except OSError:
            raise AssetError("A packaged waveform cannot be read.") from None
        if type(wav_bytes) is not bytes or len(wav_bytes) > MAX_INPUT_BYTES:
            raise AssetError("A packaged waveform exceeds its byte limit or has an invalid type.")
        try:
            pcm = parse_wav(wav_bytes)
        except WaveError:
            raise AssetError("A packaged waveform is invalid.") from None
        if hashlib.sha256(wav_bytes).hexdigest() != digest or pcm.frame_count != frame_count:
            raise AssetError("A packaged waveform does not match its declared identity.")
        fixtures.append(Fixture(fixture_id, digest, frame_count, language, tuple(segments)))
        waveforms.append((fixture_id, wav_bytes))
    return Assets(tuple(fixtures), tuple(waveforms))


def _read_resource(path: Path, limit: int) -> bytes:
    """Acquire capped bytes from one opened package file, then close its descriptor.

    Nonblocking open permits rejecting FIFOs before reading. No-follow plus
    fstat prevents final symlinks or substituted special files from supplying
    package data. The read cap also applies when a regular file grows.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise AssetError("Packaged resources must be regular files.")
            if info.st_size > limit:
                raise AssetError("A packaged resource exceeds its byte limit.")
            chunks = []
            total = 0
            while total <= limit:
                part = os.read(descriptor, limit + 1 - total)
                if not part:
                    return b"".join(chunks)
                chunks.append(part)
                total += len(part)
            raise AssetError("A packaged resource exceeds its byte limit.")
        finally:
            os.close(descriptor)
    except AssetError:
        raise
    except (OSError, ValueError):
        raise AssetError("Packaged resources cannot be read.") from None


def load_assets() -> Assets:
    """Read fixed filesystem resources without blocking on special-file opens.

    Source trees, case copies, and installed wheels expose pathlib paths on the
    supported POSIX runtime. Other traversables fail closed without extraction.
    """
    try:
        package = resources.files("audio_processing")
    except (OSError, ValueError, ModuleNotFoundError):
        raise AssetError("Packaged resources cannot be read.") from None
    if not isinstance(package, Path):
        raise AssetError("Packaged resources require filesystem files.")
    data = package.joinpath("data")
    manifest = _read_resource(data.joinpath("manifest.json"), MAX_MANIFEST_BYTES)

    def read_waveform(filename: str) -> bytes:
        return _read_resource(data.joinpath(filename), MAX_INPUT_BYTES)

    assets = validate_assets(manifest, read_waveform)
    if {fixture.fixture_id for fixture in assets.fixtures} != set(FIXTURE_IDS):
        raise AssetError("Packaged fixture names do not match the fixed allowlist.")
    return assets
