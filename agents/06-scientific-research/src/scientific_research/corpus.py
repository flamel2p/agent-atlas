"""Validate one synthetic corpus snapshot and resolve duplicate records.

The parser owns the only conversion from untrusted JSON to immutable domain data.
It preserves abstracts verbatim so later citation offsets refer to this snapshot.
The SHA256 digest identifies original input bytes, not a scientific source.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import unicodedata

MAX_CORPUS_BYTES = 1_048_576
MAX_RECORDS = 80
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class InputError(ValueError):
    """A caller-supplied corpus or request failed the public contract."""


@dataclass(frozen=True)
class Paper:
    """A canonical synthetic record; abstract is raw Unicode source text."""

    paper_id: str
    title: str
    abstract: str
    authors: tuple[str, ...]
    year: int
    source: str
    source_id: str
    synthetic: bool


@dataclass(frozen=True)
class DuplicateDecision:
    """Content-identical records removed in favor of the smallest paper ID."""

    retained_id: str
    alias_ids: tuple[str, ...]


@dataclass(frozen=True)
class Corpus:
    """One invocation's validated, canonicalized corpus and byte provenance."""

    corpus_id: str
    papers: tuple[Paper, ...]
    original_record_count: int
    duplicates: tuple[DuplicateDecision, ...]
    sha256: str


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise InputError("non-finite JSON number")


def _fields(value: object, expected: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise InputError("invalid object fields")
    return value


def _text(value: object, *, maximum: int, identifier: bool = False) -> str:
    if type(value) is not str or not value or len(value) > maximum or not value.strip():
        raise InputError("invalid text field")
    # A control in untrusted metadata can alter terminal output even inside JSON.
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value):
        raise InputError("control character in text")
    if identifier and _ID.fullmatch(value) is None:
        raise InputError("invalid identifier")
    return value


def _paper(raw: object) -> Paper:
    obj = _fields(raw, {"paper_id", "title", "abstract", "authors", "year", "source", "source_id", "synthetic"})
    authors = obj["authors"]
    if type(authors) is not list or not 1 <= len(authors) <= 12:
        raise InputError("invalid authors")
    year = obj["year"]
    if type(year) is not int or not 1 <= year <= 9999:
        raise InputError("invalid year")
    if obj["synthetic"] is not True:
        raise InputError("only synthetic records are accepted")
    return Paper(
        paper_id=_text(obj["paper_id"], maximum=64, identifier=True),
        title=_text(obj["title"], maximum=300),
        abstract=_text(obj["abstract"], maximum=8_000),
        authors=tuple(_text(author, maximum=120) for author in authors),
        year=year,
        source=_text(obj["source"], maximum=120),
        source_id=_text(obj["source_id"], maximum=120),
        synthetic=True,
    )


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def parse_corpus(raw: bytes) -> Corpus:
    """Parse <=1 MiB strict UTF-8 JSON; reject identity conflicts before dedupe."""

    if type(raw) is not bytes or len(raw) > MAX_CORPUS_BYTES:
        raise InputError("corpus byte limit exceeded or invalid bytes")
    try:
        decoded = raw.decode("utf-8")
        obj = json.loads(decoded, object_pairs_hook=_object_pairs, parse_constant=_reject_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise InputError("invalid JSON corpus") from exc
    root = _fields(obj, {"schema_version", "corpus_id", "papers"})
    if type(root["schema_version"]) is not int or root["schema_version"] != 1:
        raise InputError("unsupported schema version")
    corpus_id = _text(root["corpus_id"], maximum=64, identifier=True)
    records = root["papers"]
    if type(records) is not list or len(records) > MAX_RECORDS:
        raise InputError("invalid paper count")
    parsed = tuple(_paper(record) for record in records)
    by_id: dict[str, Paper] = {}
    for paper in parsed:
        prior = by_id.get(paper.paper_id)
        if prior is not None and prior != paper:
            raise InputError("conflicting paper identity")
        by_id[paper.paper_id] = paper

    # Content dedupe is a lexical heuristic; distinct metadata may still be aliases.
    groups: dict[tuple[str, int, str], list[Paper]] = {}
    for paper in by_id.values():
        key = (_normalized(paper.title), paper.year, _normalized(paper.abstract))
        groups.setdefault(key, []).append(paper)
    retained: list[Paper] = []
    duplicates: list[DuplicateDecision] = []
    for group in groups.values():
        group.sort(key=lambda paper: paper.paper_id)
        retained.append(group[0])
        if len(group) > 1:
            duplicates.append(DuplicateDecision(group[0].paper_id, tuple(p.paper_id for p in group[1:])))
    return Corpus(
        corpus_id=corpus_id,
        papers=tuple(sorted(retained, key=lambda paper: paper.paper_id)),
        original_record_count=len(parsed),
        duplicates=tuple(sorted(duplicates, key=lambda item: item.retained_id)),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
