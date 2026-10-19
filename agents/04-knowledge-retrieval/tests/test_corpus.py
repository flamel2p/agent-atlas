from datetime import date
import json

import pytest

from knowledge_agent.contracts import AgentError, Request
from knowledge_agent.corpus import MAX_CORPUS_BYTES, eligible, passages, validate_corpus

from conftest import encoded


def test_unicode_offsets_and_optional_end(document):
    document.pop("effective_until")
    document["text"] = "Café 订阅 cancellation.\n\nSecond paragraph."
    source = validate_corpus(encoded([document])).documents[0]
    parts = passages(source)
    assert len(parts) == 2
    assert parts[1].start == len("Café 订阅 cancellation.\n\n")
    assert parts[1].text == source.text[parts[1].start:parts[1].end] == "Second paragraph."


@pytest.mark.parametrize("raw", [
    b"", b"{", b"\xff", b"null", b"[]", b"{}", b" " * (MAX_CORPUS_BYTES + 1),
    b'{"schema_version":1,"schema_version":1,"documents":[]}',
    b'{"schema_version":1,"documents":[],"extra":true}',
    b'{"schema_version":true,"documents":[]}',
    b'{"schema_version":2,"documents":[]}',
    b'{"schema_version":1,"documents":[]}',
    b'{"schema_version":1,"documents":NaN}',
    b'{"schema_version":1,"documents":null}',
    b"[" * 2000,
])
def test_corrupt_corpus_fails_closed(raw):
    with pytest.raises(AgentError, match="^invalid_corpus$"):
        validate_corpus(raw)


@pytest.mark.parametrize(("field", "value"), [
    ("id", "../escape"), ("id", "a" * 65), ("id", None),
    ("title", ""), ("title", "x" * 121), ("title", "line\nbreak"),
    ("revision", "x" * 65), ("revision", 3), ("product", "X atlas"),
    ("product", "a" * 33), ("version", "x" * 33), ("version", []),
    ("audience", "admin"), ("audience", []), ("effective_from", "2026-10-1"),
    ("effective_from", "2026-02-30"), ("effective_from", 123),
    ("effective_until", "2026-10-01"), ("effective_until", "2026-09-30"),
    ("reviewed_at", "2026-13-01"), ("text", ""), ("text", "   "),
    ("text", "x" * 601), ("text", "x" * 9601), ("text", "\n\nbody"),
    ("text", "body\n\n"), ("text", "\n\n".join("p" for _ in range(17))),
    ("text", "a\x00b"), ("text", "\ud800"),
    ("text", "x" * 600 + "\n \n" + "x" * 600),
])
def test_invalid_document_metadata_and_bounds(document, field, value):
    document[field] = value
    with pytest.raises(AgentError, match="^invalid_corpus$"):
        validate_corpus(encoded([document]))


@pytest.mark.parametrize("field", ["id", "title", "revision", "product", "version", "audience",
                                   "effective_from", "reviewed_at", "text"])
def test_missing_fields(document, field):
    document.pop(field)
    with pytest.raises(AgentError, match="invalid_corpus"):
        validate_corpus(encoded([document]))


def test_unknown_fields_duplicate_ids_and_keys(document):
    with pytest.raises(AgentError):
        validate_corpus(encoded([{**document, "hidden": "not accepted"}]))
    with pytest.raises(AgentError):
        validate_corpus(encoded([document, document]))
    raw = encoded([document]).replace(b'"revision": "r1"', b'"revision":"r1","revision":"r2"')
    with pytest.raises(AgentError):
        validate_corpus(raw)


def test_max_documents_and_paragraphs(document):
    document["text"] = "\n\n".join("x" * 500 for _ in range(16))
    assert len(passages(validate_corpus(encoded([document])).documents[0])) == 16
    document["text"] = "Cancel subscription."
    docs = [{**document, "id": f"d-{i}"} for i in range(32)]
    assert len(validate_corpus(encoded(docs)).documents) == 32
    with pytest.raises(AgentError):
        validate_corpus(encoded(docs + [{**document, "id": "d-33"}]))


@pytest.mark.parametrize(("changes", "expected"), [
    ({}, True), ({"audience": "staff"}, False), ({"version": "1.0"}, False),
    ({"product": "other"}, False), ({"effective_from": "2026-10-19"}, True),
    ({"effective_from": "2026-10-20"}, False), ({"effective_until": "2026-10-19"}, False),
    ({"effective_until": "2026-10-20"}, True), ({"reviewed_at": "2026-10-19"}, True),
    ({"reviewed_at": "2026-10-20"}, False), ({"reviewed_at": "2026-07-21"}, True),
    ({"reviewed_at": "2026-07-20"}, False),
])
def test_eligibility_date_and_scope_boundaries(document, changes, expected):
    snapshot = validate_corpus(encoded([{**document, **changes}]))
    request = Request.validate("cancel", as_of="2026-10-19")
    assert bool(eligible(snapshot, request)) is expected
    assert request.as_of == date(2026, 10, 19)


def test_staff_includes_public_and_staff(document):
    snapshot = validate_corpus(encoded([document, {**document, "id": "staff", "audience": "staff"}]))
    request = Request.validate("cancel", audience="staff", as_of="2026-10-19")
    assert {item.id for item in eligible(snapshot, request)} == {"policy", "staff"}


def test_snapshot_digest_is_exact_bytes(document):
    compact = encoded([document])
    spaced = json.dumps(json.loads(compact), indent=4).encode()
    first, second = validate_corpus(compact), validate_corpus(spaced)
    assert first.documents == second.documents
    assert first.digest != second.digest
