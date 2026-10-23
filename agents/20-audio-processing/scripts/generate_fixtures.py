"""Reproduce synthetic tone fixtures and their authored replay manifest.

Integer square waves avoid platform-dependent speech tools or floating-point
oscillators. They encode no words. The paired English text is a deliberate
simulation for testing digest provenance and frame-preserving text modes.
"""

import hashlib
import json
from pathlib import Path
import struct


def wav(samples: list[int]) -> bytes:
    data = struct.pack(f"<{len(samples)}h", *samples)
    fmt = struct.pack("<HHIIHH", 1, 1, 16_000, 32_000, 2, 16)
    body = b"WAVEfmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(data)) + data
    return b"RIFF" + struct.pack("<I", len(body)) + body


def generated_assets() -> dict[str, bytes]:
    """Return all deterministic resources without writing files."""
    complaint = (
        [10_000 if (index // 40) % 2 == 0 else -10_000 for index in range(24_000)]
        + [8_000 if (index // 32) % 2 == 0 else -8_000 for index in range(24_000)]
    )
    assets = {"complaint.wav": wav(complaint), "silence.wav": wav([0] * 32_000)}
    manifest = {
        "version": 1,
        "fixtures": [
            {
                "fixture_id": "complaint",
                "filename": "complaint.wav",
                "sha256": hashlib.sha256(assets["complaint.wav"]).hexdigest(),
                "frame_count": 48_000,
                "author_declared_language": "en",
                "source_kind": "synthetic_tones",
                "segments": [
                    {"start_frame": 0, "end_frame": 24_000, "text": "Um, my parcel is late."},
                    {"start_frame": 24_000, "end_frame": 48_000, "text": "Uh, please check its status."},
                ],
            },
            {
                "fixture_id": "silence",
                "filename": "silence.wav",
                "sha256": hashlib.sha256(assets["silence.wav"]).hexdigest(),
                "frame_count": 32_000,
                "author_declared_language": "en",
                "source_kind": "synthetic_tones",
                "segments": [],
            },
        ],
    }
    assets["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    return assets


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "src" / "audio_processing" / "data"
    target.mkdir(parents=True, exist_ok=True)
    for filename, content in generated_assets().items():
        target.joinpath(filename).write_bytes(content)
    print("Generated complaint.wav, silence.wav, and manifest.json.")
