"""Qualify the real CLI using independently constructed WAVs and expected values.

This script never imports the agent. It compares JSON with direct arithmetic,
mutates RIFF structure, and exercises local-file and output descriptors. Pass
``--command /path/to/audio-processing`` to qualify an installed wheel.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile


def chunk(name: bytes, data: bytes) -> bytes:
    return name + struct.pack("<I", len(data)) + data + (b"\0" if len(data) % 2 else b"")


def wav(samples: list[int], *, extra: bytes = b"", **parameters: int) -> bytes:
    values = {"tag": 1, "channels": 1, "rate": 16000, "byte_rate": 32000, "align": 2, "bits": 16}
    values.update(parameters)
    fmt = struct.pack("<HHIIHH", *values.values())
    pcm = struct.pack(f"<{len(samples)}h", *samples)
    body = b"WAVE" + chunk(b"fmt ", fmt) + extra + chunk(b"data", pcm)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, help="Also probe corrupted copies of this package directory.")
    parser.add_argument("--command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command or [sys.executable, "-m", "audio_processing"]
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "PYTHONPATH"):
        environment.pop(key, None)
    checks = 0

    def invoke(arguments: list[str], *, expected: int = 0, **options: object) -> dict:
        nonlocal checks
        result = subprocess.run(
            command + arguments,
            capture_output=True,
            env=environment,
            timeout=10,
            **options,
        )
        checks += 1
        assert result.returncode == expected, (arguments, result.returncode, result.stderr)
        assert b"Traceback" not in result.stderr, (arguments, result.stderr)
        if result.stdout:
            value = json.loads(result.stdout)
            assert isinstance(value, dict), value
            return value
        assert expected != 0, (arguments, "missing report")
        return {}

    clean = invoke(["--fixture", "complaint", "--mode", "clean"])
    verbatim = invoke(["--fixture", "complaint", "--mode", "verbatim"])
    assert clean["kind"] == verbatim["kind"] == "analysis"
    assert clean["sha256"] == verbatim["sha256"]
    assert clean["metrics"] == verbatim["metrics"]
    for report in (clean, verbatim):
        transcript = report["transcript"]
        assert transcript["kind"] == "replay"
        assert transcript["evidence"] == "simulated_fixture_replay"
        assert transcript["source_kind"] == "synthetic_tones"
        assert transcript["author_declared_language"] == "en"
        assert all(key not in report for key in ("confidence", "emotion", "sentiment"))
        for segment in transcript["segments"]:
            assert segment["start_seconds"] == segment["start_frame"] / 16000
            assert segment["end_seconds"] == segment["end_frame"] / 16000
    assert verbatim["transcript"]["full_text"] == "Um, my parcel is late. Uh, please check its status."
    assert clean["transcript"]["full_text"] == "my parcel is late. please check its status."
    complaint_samples = [10000 if (i // 40) % 2 == 0 else -10000 for i in range(24000)]
    complaint_samples += [8000 if (i // 32) % 2 == 0 else -8000 for i in range(24000)]
    complaint_wav = wav(complaint_samples)
    assert clean["sha256"] == hashlib.sha256(complaint_wav).hexdigest()
    assert clean["metrics"]["frame_count"] == 48000
    assert clean["metrics"]["zero_crossing_count"] == 1349
    assert math.isclose(clean["metrics"]["rms_full_scale"], math.sqrt(82000000) / 32768, rel_tol=1e-12)
    assert clean["metrics"]["peak_full_scale"] == 10000 / 32768
    for index in range(2):
        assert clean["transcript"]["segments"][index]["start_frame"] == index * 24000
        assert clean["transcript"]["segments"][index]["end_frame"] == (index + 1) * 24000
        for key in ("source_index", "start_frame", "end_frame"):
            assert clean["transcript"]["segments"][index][key] == verbatim["transcript"]["segments"][index][key]
    assert invoke(["--fixture", "complaint"]) == clean
    silent = invoke(["--fixture", "silence"])
    assert silent["transcript"] == {"kind": "unavailable", "reason": "silent_input"}
    assert silent["metrics"]["rms_full_scale"] == silent["metrics"]["peak_full_scale"] == 0

    with tempfile.TemporaryDirectory(prefix="audio-cli-oracle-") as directory:
        base = Path(directory)
        private = base / "private-customer-label.wav"

        def analyze_bytes(data: bytes, *, rejected: bool = False) -> dict:
            private.write_bytes(data)
            before = set(base.iterdir())
            value = invoke(["--input", str(private)], expected=2 if rejected else 0)
            assert set(base.iterdir()) == before, "CLI created a report or state file"
            assert "private-customer-label" not in json.dumps(value)
            if rejected:
                assert value["kind"] == "rejected", value
            else:
                assert value["kind"] == "analysis", value
                assert value["sha256"] == hashlib.sha256(data).hexdigest()
            return value

        assert analyze_bytes(complaint_wav) == clean
        altered = bytearray(complaint_wav)
        altered[-1] ^= 1
        assert analyze_bytes(bytes(altered))["transcript"] == {"kind": "unavailable", "reason": "no_exact_fixture_match"}
        equivalent = analyze_bytes(wav(complaint_samples, extra=chunk(b"JUNK", b"equivalent samples")))
        assert equivalent["metrics"] == clean["metrics"]
        assert equivalent["transcript"] == {"kind": "unavailable", "reason": "no_exact_fixture_match"}

        vectors = [
            [0], [1], [-1], [32767], [-32768],
            [32767, -32768, 0, 16384, -8192],
            [1000, -1000, 0, 1000, -1000],
            [0, 1000, 0, -1000, 0],
            [1024] * 17,
            [8192, -8192] * 8000,
        ]
        for samples in vectors:
            report = analyze_bytes(wav(samples))
            metrics = report["metrics"]
            expected = {
                "sample_rate_hz": 16000,
                "frame_count": len(samples),
                "duration_seconds": len(samples) / 16000,
                "rms_full_scale": math.sqrt(sum(x * x for x in samples) / len(samples)) / 32768,
                "peak_full_scale": max(abs(x) for x in samples) / 32768,
                "dc_offset_full_scale": sum(samples) / len(samples) / 32768,
                "rail_sample_count": sum(x in (-32768, 32767) for x in samples),
                "zero_crossing_count": sum(a * b < 0 for a, b in zip(samples, samples[1:])),
            }
            assert metrics.keys() == expected.keys(), metrics
            for key, value in expected.items():
                assert math.isclose(metrics[key], value, rel_tol=1e-12, abs_tol=1e-15), (key, metrics[key], value)
            reason = "silent_input" if not any(samples) else "no_exact_fixture_match"
            assert report["transcript"] == {"kind": "unavailable", "reason": reason}

        accepted = wav([17, -19, 23], extra=chunk(b"JUNK", b"odd"))
        analyze_bytes(accepted)
        analyze_bytes(wav([1], extra=chunk(b"JUNK", b"") * 62))
        at_limit = wav([1] * 480000)
        assert analyze_bytes(at_limit)["metrics"]["frame_count"] == 480000

        canonical = wav([1, -1, 0, 2])
        invalid = [
            b"", b"RIFF", b"not a wave", canonical + b"trailing", canonical[:-1],
            b"RIFX" + canonical[4:], b"RF64" + canonical[4:],
            canonical[:8] + b"AVI " + canonical[12:], wav([]),
            wav([1], tag=3), wav([1], channels=2), wav([1], rate=8000),
            wav([1], byte_rate=123), wav([1], align=4), wav([1], bits=8),
            wav([1], extra=chunk(b"fmt ", canonical[20:36])),
            wav([1], extra=chunk(b"data", b"\0\0")),
            wav([1], extra=chunk(b"JUNK", b"") * 65),
            wav([1] * 480001), b"x" * (1048576 + 1),
        ]
        odd_data_body = b"WAVE" + canonical[12:36] + chunk(b"data", b"\x01")
        invalid.append(b"RIFF" + struct.pack("<I", len(odd_data_body)) + odd_data_body)
        for value in invalid:
            analyze_bytes(value, rejected=True)
        for offset in (4, 16, 40):
            for size in (0, 1, 0xFFFFFFFF):
                altered = bytearray(canonical)
                struct.pack_into("<I", altered, offset, size)
                analyze_bytes(bytes(altered), rejected=True)

        missing = base / "private-customer-label-missing.wav"
        result = invoke(["--input", str(missing)], expected=2)
        assert result["kind"] == "rejected" and str(missing) not in json.dumps(result)
        invoke(["--input", str(base)], expected=2)
        private.write_bytes(canonical)
        link = base / "linked.wav"
        link.symlink_to(private)
        invoke(["--input", str(link)], expected=2)
        fifo = base / "pipe.wav"
        os.mkfifo(fifo)
        invoke(["--input", str(fifo)], expected=2)

        for arguments in (
            [], ["--fixture", "missing"], ["--fixture", "complaint", "--mode", "normalized"],
            ["--fixture", "complaint", "--input", str(private)],
            ["--fixture", "../complaint"], ["--fixture", "complaint", "--manifest", "evil.json"],
        ):
            invoke(arguments, expected=2)

        for flags in ([], ["-u"]):
            if flags and command[:2] != [sys.executable, "-m"]:
                continue
            output_command = command if not flags else [command[0], *flags, *command[1:]]
            result = subprocess.run(
                output_command + ["--fixture", "complaint"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
                preexec_fn=lambda: os.close(1), timeout=10,
            )
            checks += 1
            assert result.returncode == 1 and b"Traceback" not in result.stderr, (result.returncode, result.stderr)

        help_result = subprocess.run(command + ["--help"], capture_output=True, env=environment, timeout=10)
        checks += 1
        assert help_result.returncode == 0 and b"usage:" in help_result.stdout and not help_result.stderr
        for flags in ([], ["-u"]):
            if flags and command[:2] != [sys.executable, "-m"]:
                continue
            output_command = command if not flags else [command[0], *flags, *command[1:]]
            closed = subprocess.run(
                output_command + ["--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=environment, preexec_fn=lambda: os.close(1), timeout=10,
            )
            checks += 1
            assert closed.returncode == 1 and b"Traceback" not in closed.stderr, (closed.returncode, closed.stderr)
            read_descriptor, write_descriptor = os.pipe()
            os.close(read_descriptor)
            try:
                help_result = subprocess.run(
                    output_command + ["--help"], stdout=write_descriptor,
                    stderr=subprocess.PIPE, env=environment, timeout=10,
                )
            finally:
                os.close(write_descriptor)
            checks += 1
            assert help_result.returncode == 1 and b"Exception ignored" not in help_result.stderr and b"Traceback" not in help_result.stderr, (help_result.returncode, help_result.stderr)

        read_descriptor, write_descriptor = os.pipe()
        os.close(read_descriptor)
        try:
            broken = subprocess.run(
                command + ["--fixture", "complaint"], stdout=write_descriptor,
                stderr=subprocess.PIPE, env=environment, timeout=10,
            )
        finally:
            os.close(write_descriptor)
        checks += 1
        assert broken.returncode == 1 and b"Traceback" not in broken.stderr, (broken.returncode, broken.stderr)

        if args.package_dir is not None:
            clone_root = base / "isolated-package"
            clone = clone_root / "audio_processing"
            shutil.copytree(args.package_dir, clone, ignore=shutil.ignore_patterns("__pycache__"))
            fault_environment = dict(environment, PYTHONPATH=str(clone_root))
            for name in ("manifest.json", "complaint.wav", "silence.wav"):
                resource = clone / "data" / name
                original = resource.read_bytes()
                for kind in ("fifo", "directory", "symlink", "missing"):
                    resource.unlink()
                    if kind == "fifo":
                        os.mkfifo(resource)
                    elif kind == "directory":
                        resource.mkdir()
                    elif kind == "symlink":
                        resource.symlink_to(private)
                    fault = subprocess.run(command + ["--fixture", "complaint"], capture_output=True, env=fault_environment, timeout=5)
                    checks += 1
                    assert fault.returncode == 3 and b"Traceback" not in fault.stderr, (name, kind, fault.returncode, fault.stderr)
                    value = json.loads(fault.stdout)
                    assert value["kind"] == "rejected" and value["code"] == "invalid_assets", value
                    assert str(clone_root) not in json.dumps(value)
                    if kind == "directory":
                        resource.rmdir()
                    elif kind != "missing":
                        resource.unlink()
                    resource.write_bytes(original)

    print(json.dumps({"result": "passed", "cli_invocations": checks, "mode": "fixture", "imports_agent_internals": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
