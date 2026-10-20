"""Pure lexical selection, supported grouping, and extractive evidence mapping.

Jaccard is intersection size divided by union size of token sets. It measures
shared vocabulary here, never scientific confidence. Complete-link support is
the least Jaccard score across two groups; a merge requires positive support
for every cross-pair. All intermediate state is local to one mapping call.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import re

from .corpus import Corpus, DuplicateDecision, InputError, Paper, _text

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_SENTENCE = re.compile(r"[^.!?]+[.!?]?", re.UNICODE)
_STOPWORDS = frozenset({"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "of", "on", "or", "that", "the", "to", "was", "were", "with"})
_LIMITS = (
    "Synthetic corpus only; lexical relevance and theme membership are heuristics.",
    "Excerpts are source text, not validated scientific findings.",
    "Consensus, disagreement, study quality, and research gaps: not assessed.",
)


def _tokens(value: str) -> frozenset[str]:
    return frozenset(token for token in _WORD.findall(value.casefold()) if token not in _STOPWORDS)


def _jaccard(left: frozenset[str], right: frozenset[str]) -> Fraction:
    union = left | right
    return Fraction(len(left & right), len(union)) if union else Fraction(0)


@dataclass(frozen=True)
class ResearchRequest:
    """Validated host options; the objective is data and cannot change policy."""

    objective: str
    max_papers: int = 20
    target_themes: int = 4

    def __post_init__(self) -> None:
        _text(self.objective, maximum=500)
        if not _tokens(self.objective):
            raise InputError("objective has no searchable terms")
        if type(self.max_papers) is not int or not 1 <= self.max_papers <= 20:
            raise InputError("invalid max papers")
        if type(self.target_themes) is not int or not 1 <= self.target_themes <= 8:
            raise InputError("invalid target themes")


@dataclass(frozen=True)
class RankedPaper:
    """Selected paper, exact relevance fraction, and overlapping query terms."""

    paper: Paper
    score: Fraction
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceSpan:
    """Half-open Unicode code-point slice into one selected member abstract."""

    paper_id: str
    abstract_sha256: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Theme:
    """A supported lexical group and at most two member excerpts."""

    theme_id: str
    member_ids: tuple[str, ...]
    descriptors: tuple[str, ...]
    evidence: tuple[EvidenceSpan, ...]


@dataclass(frozen=True)
class LiteratureMap:
    """Complete invocation result; JSON is its authoritative public form."""

    objective: str
    corpus_id: str
    corpus_sha256: str
    query_terms: tuple[str, ...]
    original_record_count: int
    considered_count: int
    selected: tuple[RankedPaper, ...]
    themes: tuple[Theme, ...]
    duplicates: tuple[DuplicateDecision, ...]
    outcome: str
    stop_reason: str
    truncated: bool

    def to_dict(self) -> dict[str, object]:
        """Produce only JSON-native values in stable insertion and tuple order."""

        return {
            "schema_version": 1,
            "source_kind": "synthetic",
            "corpus_id": self.corpus_id,
            "corpus_sha256": self.corpus_sha256,
            "objective": self.objective,
            "outcome": self.outcome,
            "query_terms": list(self.query_terms),
            "original_record_count": self.original_record_count,
            "considered_count": self.considered_count,
            "removed_duplicate_count": self.original_record_count - self.considered_count,
            "selected_count": len(self.selected),
            "truncated": self.truncated,
            "selected_papers": [
                {
                    "paper_id": item.paper.paper_id,
                    "title": item.paper.title,
                    "abstract": item.paper.abstract,
                    "authors": list(item.paper.authors),
                    "year": item.paper.year,
                    "source": item.paper.source,
                    "source_id": item.paper.source_id,
                    "synthetic": item.paper.synthetic,
                    "relevance": {"numerator": item.score.numerator, "denominator": item.score.denominator},
                    "matched_terms": list(item.matched_terms),
                }
                for item in self.selected
            ],
            "themes": [
                {
                    "theme_id": theme.theme_id,
                    "member_ids": list(theme.member_ids),
                    "descriptors": list(theme.descriptors),
                    "evidence": [
                        {
                            "paper_id": span.paper_id,
                            "abstract_sha256": span.abstract_sha256,
                            "start": span.start,
                            "end": span.end,
                            "text": span.text,
                        }
                        for span in theme.evidence
                    ],
                }
                for theme in self.themes
            ],
            "duplicate_decisions": [
                {"retained_id": decision.retained_id, "alias_ids": list(decision.alias_ids)}
                for decision in self.duplicates
            ],
            "stop_reason": self.stop_reason,
            "interpretation_limits": list(_LIMITS),
            "assessments": {"consensus": "not_assessed", "disagreement": "not_assessed", "study_quality": "not_assessed", "research_gaps": "not_assessed"},
        }


def _complete_link(left: tuple[str, ...], right: tuple[str, ...], terms: dict[str, frozenset[str]]) -> Fraction:
    return min(_jaccard(terms[a], terms[b]) for a in left for b in right)


def _groups(selected: tuple[RankedPaper, ...], query: frozenset[str], target: int) -> tuple[list[tuple[str, ...]], str]:
    terms = {item.paper.paper_id: _tokens(item.paper.title + " " + item.paper.abstract) - query for item in selected}
    groups = [(item.paper.paper_id,) for item in selected]
    if len(groups) <= target:
        return groups, "at_or_below_target"
    # At most n-1 merges. Unsupported vocabulary never forces a target count.
    while len(groups) > target:
        candidates = [
            (_complete_link(groups[i], groups[j], terms), tuple(sorted(groups[i] + groups[j])), i, j)
            for i in range(len(groups)) for j in range(i + 1, len(groups))
        ]
        positive = [item for item in candidates if item[0] > 0]
        if not positive:
            return groups, "no_supported_merge"
        # Highest support wins; sorted IDs resolve ties without input-order effects.
        _, joined, i, j = min(positive, key=lambda item: (-item[0], item[1]))
        groups = [group for index, group in enumerate(groups) if index not in (i, j)] + [joined]
    return groups, "target_reached"


def _evidence(paper: Paper, preferred: frozenset[str]) -> EvidenceSpan:
    choices: list[tuple[int, int, int, str]] = []
    for match in _SENTENCE.finditer(paper.abstract):
        raw = match.group()
        stripped = raw.strip()
        if stripped and _tokens(stripped):
            start = match.start() + len(raw) - len(raw.lstrip())
            end = start + len(stripped)
            choices.append((len(_tokens(stripped) & preferred), start, end, stripped))
    if not choices:
        # A valid punctuation-only abstract still needs exact, local evidence.
        text = paper.abstract.strip()
        start = paper.abstract.index(text)
        choices.append((0, start, start + len(text), text))
    _, start, end, text = min(choices, key=lambda item: (-item[0], item[1]))
    return EvidenceSpan(paper.paper_id, hashlib.sha256(paper.abstract.encode("utf-8")).hexdigest(), start, end, text)


def _theme(group: tuple[str, ...], selected: tuple[RankedPaper, ...], query: frozenset[str], number: int) -> Theme:
    by_id = {item.paper.paper_id: item for item in selected}
    order = {item.paper.paper_id: rank for rank, item in enumerate(selected)}
    terms = {paper_id: _tokens(by_id[paper_id].paper.title + " " + by_id[paper_id].paper.abstract) - query for paper_id in group}
    frequency = Counter(term for tokens in terms.values() for term in tokens)
    descriptors = tuple(term for term, _ in sorted(frequency.items(), key=lambda item: (-item[1], item[0]))[:3])
    def representative_key(paper_id: str) -> tuple[Fraction, int, str]:
        others = [other for other in group if other != paper_id]
        support = min((_jaccard(terms[paper_id], terms[other]) for other in others), default=Fraction(1))
        return (-support, order[paper_id], paper_id)
    representatives = sorted(group, key=representative_key)[:2]
    preferred = query | frozenset(descriptors)
    spans = tuple(_evidence(by_id[paper_id].paper, preferred) for paper_id in representatives)
    return Theme(f"T{number}", group, descriptors, spans)


def _validate_evidence(selected: tuple[RankedPaper, ...], themes: tuple[Theme, ...]) -> None:
    papers = {item.paper.paper_id: item.paper for item in selected}
    for theme in themes:
        for span in theme.evidence:
            if span.paper_id not in theme.member_ids or span.paper_id not in papers:
                raise RuntimeError("invalid evidence membership")
            abstract = papers[span.paper_id].abstract
            if abstract[span.start:span.end] != span.text or hashlib.sha256(abstract.encode("utf-8")).hexdigest() != span.abstract_sha256:
                raise RuntimeError("invalid evidence provenance")


def map_literature(corpus: Corpus, request: ResearchRequest) -> LiteratureMap:
    """Map a validated snapshot once, with no I/O, retries, or model authority."""

    if type(corpus) is not Corpus or type(request) is not ResearchRequest:
        raise TypeError("expected Corpus and ResearchRequest")
    query = _tokens(request.objective)
    ranked: list[RankedPaper] = []
    for paper in corpus.papers:
        terms = _tokens(paper.title + " " + paper.abstract)
        score = _jaccard(query, terms)
        if score > 0:
            ranked.append(RankedPaper(paper, score, tuple(sorted(query & terms))))
    ranked.sort(key=lambda item: (-item.score, item.paper.paper_id))
    selected = tuple(ranked[:request.max_papers])
    if not selected:
        return LiteratureMap(request.objective, corpus.corpus_id, corpus.sha256, tuple(sorted(query)), corpus.original_record_count, len(corpus.papers), (), (), corpus.duplicates, "no_matches", "no_positive_overlap", False)
    groups, stop = _groups(selected, query, request.target_themes)
    search_order = {item.paper.paper_id: rank for rank, item in enumerate(selected)}
    groups.sort(key=lambda group: (min(search_order[paper_id] for paper_id in group), group))
    themes = tuple(_theme(group, selected, query, number) for number, group in enumerate(groups, 1))
    _validate_evidence(selected, themes)
    return LiteratureMap(request.objective, corpus.corpus_id, corpus.sha256, tuple(sorted(query)), corpus.original_record_count, len(corpus.papers), selected, themes, corpus.duplicates, "mapped", stop, len(ranked) > len(selected))
