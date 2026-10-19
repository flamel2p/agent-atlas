from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from math import log

from .contracts import AgentError, tokens
from .corpus import Document, Passage, Snapshot, passages


@dataclass(frozen=True, slots=True)
class Chunk:
    paragraphs: tuple[Passage, ...]
    score: float = 0.0

    @property
    def id(self):
        return f"{self.paragraphs[0].document.id}:c{self.paragraphs[0].index + 1}"

    @property
    def text(self):
        return self.paragraphs[0].document.text[self.paragraphs[0].start:self.paragraphs[-1].end]

    def public(self):
        first, last = self.paragraphs[0], self.paragraphs[-1]
        return {"chunk_id": self.id, "document_id": first.document.id, "title": first.document.title,
                "revision": first.document.revision, "version": first.document.version,
                "reviewed_at": first.document.reviewed_at.isoformat(), "start": first.start,
                "end": last.end, "text": self.text, "score": self.score,
                "passage_ids": [part.id for part in self.paragraphs]}


def make_chunks(documents: tuple[Document, ...]) -> tuple[Chunk, ...]:
    chunks = []
    for document in documents:
        parts = passages(document)
        if len(parts) == 1:
            chunks.append(Chunk(parts))
        else:
            chunks.extend(Chunk(parts[i:i + 2]) for i in range(len(parts) - 1))
    return tuple(chunks)


def retrieve(documents: tuple[Document, ...], question: str) -> tuple[Chunk, ...]:
    chunks = make_chunks(documents)
    if not chunks:
        return ()
    frequencies = [Counter(tokens(chunk.text)) for chunk in chunks]
    lengths = [sum(frequency.values()) for frequency in frequencies]
    average = sum(lengths) / len(chunks)
    if average == 0:
        return ()
    query = set(tokens(question))
    document_frequency = Counter(word for frequency in frequencies for word in frequency if word in query)
    ranked = []
    for chunk, frequency, length in zip(chunks, frequencies, lengths):
        score = 0.0
        for word in sorted(query):
            count = frequency[word]
            if count:
                df = document_frequency[word]
                inverse = log(1 + (len(chunks) - df + 0.5) / (df + 0.5))
                score += inverse * count * 2.2 / (count + 1.2 * (0.25 + 0.75 * length / average))
        if score > 0:
            ranked.append(Chunk(chunk.paragraphs, score))
    return tuple(sorted(ranked, key=lambda item: (-item.score, item.id))[:3])


def candidate_passages(chunks: tuple[Chunk, ...]) -> tuple[Passage, ...]:
    found = {}
    for chunk in chunks:
        for part in chunk.paragraphs:
            found.setdefault(part.id, part)
    return tuple(found.values())


def replay_select(question: str, candidates: tuple[Passage, ...]) -> dict:
    wanted = set(tokens(question))
    if wanted:
        for count in range(1, min(3, len(candidates)) + 1):
            for selected in combinations(candidates, count):
                coverage = set().union(*(set(tokens(part.text)) for part in selected))
                if wanted <= coverage:
                    return {"status": "selected", "passage_ids": [part.id for part in selected]}
    return {"status": "abstained", "passage_ids": []}


def render_selection(selection: object, candidates: tuple[Passage, ...], snapshot: Snapshot) -> tuple[str, list[dict]]:
    if not isinstance(selection, dict) or set(selection) != {"status", "passage_ids"}:
        raise AgentError("invalid_selection")
    state, selected = selection["status"], selection["passage_ids"]
    if state not in ("selected", "abstained") or not isinstance(selected, list):
        raise AgentError("invalid_selection")
    if any(not isinstance(item, str) for item in selected) or len(selected) > 3 or len(set(selected)) != len(selected):
        raise AgentError("invalid_selection")
    if (state == "selected") != bool(selected):
        raise AgentError("invalid_selection")
    allowed = {part.id: part for part in candidates}
    sources = {document.id: document for document in snapshot.documents}
    citations = []
    for passage_id in selected:
        if passage_id not in allowed:
            raise AgentError("invalid_selection")
        part = allowed[passage_id]
        document = sources.get(part.document.id)
        if document != part.document or part not in passages(document):
            raise AgentError("invalid_selection")
        citations.append({"document_id": document.id, "title": document.title,
                          "revision": document.revision, "product": document.product,
                          "version": document.version, "reviewed_at": document.reviewed_at.isoformat(),
                          "passage_id": part.id, "start": part.start, "end": part.end,
                          "quote": document.text[part.start:part.end], "snapshot_digest": snapshot.digest})
    answer = "\n\n".join(f'[{index}] {citation["quote"]}' for index, citation in enumerate(citations, 1))
    return answer, citations
