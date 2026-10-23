"""Analytical and adversarial checks for the waveform and replay contracts."""

import copy
from dataclasses import FrozenInstanceError
import hashlib
import io
import json
import math
from pathlib import Path
import runpy
import struct
import unittest
from unittest.mock import patch
import wave

from audio_processing import Analysis, Mode, Rejected, analyze, analyze_fixture
from audio_processing.assets import AssetError, load_assets, validate_assets
from audio_processing.core import (
    Fixture, MAX_FRAMES, MAX_INPUT_BYTES, SourceSegment,
    TranscriptUnavailable, parse_wav, render_replay,
)


def make_wav(samples, rate=16_000, channels=1, width=2):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(width)
        output.setframerate(rate)
        output.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return stream.getvalue()


def chunk(name, body, padding=True):
    return name + struct.pack("<I", len(body)) + body + (b"\0" if padding and len(body) % 2 else b"")


def riff(*chunks):
    body = b"WAVE" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body


FMT = struct.pack("<HHIIHH", 1, 1, 16_000, 32_000, 2, 16)


def metadata(samples=(1, -1)):
    wav_bytes = make_wav(samples)
    document = {
        "version": 1,
        "fixtures": [{
            "fixture_id": "test",
            "filename": "test.wav",
            "sha256": hashlib.sha256(wav_bytes).hexdigest(),
            "frame_count": len(samples),
            "author_declared_language": "en",
            "source_kind": "synthetic_tones",
            "segments": [{"start_frame": 0, "end_frame": len(samples), "text": "Um, a test."}],
        }],
    }
    return document, wav_bytes


class SignalTests(unittest.TestCase):
    def test_analytical_metrics_on_original_signed_samples(self):
        raw = make_wav([0, 32_767, -32_768, 1, 0, -1, 1, -1])
        result = analyze(raw)
        self.assertIsInstance(result, Analysis)
        metrics = result.metrics.to_dict()
        self.assertEqual(result.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(metrics["sample_rate_hz"], 16_000)
        self.assertEqual(metrics["frame_count"], 8)
        self.assertEqual(metrics["duration_seconds"], 8 / 16_000)
        self.assertAlmostEqual(metrics["rms_full_scale"], math.sqrt((32767**2 + 32768**2 + 4) / 8) / 32768)
        self.assertEqual(metrics["peak_full_scale"], 1)
        self.assertEqual(metrics["dc_offset_full_scale"], -1 / 8 / 32768)
        self.assertEqual(metrics["rail_sample_count"], 2)
        self.assertEqual(metrics["zero_crossing_count"], 4)
        self.assertEqual(result.transcript, TranscriptUnavailable("no_exact_fixture_match"))
        json.dumps(result.to_dict(), allow_nan=False)

    def test_quiet_nonzero_is_not_silence(self):
        result = analyze(make_wav([1] * 160))
        self.assertEqual(result.metrics.rms_full_scale, 1 / 32768)
        self.assertEqual(result.metrics.dc_offset_full_scale, 1 / 32768)
        self.assertEqual(result.transcript.reason, "no_exact_fixture_match")

    def test_zero_interrupts_adjacent_crossings(self):
        self.assertEqual(analyze(make_wav([-1, 0, 1])).metrics.zero_crossing_count, 0)
        self.assertEqual(analyze(make_wav([-1, 1, -1])).metrics.zero_crossing_count, 2)

    def test_silence_has_metrics_without_text(self):
        result = analyze_fixture("silence")
        self.assertEqual(result.transcript.to_dict(), {"kind": "unavailable", "reason": "silent_input"})
        self.assertEqual(result.metrics.frame_count, 32_000)
        self.assertEqual(result.metrics.rms_full_scale, 0)
        self.assertEqual(result.metrics.peak_full_scale, 0)
        self.assertEqual(result.metrics.dc_offset_full_scale, 0)
        self.assertEqual(result.metrics.rail_sample_count, 0)
        self.assertEqual(result.metrics.zero_crossing_count, 0)

    def test_maximum_frame_count_is_measurable(self):
        result = analyze(make_wav([32_767] * MAX_FRAMES))
        self.assertIsInstance(result, Analysis)
        self.assertEqual(result.metrics.frame_count, MAX_FRAMES)
        self.assertEqual(result.metrics.rms_full_scale, 32767 / 32768)

    def test_immutable_outcomes(self):
        result = analyze_fixture("complaint")
        with self.assertRaises(FrozenInstanceError):
            result.sha256 = "changed"
        exported = result.to_dict()
        exported["transcript"]["segments"][0]["text"] = "changed"
        self.assertEqual(result.transcript.segments[0].text, "my parcel is late.")


class ReplayTests(unittest.TestCase):
    def test_complaint_modes_share_identity_measurements_and_intervals(self):
        clean = analyze_fixture("complaint")
        verbatim = analyze_fixture("complaint", Mode.VERBATIM)
        self.assertEqual(clean.sha256, verbatim.sha256)
        self.assertEqual(clean.metrics, verbatim.metrics)
        self.assertEqual(clean.transcript.full_text, "my parcel is late. please check its status.")
        self.assertEqual(verbatim.transcript.full_text, "Um, my parcel is late. Uh, please check its status.")
        self.assertEqual([(s.source_index, s.start_frame, s.end_frame) for s in clean.transcript.segments], [(0, 0, 24000), (1, 24000, 48000)])
        self.assertEqual([(s.start_frame, s.end_frame) for s in clean.transcript.segments], [(s.start_frame, s.end_frame) for s in verbatim.transcript.segments])
        self.assertEqual(clean.metrics.peak_full_scale, 10000 / 32768)
        self.assertEqual(clean.metrics.dc_offset_full_scale, 0)
        self.assertEqual(clean.metrics.zero_crossing_count, 1349)
        self.assertAlmostEqual(clean.metrics.rms_full_scale, math.sqrt(82_000_000) / 32768)
        rendered = clean.transcript.to_dict()
        self.assertEqual(rendered["evidence"], "simulated_fixture_replay")
        self.assertEqual(rendered["source_kind"], "synthetic_tones")
        self.assertEqual(rendered["author_declared_language"], "en")
        self.assertEqual(rendered["segments"][1]["start_seconds"], 1.5)
        self.assertEqual(rendered["segments"][1]["end_seconds"], 3.0)
        for unsupported in ("confidence", "language", "sentiment", "emotion", "speaker"):
            self.assertNotIn(unsupported, rendered)

    def test_one_sample_byte_change_loses_replay(self):
        raw = bytearray(load_assets().waveform("complaint"))
        raw[-1] ^= 1
        result = analyze(bytes(raw))
        self.assertIsInstance(result, Analysis)
        self.assertEqual(result.transcript.reason, "no_exact_fixture_match")

    def test_same_pcm_in_different_container_loses_replay(self):
        raw = load_assets().waveform("complaint")
        alternate = riff(chunk(b"JUNK", b"x"), raw[12:])
        original = analyze(raw)
        changed = analyze(alternate)
        self.assertEqual(original.metrics, changed.metrics)
        self.assertNotEqual(original.sha256, changed.sha256)
        self.assertEqual(changed.transcript.reason, "no_exact_fixture_match")

    def test_clean_token_rule_is_exact_and_uses_unicode_whitespace(self):
        authored = "  (UM),\u00a0uh...  umbrella uh-huh umm “um” ... uh!word  "
        fixture = Fixture("test", "0" * 64, 10, "en", (SourceSegment(0, 10, authored),))
        self.assertEqual(render_replay(fixture, Mode.CLEAN).full_text, "umbrella uh-huh umm “um” ... uh!word")
        self.assertEqual(render_replay(fixture, Mode.VERBATIM).segments[0].text, authored)

    def test_omitted_filler_segments_preserve_source_indices_and_frames(self):
        fixture = Fixture("test", "0" * 64, 10, "en", (
            SourceSegment(0, 2, "Um, uh!"),
            SourceSegment(2, 5, " retain. "),
            SourceSegment(5, 10, "UH"),
        ))
        result = render_replay(fixture, Mode.CLEAN)
        self.assertEqual([(s.source_index, s.start_frame, s.end_frame, s.text) for s in result.segments], [(1, 2, 5, "retain.")])
        self.assertEqual(result.full_text, "retain.")

    def test_all_filler_is_a_valid_empty_replay(self):
        fixture = Fixture("test", "0" * 64, 2, "en", (SourceSegment(0, 2, "Um UH."),))
        result = render_replay(fixture, Mode.CLEAN)
        self.assertEqual(result.to_dict()["kind"], "replay")
        self.assertEqual(result.segments, ())
        self.assertEqual(result.full_text, "")

    def test_public_api_has_no_annotation_override(self):
        with self.assertRaises(TypeError):
            analyze(make_wav([1]), fixtures=())
        with self.assertRaises(TypeError):
            analyze(make_wav([1]), "clean")
        with self.assertRaises(ValueError):
            analyze_fixture("../other")

    def test_fixed_resource_corruption_fails_before_analysis(self):
        with patch("audio_processing.load_assets", side_effect=AssetError("Packaged resources cannot be read.")):
            self.assertEqual(analyze(make_wav([1])).code, "invalid_assets")
            self.assertEqual(analyze_fixture("complaint").code, "invalid_assets")

    def test_generated_assets_match_committed_bytes(self):
        root = Path(__file__).resolve().parents[1]
        generated = runpy.run_path(str(root / "scripts" / "generate_fixtures.py"))["generated_assets"]()
        for filename, content in generated.items():
            with self.subTest(filename=filename):
                self.assertEqual((root / "src" / "audio_processing" / "data" / filename).read_bytes(), content)


class WaveRejectionTests(unittest.TestCase):
    def assert_rejected(self, raw):
        result = analyze(raw)
        self.assertIsInstance(result, Rejected)
        self.assertEqual(result.code, "invalid_wav")
        self.assertNotIn("metrics", result.to_dict())

    def test_truncation_at_every_byte_of_a_small_wav(self):
        raw = make_wav([1, -1])
        for length in range(len(raw)):
            with self.subTest(length=length):
                self.assert_rejected(raw[:length])

    def test_empty_oversized_and_too_many_frames(self):
        for raw in (b"", b"x" * (MAX_INPUT_BYTES + 1), make_wav([]), make_wav([1] * (MAX_FRAMES + 1))):
            with self.subTest(length=len(raw)):
                self.assert_rejected(raw)

    def test_container_structure_failures(self):
        valid_data = chunk(b"data", b"\x01\0")
        fmt = chunk(b"fmt ", FMT)
        cases = {
            "no_fmt": riff(valid_data),
            "no_data": riff(fmt),
            "duplicate_fmt": riff(fmt, fmt, valid_data),
            "duplicate_data": riff(fmt, valid_data, valid_data),
            "extended_fmt": riff(chunk(b"fmt ", FMT + b"\0\0"), valid_data),
            "odd_data": riff(fmt, chunk(b"data", b"x")),
            "missing_pad": riff(fmt, valid_data, chunk(b"JUNK", b"x", padding=False)),
            "incomplete_chunk_header": riff(fmt, valid_data, b"junk"),
            "incomplete_chunk_body": riff(fmt, valid_data, b"JUNK\x08\0\0\0xx"),
            "trailing_bytes": make_wav([1]) + b"x",
            "wrong_riff_size": make_wav([1])[:4] + b"\0\0\0\0" + make_wav([1])[8:],
            "wrong_magic": b"RIFX" + make_wav([1])[4:],
            "wrong_wave": make_wav([1])[:8] + b"NOPE" + make_wav([1])[12:],
        }
        for name, raw in cases.items():
            with self.subTest(case=name):
                self.assert_rejected(raw)

    def test_every_pcm_format_field_is_enforced(self):
        fields = [1, 1, 16000, 32000, 2, 16]
        for index, value in enumerate((3, 2, 8000, 1, 1, 8)):
            changed = fields.copy()
            changed[index] = value
            with self.subTest(index=index):
                self.assert_rejected(riff(chunk(b"fmt ", struct.pack("<HHIIHH", *changed)), chunk(b"data", b"\1\0")))

    def test_chunk_cap_allows_64_complete_chunks_only(self):
        base = (chunk(b"fmt ", FMT), chunk(b"data", b"\1\0"))
        self.assertIsInstance(analyze(riff(*base, *([chunk(b"JUNK", b"x")] * 62))), Analysis)
        self.assert_rejected(riff(*base, *([chunk(b"JUNK", b"")] * 63)))

    def test_complete_unknown_chunks_and_data_before_fmt_are_allowed(self):
        result = analyze(riff(chunk(b"data", b"\1\0"), chunk(b"JUNK", b"x"), chunk(b"fmt ", FMT)))
        self.assertIsInstance(result, Analysis)
        self.assertEqual(result.metrics.frame_count, 1)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.document, self.wav = metadata()

    def validate(self, document):
        return validate_assets(json.dumps(document).encode(), lambda _name: self.wav)

    def test_valid_manifest_freezes_ordered_metadata(self):
        assets = self.validate(self.document)
        self.document["fixtures"][0]["segments"][0]["text"] = "changed"
        self.assertEqual(assets.fixtures[0].segments[0].text, "Um, a test.")
        self.assertEqual(assets.waveform("test"), self.wav)

    def test_json_duplicates_invalid_encoding_nonfinite_and_limits(self):
        cases = [
            b'{"version":1,"version":1,"fixtures":[]}',
            b'{"version":1,"fixtures":[{"fixture_id":"a","fixture_id":"b"}]}',
            b'{"version":NaN,"fixtures":[]}',
            b'{"version":Infinity,"fixtures":[]}',
            b'{"version":1e999,"fixtures":[]}',
            b"\xff", b"{", b"[]", b"x" * 65_537,
            b"[" * 2000 + b"]" * 2000,
        ]
        for raw in cases:
            with self.subTest(raw_length=len(raw)):
                with self.assertRaises(AssetError):
                    validate_assets(raw, lambda _name: self.wav)

    def test_unknown_fields_at_each_level(self):
        for level in ("root", "fixture", "segment"):
            document = copy.deepcopy(self.document)
            target = {"root": document, "fixture": document["fixtures"][0], "segment": document["fixtures"][0]["segments"][0]}[level]
            target["extra"] = "not allowed"
            with self.subTest(level=level), self.assertRaises(AssetError):
                self.validate(document)

    def test_invalid_metadata_types_and_values(self):
        mutations = [
            ("version", True), ("version", 2), ("fixtures", []), ("fixtures", {}),
            ("fixture_id", "../test"), ("fixture_id", True),
            ("filename", "../test.wav"), ("filename", "/test.wav"), ("filename", "test\\file.wav"),
            ("sha256", "0" * 63), ("sha256", "A" * 64),
            ("frame_count", True), ("frame_count", 0), ("frame_count", 1.0),
            ("author_declared_language", ""), ("author_declared_language", "en\n"),
            ("source_kind", "speech"), ("segments", {}), ("segments", [None]),
        ]
        for key, value in mutations:
            document = copy.deepcopy(self.document)
            target = document if key in {"version", "fixtures"} else document["fixtures"][0]
            target[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(AssetError):
                self.validate(document)

    def test_invalid_segment_fields_offsets_text_and_controls(self):
        for key, value in (
            ("start_frame", True), ("start_frame", -1), ("start_frame", 1.0),
            ("end_frame", False), ("end_frame", 0), ("end_frame", 3),
            ("text", None), ("text", "x" * 1001), ("text", "bad\ntext"),
            ("text", "bad\x7ftext"), ("text", "bad\u202etext"), ("text", "\ud800"),
        ):
            document = copy.deepcopy(self.document)
            document["fixtures"][0]["segments"][0][key] = value
            with self.subTest(key=key, value=repr(value)), self.assertRaises(AssetError):
                self.validate(document)

    def test_interval_order_and_overlap_are_rejected(self):
        document, self.wav = metadata([1] * 10)
        for spans in (((3, 5), (0, 2)), ((0, 5), (4, 8)), ((0, 2), (2, 2))):
            document["fixtures"][0]["segments"] = [{"start_frame": start, "end_frame": end, "text": "text"} for start, end in spans]
            with self.subTest(spans=spans), self.assertRaises(AssetError):
                self.validate(document)

    def test_duplicate_ids_or_digests_are_rejected(self):
        for field in ("fixture_id", "sha256"):
            document = copy.deepcopy(self.document)
            other = copy.deepcopy(document["fixtures"][0])
            other["fixture_id"] = "other"
            other["sha256"] = "0" * 64
            other[field] = document["fixtures"][0][field]
            document["fixtures"].append(other)
            with self.subTest(field=field), self.assertRaises(AssetError):
                self.validate(document)

    def test_digest_frame_count_and_malformed_asset_fail_closed(self):
        for key, value in (("sha256", "0" * 64), ("frame_count", 3)):
            document = copy.deepcopy(self.document)
            document["fixtures"][0][key] = value
            with self.subTest(key=key), self.assertRaises(AssetError):
                self.validate(document)
        for bad in (b"bad", b"x" * (MAX_INPUT_BYTES + 1), "not bytes"):
            with self.subTest(value_type=type(bad)), self.assertRaises(AssetError):
                validate_assets(json.dumps(self.document).encode(), lambda _name: bad)

    def test_filename_is_rejected_before_any_resource_read(self):
        self.document["fixtures"][0]["filename"] = "../private.wav"
        with patch("builtins.open", side_effect=AssertionError("must not read")):
            with self.assertRaises(AssetError):
                validate_assets(json.dumps(self.document).encode(), lambda _name: self.fail("unsafe resource read"))

    def test_segment_limit_and_valid_maximum_text_length(self):
        document, self.wav = metadata([1] * 128)
        document["fixtures"][0]["segments"] = [{"start_frame": index, "end_frame": index + 1, "text": "x" * 1000} for index in range(128)]
        encoded = json.dumps(document).encode()
        self.assertGreater(len(encoded), 65_536)
        with self.assertRaises(AssetError):
            self.validate(document)
        document["fixtures"][0]["segments"] = [{"start_frame": index, "end_frame": index + 1, "text": "x"} for index in range(128)]
        self.assertEqual(len(self.validate(document).fixtures[0].segments), 128)
        document["fixtures"][0]["segments"].append(document["fixtures"][0]["segments"][-1])
        with self.assertRaises(AssetError):
            self.validate(document)
        self.document, self.wav = metadata()
        self.document["fixtures"][0]["segments"][0]["text"] = "x" * 1000
        self.assertEqual(len(self.validate(self.document).fixtures[0].segments[0].text), 1000)

    def test_eight_unique_fixtures_allowed_ninth_rejected(self):
        document = {"version": 1, "fixtures": []}
        waveforms = {}
        for index in range(9):
            item_document, raw = metadata([index + 1])
            item = item_document["fixtures"][0]
            item["fixture_id"] = f"fixture{index}"
            item["filename"] = f"fixture{index}.wav"
            document["fixtures"].append(item)
            waveforms[item["filename"]] = raw
        eight = copy.deepcopy(document)
        eight["fixtures"].pop()
        self.assertEqual(len(validate_assets(json.dumps(eight).encode(), waveforms.__getitem__).fixtures), 8)
        with self.assertRaises(AssetError):
            validate_assets(json.dumps(document).encode(), waveforms.__getitem__)


if __name__ == "__main__":
    unittest.main()
