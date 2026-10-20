"""Synthetic invoice builders shared by contract tests; never recognized OCR."""

from copy import deepcopy
from importlib.resources import files
import json

import pytest

from document_intelligence import TokenFile, extract_invoice


@pytest.fixture
def clean():
    return json.loads(files("document_intelligence").joinpath("fixtures", "clean.json").read_bytes())


@pytest.fixture
def extract(tmp_path):
    def run(payload):
        path = tmp_path / "invoice.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return extract_invoice(TokenFile(path))
    return run


def add_page(payload, *, value="MYR 1,234.50", score=98):
    page = deepcopy(payload["pages"][0])
    page["number"] = len(payload["pages"]) + 1
    page["tokens"] = [t for t in page["tokens"] if t["line_key"][2] == 3]
    page["tokens"][-2]["text"], page["tokens"][-1]["text"] = value.split(" ", 1)
    page["tokens"][-1]["ocr_score"] = score
    payload["pages"].append(page)


def set_total(payload, value):
    tokens = payload["pages"][0]["tokens"]
    tokens[-2]["text"] = value
    tokens[-2]["bbox"][2] = tokens[-1]["bbox"][2]
    tokens.pop()
