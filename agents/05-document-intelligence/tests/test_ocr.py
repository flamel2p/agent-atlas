"""Fake native processes qualify limits and cleanup, never OCR recognition."""

from importlib.resources import files
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from PIL import Image
import pytest

from document_intelligence import ImagePages, InvoiceError, extract_invoice
from document_intelligence import ocr

pytestmark = pytest.mark.mocked_ocr


@pytest.fixture
def image_path(tmp_path):
    path = tmp_path / "invoice.png"
    path.write_bytes(files("document_intelligence").joinpath("fixtures", "invoice.png").read_bytes())
    return path


@pytest.fixture
def tsv(clean):
    lines = ["\t".join(ocr.HEADER), "1\t1\t0\t0\t0\t0\t0\t0\t1200\t800\t-1\t"]
    for index, token in enumerate(clean["pages"][0]["tokens"], 1):
        left, top, right, bottom = token["bbox"]
        lines.append("\t".join(map(str, [5, 1, *token["line_key"], index, left, top, right-left, bottom-top, token["ocr_score"], token["text"]])))
    return ("\n".join(lines) + "\n").encode()


@pytest.fixture
def processes(monkeypatch):
    created = []
    original = subprocess.Popen
    def start(*args, **kwargs):
        process = original(*args, **kwargs)
        created.append(process)
        return process
    monkeypatch.setattr(ocr.subprocess, "Popen", start)
    yield created
    for process in created:
        assert process.poll() is not None
        assert all(stream.closed for stream in (process.stdin, process.stdout, process.stderr))
        with pytest.raises(ChildProcessError):
            os.waitpid(process.pid, os.WNOHANG)


def fake_executable(tmp_path, monkeypatch, body):
    executable = tmp_path / "fake-tesseract"
    executable.write_text(f"#!{sys.executable}\n" + body)
    executable.chmod(0o700)
    monkeypatch.setattr(ocr.shutil, "which", lambda name: str(executable) if name == "tesseract" else None)
    return executable


def test_full_image_adapter_fixed_args_and_tsv_ledger(tmp_path, monkeypatch, image_path, tsv, processes):
    fake_executable(tmp_path, monkeypatch, f"""
import sys
args = sys.argv[1:]
if args == ['--version']:
    print('tesseract 5.5.0')
elif args == ['--list-langs']:
    print('List of available languages (1):\\neng')
elif args == ['stdin', 'stdout', '-l', 'eng', '--psm', '6', 'tsv']:
    data = sys.stdin.buffer.read()
    assert data.startswith(b'\\x89PNG')
    sys.stdout.buffer.write({tsv!r})
else:
    raise SystemExit(7)
""")
    before = set(tmp_path.iterdir())
    report = extract_invoice(ImagePages((image_path, image_path)))
    assert report.status == "extracted"
    assert report.document.source_mode == "local_ocr"
    assert report.document.engine == "tesseract 5.5.0"
    assert report.record["total_myr"] == "1234.50"
    assert len(report.total_myr.candidates) == 2
    assert report.total_myr.candidates[1].evidence.page == 2
    assert len(processes) == 4
    assert set(tmp_path.iterdir()) == before


def test_missing_binary_does_not_fall_back(monkeypatch, image_path):
    monkeypatch.setattr(ocr.shutil, "which", lambda _: None)
    with pytest.raises(InvoiceError, match="^ocr_unavailable$"):
        extract_invoice(ImagePages((image_path,)))


@pytest.mark.parametrize("body,code", [
    ("import sys; sys.stderr.write('PRIVATE INVOICE'); sys.exit(2)", "ocr_failed"),
    ("import sys; sys.stdout.buffer.write(b'x' * (2 * 1024 * 1024 + 1))", "ocr_output_limit"),
    ("import sys; sys.stderr.buffer.write(b'x' * (64 * 1024 + 1))", "ocr_output_limit"),
    ("import time; time.sleep(60)", "ocr_timeout"),
    ("import sys,time; print('valid output', flush=True); sys.stdout.close(); time.sleep(60)", "ocr_timeout"),
])
def test_process_failure_bounds_reap_and_close(body, code, monkeypatch, processes):
    monkeypatch.setattr(ocr, "PROCESS_SECONDS", 0.3)
    with pytest.raises(InvoiceError, match=f"^{code}$"):
        ocr._run([sys.executable, "-c", body], b"", time.monotonic() + 5)
    assert len(processes) == 1


def test_overall_deadline_shortens_page_timeout(processes):
    start = time.monotonic()
    with pytest.raises(InvoiceError, match="^ocr_timeout$"):
        ocr._run([sys.executable, "-c", "import time; time.sleep(60)"], b"", start + 0.15)
    assert time.monotonic() - start < 2


def test_expired_stage_never_starts_next_process(processes):
    with pytest.raises(InvoiceError, match="^ocr_timeout$"):
        ocr._run([sys.executable, "-c", "pass"], b"", time.monotonic() - 1)
    assert processes == []


def test_cancellation_reaps_process_and_closes_pipes(monkeypatch, processes):
    def cancel(*args, **kwargs):
        raise KeyboardInterrupt()
    monkeypatch.setattr(ocr.selectors.DefaultSelector, "select", cancel)
    with pytest.raises(KeyboardInterrupt):
        ocr._run([sys.executable, "-c", "import time; time.sleep(60)"], b"", time.monotonic() + 5)
    assert len(processes) == 1


def test_adapter_error_reaps_process_and_closes_pipes(monkeypatch, processes):
    def fail(*args, **kwargs):
        raise OSError("private failure detail")
    monkeypatch.setattr(ocr.os, "set_blocking", fail)
    with pytest.raises(InvoiceError, match="^ocr_failed$"):
        ocr._run([sys.executable, "-c", "import time; time.sleep(60)"], b"", time.monotonic() + 5)


def test_simultaneous_input_and_output_do_not_deadlock(processes):
    payload = b"a" * 300_000
    body = "import sys; sys.stdout.buffer.write(b'x'*200000); sys.stdout.flush(); sys.stdout.buffer.write(sys.stdin.buffer.read())"
    assert ocr._run([sys.executable, "-c", body], payload, time.monotonic() + 5) == b"x" * 200_000 + payload


@pytest.mark.parametrize("transform", [
    lambda data: b"wrong header\n", lambda data: data + b"malformed row\n",
    lambda data: data.replace(b"5\t1\t", b"5\t2\t", 1),
    lambda data: data.replace(b"\t98\t", b"\tnan\t", 1),
    lambda data: data.replace(b"\t98\t", b"\t101\t", 1),
    lambda data: data.replace(b"\tInvoice\n", b"\t" + b"x" * 257 + b"\n", 1),
    lambda data: data.replace(b"\t40\t90\t", b"\t1199\t90\t", 1),
    lambda data: data.replace(b"\t1200\t800\t-1\t", b"\t1201\t800\t-1\t", 1),
])
def test_malformed_tsv_is_rejected(tsv, transform):
    with pytest.raises(InvoiceError):
        ocr._parse_tsv(transform(tsv), 1, (1200, 800))


def test_missing_word_score_survives_tsv(tsv):
    page = ocr._parse_tsv(tsv.replace(b"\t98\t", b"\t-1\t", 1), 1, (1200, 800))
    assert len(page.tokens) == 10
    assert page.tokens[0].ocr_score is None


@pytest.mark.parametrize("response,code", [(b"not tesseract", "invalid_ocr_version"), (b"tesseract 5.5.0\n", "ocr_language_unavailable")])
def test_metadata_and_english_prerequisite(monkeypatch, image_path, response, code):
    monkeypatch.setattr(ocr.shutil, "which", lambda _: "/fixed/tesseract")
    monkeypatch.setattr(ocr, "_run", lambda *args: response)
    with pytest.raises(InvoiceError, match=f"^{code}$"):
        extract_invoice(ImagePages((image_path,)))


@pytest.mark.parametrize("kind,code", [("unsupported", "invalid_image"), ("orientation", "image_orientation"), ("multiframe", "multiframe_image"), ("pixels", "pixel_limit")])
def test_image_boundary_before_process(kind, code, tmp_path, processes):
    path = tmp_path / "test.png"
    if kind == "unsupported":
        path.write_bytes(b"not an image")
    elif kind == "orientation":
        image = Image.new("RGB", (20, 20))
        exif = Image.Exif()
        exif[274] = 6
        image.save(path, exif=exif)
    elif kind == "multiframe":
        image = Image.new("RGB", (20, 20))
        image.save(path, save_all=True, append_images=[Image.new("RGB", (20, 20), "red")])
    else:
        Image.new("1", (4001, 3000)).save(path)
    with pytest.raises(InvoiceError, match=f"^{code}$"):
        extract_invoice(ImagePages((path,)))
    assert processes == []


def test_input_snapshot_used_after_path_changes(tmp_path, monkeypatch, image_path, tsv):
    original_bytes = image_path.read_bytes()
    seen = []
    def call(args, data, deadline, *limits):
        if args[-1] == "--version":
            image_path.write_bytes(b"replaced after bounded read")
            return b"tesseract 5.5.0\n"
        if args[-1] == "--list-langs":
            return b"eng\n"
        seen.append(data)
        return tsv
    monkeypatch.setattr(ocr.shutil, "which", lambda _: "/fixed/tesseract")
    monkeypatch.setattr(ocr, "_run", call)
    report = extract_invoice(ImagePages((image_path,)))
    assert report.status == "extracted"
    assert seen == [original_bytes]
