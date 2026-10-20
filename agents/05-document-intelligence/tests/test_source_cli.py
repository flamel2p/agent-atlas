"""Ingress and CLI failures must never expose a partial accepted record."""

from copy import deepcopy
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path

import pytest

from document_intelligence import Example, ImagePages, InvoiceError, TokenFile, extract_invoice
from document_intelligence.cli import main
from document_intelligence.source import MAX_BYTES


@pytest.mark.parametrize("body,code", [
    (b'{"schema_version":1,"schema_version":1,"pages":[]}', "duplicate_json_key"),
    (b'{"schema_version":1,"pages":[],"other":1}', "invalid_schema"),
    (b'{"schema_version":true,"pages":[]}', "invalid_schema"),
    (b'{"schema_version":1,"pages":NaN}', "invalid_schema"),
    pytest.param(b"[" * 2000 + b"]" * 2000, "invalid_schema", id="deep-container"),
    (b"\xff", "invalid_json"), (b"not JSON", "invalid_json"),
])
def test_malformed_json(tmp_path, body, code):
    path = tmp_path / "invoice.json"
    path.write_bytes(body)
    with pytest.raises(InvoiceError, match=f"^{code}$"):
        extract_invoice(TokenFile(path))


@pytest.mark.parametrize("key,value,code", [
    ("ocr_score", True, "invalid_score"), ("ocr_score", -1, "invalid_score"),
    ("ocr_score", 101, "invalid_score"), ("ocr_score", 10 ** 400, "invalid_score"),
    ("ocr_score", float("inf"), "invalid_schema"),
    ("ocr_score", float("nan"), "invalid_schema"), ("text", "", "invalid_schema"),
    ("text", "x" * 257, "text_limit"), ("id", " ", "invalid_schema"),
    ("line_key", [1, False, 1], "invalid_schema"), ("bbox", [1, 2, 1, 3], "invalid_geometry"),
    ("bbox", [1, 2, 1201, 3], "invalid_geometry"), ("bbox", [0, 0, 1, True], "invalid_schema"),
])
def test_token_boundary_rejects_bad_data(clean, extract, key, value, code):
    clean["pages"][0]["tokens"][0][key] = value
    with pytest.raises(InvoiceError, match=f"^{code}$"):
        extract(clean)


@pytest.mark.parametrize("mutation,code", [
    (lambda p: p["pages"][0].update(width=True), "invalid_schema"),
    (lambda p: p["pages"][0].update(number=2), "invalid_page_order"),
    (lambda p: p["pages"][0]["tokens"][0].update(extra=1), "invalid_schema"),
    (lambda p: p["pages"][0]["tokens"].append(deepcopy(p["pages"][0]["tokens"][0])), "duplicate_token_id"),
    (lambda p: p.update(pages=[]), "page_limit"),
    (lambda p: p.update(pages=p["pages"] * 4), "page_limit"),
])
def test_document_shape_limits(clean, extract, mutation, code):
    mutation(clean)
    with pytest.raises(InvoiceError, match=f"^{code}$"):
        extract(clean)


def test_total_token_limit_across_pages(clean, extract):
    template = clean["pages"][0]
    clean["pages"] = []
    for number in (1, 2):
        page = deepcopy(template)
        page["number"] = number
        page["tokens"] = []
        for index in range(2501):
            token = deepcopy(template["tokens"][0])
            token["id"] = str(index)
            page["tokens"].append(token)
        clean["pages"].append(page)
    with pytest.raises(InvoiceError, match="^token_limit$"):
        extract(clean)


def test_oversized_file_and_special_file_are_rejected(tmp_path):
    path = tmp_path / "large.json"
    with path.open("wb") as stream:
        stream.truncate(MAX_BYTES + 1)
    with pytest.raises(InvoiceError, match="^input_limit$"):
        extract_invoice(TokenFile(path))
    fifo = tmp_path / "fifo.json"
    os.mkfifo(fifo)
    with pytest.raises(InvoiceError, match="^unsupported_file$"):
        extract_invoice(TokenFile(fifo))


def test_symlink_directory_and_unsupported_files(tmp_path):
    path = tmp_path / "invoice.json"
    path.write_text("{}")
    symlink = tmp_path / "link.json"
    symlink.symlink_to(path)
    for source in (TokenFile(symlink), TokenFile(tmp_path), ImagePages((tmp_path / "invoice.pdf",))):
        with pytest.raises(InvoiceError):
            extract_invoice(source)


@pytest.mark.parametrize("source", [TokenFile(Path("invoice\x00.json")), ImagePages((Path("invoice\x00.png"),))])
def test_invalid_path_is_sanitized_at_public_api(source):
    with pytest.raises(InvoiceError, match="^input_unreadable$"):
        extract_invoice(source)


def test_image_input_total_byte_and_page_bounds(tmp_path):
    paths = tuple(tmp_path / f"{i}.png" for i in range(2))
    for path in paths:
        with path.open("wb") as stream:
            stream.truncate(MAX_BYTES // 2 + 1)
    with pytest.raises(InvoiceError, match="^input_limit$"):
        extract_invoice(ImagePages(paths))
    for sequence in ((), paths * 2):
        with pytest.raises(InvoiceError, match="^page_limit$"):
            extract_invoice(ImagePages(sequence))


def test_source_hash_is_exact_input_bytes(tmp_path, clean):
    data = json.dumps(clean).encode()
    path = tmp_path / "invoice.json"
    path.write_bytes(data)
    assert extract_invoice(TokenFile(path)).document.source_sha256 == (hashlib.sha256(data).hexdigest(),)


@pytest.mark.parametrize("args,code,status", [
    (["--example", "clean"], 0, "extracted"),
    (["--example", "conflicting-total"], 2, "review_required"),
    (["--example", "weak-label"], 2, "review_required"),
    ([], 1, "error"), (["--example", "private invoice contents"], 1, "error"),
    (["--example", "clean", "--tokens", "file.json"], 1, "error"),
])
def test_cli_exit_status_and_sanitized_errors(args, code, status, capsys):
    assert main(args) == code
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == status
    assert captured.err == ""
    if code == 1:
        assert result == {"status": "error", "error": {"code": "invalid_arguments"}}


@pytest.mark.parametrize("exception,code,error", [(KeyboardInterrupt(), 130, "cancelled"), (RuntimeError("PRIVATE INVOICE"), 1, "processing_error")])
def test_cli_sanitizes_interrupt_and_unexpected_failure(monkeypatch, capsys, exception, code, error):
    def fail(_):
        raise exception
    monkeypatch.setattr("document_intelligence.cli.extract_invoice", fail)
    assert main(["--example", "clean"]) == code
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == error
    assert "record" not in result


def test_fixture_mode_never_invokes_ocr(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("OCR invoked for fixture")
    monkeypatch.setattr("subprocess.Popen", fail)
    assert extract_invoice(Example("clean")).status == "extracted"
