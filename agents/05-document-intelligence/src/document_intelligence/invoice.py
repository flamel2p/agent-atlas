"""Invoice policy over an immutable, invocation-local document ledger.

A ledger retains every validated OCR token in original pixel coordinates.
Evidence points back to this ledger; it proves where text came from, not whether
recognition was correct. Pure field policy associates exact cues on one line,
validates every candidate, then accepts consensus or produces a review packet.
No model proposes actions and this module performs no I/O or downstream posting.
"""

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
import re
from typing import Literal

type FieldName = Literal["invoice_number", "invoice_date", "total_myr"]
type Value = str | date | Decimal
MAX_CANDIDATES = 64


class InvoiceError(Exception):
    """A stable public failure code; never attach source text or raw exceptions."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Box:
    """Half-open pixel edges, top-left origin, on the unmodified source page."""

    left: int
    top: int
    right: int
    bottom: int


@dataclass(frozen=True)
class Token:
    id: str
    text: str
    line_key: tuple[int, int, int]
    bbox: Box
    ocr_score: float | None


@dataclass(frozen=True)
class Page:
    number: int
    width: int
    height: int
    tokens: tuple[Token, ...]


@dataclass(frozen=True)
class Document:
    """Validated source snapshot, with hashes in the caller's source order."""

    source_mode: Literal["fixture", "local_ocr"]
    source_sha256: tuple[str, ...]
    pages: tuple[Page, ...]
    engine: str | None = None


@dataclass(frozen=True)
class Evidence:
    page: int
    cue_token_ids: tuple[str, ...]
    value_token_ids: tuple[str, ...]
    cue_bbox: Box
    value_bbox: Box | None


@dataclass(frozen=True)
class Candidate:
    raw_value: str
    normalized_value: Value | None
    evidence: Evidence
    min_ocr_score: float | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AcceptedField:
    value: Value
    candidates: tuple[Candidate, ...]

    @property
    def status(self) -> str:
        return "accepted"


@dataclass(frozen=True)
class ReviewField:
    candidates: tuple[Candidate, ...]
    reasons: tuple[str, ...]

    @property
    def value(self) -> None:
        return None

    @property
    def status(self) -> str:
        return "review_required"


type Field = AcceptedField | ReviewField


def _serialized(value: Value | None) -> str | None:
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, date):
        return value.isoformat()
    return value


@dataclass(frozen=True)
class InvoiceReport:
    """The field union owns acceptance; document status cannot drift from it."""

    document: Document
    invoice_number: Field
    invoice_date: Field
    total_myr: Field

    @property
    def status(self) -> str:
        return "extracted" if all(isinstance(f, AcceptedField) for f in self.fields) else "review_required"

    @property
    def fields(self) -> tuple[Field, Field, Field]:
        return self.invoice_number, self.invoice_date, self.total_myr

    @property
    def record(self) -> dict[str, str | None] | None:
        if self.status != "extracted":
            return None
        return {name: _serialized(field.value) for name, field in zip(FIELD_NAMES, self.fields)}

    def to_dict(self) -> dict:
        fields = {}
        for name, field in zip(FIELD_NAMES, self.fields):
            candidates = []
            for candidate in field.candidates:
                item = asdict(candidate)
                item["normalized_value"] = _serialized(candidate.normalized_value)
                candidates.append(item)
            fields[name] = {
                "status": field.status,
                "value": _serialized(field.value),
                "reasons": field.reasons if isinstance(field, ReviewField) else (),
                "candidates": candidates,
            }
        return {**asdict(self.document), "fields": fields, "status": self.status, "record": self.record}


FIELD_NAMES: tuple[FieldName, ...] = ("invoice_number", "invoice_date", "total_myr")
LABELS: dict[str, FieldName] = {
    "invoice no": "invoice_number", "invoice number": "invoice_number",
    "invoice #": "invoice_number", "invoice date": "invoice_date",
    "grand total": "total_myr", "total due": "total_myr", "amount due": "total_myr",
}


def _box(tokens: tuple[Token, ...]) -> Box:
    return Box(min(t.bbox.left for t in tokens), min(t.bbox.top for t in tokens),
               max(t.bbox.right for t in tokens), max(t.bbox.bottom for t in tokens))


def _cue_at(tokens: tuple[Token, ...], start: int) -> tuple[int, FieldName] | None:
    # Labels span at most two words, plus an optional punctuation token. Whole
    # token matching prevents substring labels and never edits OCR characters.
    for end in range(start + 1, min(len(tokens), start + 3) + 1):
        label = " ".join(t.text for t in tokens[start:end])
        label = " ".join(label.lower().rstrip(".:").split())
        if label in LABELS:
            if end < len(tokens) and tokens[end].text in (":", "."):
                end += 1
            return end, LABELS[label]
    return None


def _value(name: FieldName, raw: str) -> tuple[Value | None, str | None]:
    if not raw:
        return None, "missing_value"
    if name == "invoice_number":
        return (raw, None) if re.fullmatch(r"[A-Z0-9][A-Z0-9/-]{1,31}", raw) else (None, "invalid_identifier")
    if name == "invoice_date":
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
            try:
                return date.fromisoformat(raw), None
            except ValueError:
                pass
        return None, "invalid_date"
    match = re.fullmatch(r"(?:RM|MYR)\s+([0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)\.([0-9]{2})", raw)
    if not match:
        reason = "invalid_amount" if re.match(r"^(?:RM|MYR)(?:\s|$)", raw) else "unsupported_currency"
        return None, reason
    amount = Decimal(match[1].replace(",", "") + "." + match[2])
    if not Decimal("0") < amount <= Decimal("999999999.99"):
        return None, "amount_out_of_range"
    return amount, None


def _candidate(name: FieldName, page: int, cue: tuple[Token, ...],
               value: tuple[Token, ...], multiple: bool) -> Candidate:
    tokens = cue + value
    raw = " ".join(t.text for t in value)
    normalized, invalid = _value(name, raw)
    reasons = [invalid] if invalid else []
    if multiple:
        reasons.append("multiple_cues")
    # Same line keys are necessary but not sufficient: overlapping horizontal
    # spans leave association ambiguous even when text happens to parse.
    if any(a.bbox.right > b.bbox.left for a, b in zip(tokens, tokens[1:])):
        reasons.append("ambiguous_geometry")
    # OCR can assign one line key to different table columns. Require adjacent
    # spans to share vertical pixels and have a gap <= six token heights.
    if any(min(a.bbox.bottom, b.bbox.bottom) <= max(a.bbox.top, b.bbox.top)
           or b.bbox.left - a.bbox.right > 6 * max(a.bbox.bottom - a.bbox.top, b.bbox.bottom - b.bbox.top)
           for a, b in zip(tokens, tokens[1:])):
        reasons.append("ambiguous_layout")
    score = None if any(t.ocr_score is None for t in tokens) else min(t.ocr_score for t in tokens)
    if score is None:
        reasons.append("missing_ocr_score")
    if any(t.ocr_score is not None and t.ocr_score < 80 for t in tokens):
        reasons.append("low_ocr_score")
    return Candidate(raw, normalized,
                     Evidence(page, tuple(t.id for t in cue), tuple(t.id for t in value),
                              _box(cue), _box(value) if value else None), score, tuple(reasons))


def _resolve(candidates: tuple[Candidate, ...]) -> Field:
    if not candidates:
        return ReviewField((), ("missing",))
    reasons = {reason for candidate in candidates for reason in candidate.reasons}
    values = {c.normalized_value for c in candidates if c.normalized_value is not None}
    if len(values) > 1:
        reasons.add("conflicting_values")
    if reasons:
        return ReviewField(candidates, tuple(sorted(reasons)))
    return AcceptedField(next(iter(values)), candidates)


def extract_document(document: Document) -> InvoiceReport:
    """Pure policy for validated ledgers. Every relevant candidate is retained."""
    found: dict[FieldName, list[Candidate]] = {name: [] for name in FIELD_NAMES}
    for page in document.pages:
        lines: dict[tuple[int, int, int], list[Token]] = {}
        for token in page.tokens:
            lines.setdefault(token.line_key, []).append(token)
        for key in sorted(lines):
            tokens = tuple(sorted(lines[key], key=lambda t: (t.bbox.left, t.bbox.top, t.id)))
            if not _cue_at(tokens, 0):
                continue
            cues = []
            position = 0
            while position < len(tokens):
                match = _cue_at(tokens, position)
                if match:
                    end, name = match
                    cues.append((position, end, name))
                    position = end
                else:
                    position += 1
            for index, (start, end, name) in enumerate(cues):
                stop = cues[index + 1][0] if index + 1 < len(cues) else len(tokens)
                if len(found[name]) >= MAX_CANDIDATES:
                    raise InvoiceError("candidate_limit")
                found[name].append(_candidate(name, page.number, tokens[start:end], tokens[end:stop], len(cues) > 1))
    return InvoiceReport(document, *(_resolve(tuple(found[name])) for name in FIELD_NAMES))
