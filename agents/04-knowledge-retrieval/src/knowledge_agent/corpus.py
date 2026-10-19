"""Load a bounded source snapshot and filter it before any retrieval or exposure.

Documents own exact text; passages identify paragraph slices within that text.
All resources are packaged with this case, with no user-supplied file paths.
"""

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from importlib.resources import files
import re
import unicodedata

from .contracts import AgentError, Request, VERSION, iso_date, safe_string, strict_json


MAX_CORPUS_BYTES = 128 * 1024
DOCUMENT_FIELDS = {
    "id", "title", "revision", "product", "version", "audience", "effective_from",
    "effective_until", "reviewed_at", "text",
}
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
SEPARATOR = re.compile(r"\n[ \t]*\n")


@dataclass(frozen=True, slots=True)
class Document:
    """Validated source text plus metadata used for eligibility and citation."""

    id: str
    title: str
    revision: str
    product: str
    version: str
    audience: str
    effective_from: date
    effective_until: date | None
    reviewed_at: date
    text: str


@dataclass(frozen=True, slots=True)
class Passage:
    """One complete paragraph, addressed by half-open Python character offsets.

    ``start:end`` indexes Unicode characters, not UTF-8 bytes or model tokens.
    Text is derived from the document so quotations cannot drift independently.
    """

    document: Document
    index: int
    start: int
    end: int

    @property
    def id(self) -> str:
        return f"{self.document.id}:p{self.index + 1}"

    @property
    def text(self) -> str:
        return self.document.text[self.start:self.end]


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Immutable validated documents and a SHA-256 digest of their original bytes."""

    digest: str
    documents: tuple[Document, ...]


def passages(document: Document) -> tuple[Passage, ...]:
    """Locate paragraphs without rewriting whitespace or losing source offsets.

    Corpus validation rejects blank/oversize spans; this helper only splits them.
    """
    spans = []
    start = 0
    for separator in SEPARATOR.finditer(document.text):
        spans.append((start, separator.start()))
        start = separator.end()
    spans.append((start, len(document.text)))
    return tuple(Passage(document, i, start, end) for i, (start, end) in enumerate(spans))


def load_bundled() -> bytes:
    """Read one byte beyond the size cap so validation can detect an oversize file."""
    with files("knowledge_agent").joinpath("resources/corpus.json").open("rb") as stream:
        return stream.read(MAX_CORPUS_BYTES + 1)


def validate_corpus(raw: bytes) -> Snapshot:
    """Reject the entire snapshot on malformed metadata, text, or paragraph bounds.

    No partially validated documents reach ranking. The digest identifies the
    exact input bytes, so even a formatting-only corpus edit changes provenance.
    """
    try:
        if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_CORPUS_BYTES:
            raise ValueError
        root = strict_json(raw.decode("utf-8"))
        if not isinstance(root, dict) or set(root) != {"schema_version", "documents"}:
            raise ValueError
        if type(root["schema_version"]) is not int or root["schema_version"] != 1:
            raise ValueError
        entries = root["documents"]
        if not isinstance(entries, list) or not 1 <= len(entries) <= 32:
            raise ValueError
        documents, ids = [], set()
        for entry in entries:
            if not isinstance(entry, dict) or not (
                DOCUMENT_FIELDS - {"effective_until"} <= set(entry) <= DOCUMENT_FIELDS
            ):
                raise ValueError
            if not safe_string(entry["id"], 64) or not IDENTIFIER.fullmatch(entry["id"]):
                raise ValueError
            if entry["id"] in ids:
                raise ValueError
            ids.add(entry["id"])
            for name, limit in (("title", 120), ("revision", 64), ("product", 32)):
                if not safe_string(entry[name], limit):
                    raise ValueError
            if not IDENTIFIER.fullmatch(entry["product"]):
                raise ValueError
            if not isinstance(entry["version"], str) or not VERSION.fullmatch(entry["version"]):
                raise ValueError
            if entry["audience"] not in ("public", "staff"):
                raise ValueError
            start = iso_date(entry["effective_from"])
            end = iso_date(entry["effective_until"]) if entry.get("effective_until") is not None else None
            reviewed = iso_date(entry["reviewed_at"])
            if end is not None and end <= start:
                raise ValueError
            body = entry["text"]
            if not isinstance(body, str) or not 0 < len(body) <= 9600 or not body.strip():
                raise ValueError
            if any(unicodedata.category(char) in {"Cc", "Cs"} and char not in "\n\t" for char in body):
                raise ValueError
            document = Document(entry["id"], entry["title"], entry["revision"], entry["product"],
                                entry["version"], entry["audience"], start, end, reviewed, body)
            parts = passages(document)
            if not 1 <= len(parts) <= 16 or any(not part.text.strip() or len(part.text) > 600 for part in parts):
                raise ValueError
            # Bound the original span, including separators, of every two-paragraph chunk.
            if any(right.end - left.start > 1202 for left, right in zip(parts, parts[1:])):
                raise ValueError
            documents.append(document)
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError):
        raise AgentError("invalid_corpus") from None
    return Snapshot(sha256(raw).hexdigest(), tuple(documents))


def eligible(snapshot: Snapshot, request: Request) -> tuple[Document, ...]:
    """Apply host scope before ranking, including its term-frequency statistics.

    Effective intervals are [start, end); review age includes days 0 through 90.
    Staff scope includes public sources. These dates enforce declared metadata,
    not independently verified real-world freshness.
    """
    return tuple(document for document in snapshot.documents if (
        document.product == "atlasdesk" and document.version == request.version
        and (document.audience == "public" or request.audience == "staff")
        and document.effective_from <= request.as_of
        and (document.effective_until is None or request.as_of < document.effective_until)
        and 0 <= (request.as_of - document.reviewed_at).days <= 90
    ))
