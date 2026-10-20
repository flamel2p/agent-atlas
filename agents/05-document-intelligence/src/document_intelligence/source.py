"""Public extraction boundary for strict token JSON or explicitly ordered images.

Only regular caller-selected files are read. Byte/type/geometry/count validation
creates immutable records before policy runs. Fixture mode never imports Pillow
or starts OCR. Source hashes identify the exact bytes read, not semantic equality.
"""

from dataclasses import dataclass
import hashlib
from importlib.resources import files
import json
import math
import os
from pathlib import Path
import stat
from typing import TypeAlias

from .invoice import Box, Document, InvoiceError, InvoiceReport, Page, Token, extract_document

MAX_BYTES = 8 * 1024 * 1024
MAX_PAGES = 3
MAX_TOKENS = 5000
MAX_TEXT = 256


@dataclass(frozen=True)
class TokenFile:
    path: Path


@dataclass(frozen=True)
class Example:
    name: str


@dataclass(frozen=True)
class ImagePages:
    """Image order is page order; no discovery or directory traversal occurs."""

    paths: tuple[Path, ...]


Source: TypeAlias = TokenFile | Example | ImagePages
EXAMPLES = ("clean", "conflicting-total", "weak-label")


def read_regular(path: Path, remaining: int) -> bytes:
    """O_NOFOLLOW closes a final-component symlink race; O_NONBLOCK avoids FIFOs."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise InvoiceError("unsupported_file")
            if metadata.st_size > remaining:
                raise InvoiceError("input_limit")
            data = stream.read(remaining + 1)
            if len(data) > remaining:
                raise InvoiceError("input_limit")
            return data
    except (OSError, ValueError):
        raise InvoiceError("input_unreadable") from None


def _keys(value: object, expected: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise InvoiceError("invalid_schema")
    return value


def _integer(value: object, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise InvoiceError("invalid_schema")
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvoiceError("duplicate_json_key")
        result[key] = value
    return result


def _nonfinite(_: str) -> None:
    raise InvoiceError("invalid_schema")


def page_from_data(raw: object, number: int) -> Page:
    """Validate the common ledger schema for JSON and normalized OCR word rows."""
    page = _keys(raw, {"number", "width", "height", "tokens"})
    if _integer(page["number"]) != number:
        raise InvoiceError("invalid_page_order")
    width, height = _integer(page["width"]), _integer(page["height"])
    if not isinstance(page["tokens"], list):
        raise InvoiceError("invalid_schema")
    if len(page["tokens"]) > MAX_TOKENS:
        raise InvoiceError("token_limit")
    tokens, identifiers = [], set()
    for raw_token in page["tokens"]:
        item = _keys(raw_token, {"id", "text", "line_key", "bbox", "ocr_score"})
        identifier, text = item["id"], item["text"]
        if not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 64:
            raise InvoiceError("invalid_schema")
        if identifier in identifiers:
            raise InvoiceError("duplicate_token_id")
        identifiers.add(identifier)
        if not isinstance(text, str) or not text.strip():
            raise InvoiceError("invalid_schema")
        if len(text) > MAX_TEXT:
            raise InvoiceError("text_limit")
        key = item["line_key"]
        if not isinstance(key, list) or len(key) != 3:
            raise InvoiceError("invalid_schema")
        line_key = tuple(_integer(value) for value in key)
        raw_box = item["bbox"]
        if not isinstance(raw_box, list) or len(raw_box) != 4:
            raise InvoiceError("invalid_schema")
        left, top, right, bottom = (_integer(value, 0) for value in raw_box)
        if not 0 <= left < right <= width or not 0 <= top < bottom <= height:
            raise InvoiceError("invalid_geometry")
        score = item["ocr_score"]
        if score is not None and (type(score) not in (int, float) or not 0 <= score <= 100 or not math.isfinite(score)):
            raise InvoiceError("invalid_score")
        tokens.append(Token(identifier, text, line_key, Box(left, top, right, bottom), float(score) if score is not None else None))
    # Canonical order makes policy/evidence invariant to input token ordering.
    tokens.sort(key=lambda t: (*t.line_key, t.bbox.left, t.bbox.top, t.id))
    return Page(number, width, height, tuple(tokens))


def _json_document(data: bytes) -> Document:
    try:
        raw = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    except (ValueError, UnicodeError, RecursionError):
        raise InvoiceError("invalid_json") from None
    root = _keys(raw, {"schema_version", "pages"})
    if type(root["schema_version"]) is not int or root["schema_version"] != 1:
        raise InvoiceError("invalid_schema")
    raw_pages = root["pages"]
    if not isinstance(raw_pages, list):
        raise InvoiceError("invalid_schema")
    if not 1 <= len(raw_pages) <= MAX_PAGES:
        raise InvoiceError("page_limit")
    pages = tuple(page_from_data(page, index) for index, page in enumerate(raw_pages, 1))
    if sum(len(page.tokens) for page in pages) > MAX_TOKENS:
        raise InvoiceError("token_limit")
    return Document("fixture", (hashlib.sha256(data).hexdigest(),), pages)


def extract_invoice(source: Source) -> InvoiceReport:
    """Validate one source, run bounded perception once, then apply pure policy.

    Raises InvoiceError with a stable code on failure; no partial report escapes.
    KeyboardInterrupt remains observable to callers and is sanitized by the CLI.
    """
    if isinstance(source, Example):
        if source.name not in EXAMPLES:
            raise InvoiceError("unknown_example")
        data = files("document_intelligence").joinpath("fixtures", f"{source.name}.json").read_bytes()
        if len(data) > MAX_BYTES:
            raise InvoiceError("input_limit")
        document = _json_document(data)
    elif isinstance(source, TokenFile):
        if not isinstance(source.path, Path) or source.path.suffix.lower() != ".json":
            raise InvoiceError("unsupported_file")
        document = _json_document(read_regular(source.path, MAX_BYTES))
    elif isinstance(source, ImagePages):
        if not isinstance(source.paths, tuple) or not 1 <= len(source.paths) <= MAX_PAGES:
            raise InvoiceError("page_limit")
        snapshots = []
        used = 0
        for path in source.paths:
            if not isinstance(path, Path) or path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                raise InvoiceError("unsupported_file")
            data = read_regular(path, MAX_BYTES - used)
            snapshots.append(data)
            used += len(data)
        from .ocr import image_document
        document = image_document(tuple(snapshots))
    else:
        raise InvoiceError("invalid_source")
    return extract_document(document)
