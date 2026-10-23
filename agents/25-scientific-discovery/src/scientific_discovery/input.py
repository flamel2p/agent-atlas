"""Strict JSON and filesystem boundary producing immutable domain input.

Text is evidence data, not authority. Structural limits are checked before domain
work; references that represent missing evidence are retained for coverage gates.
"""
import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path
from typing import Any

from .domain import Constraints, CorpusRecord, Measurement, Paper, Request, Topic

MAX_BYTES = 65536
MAX_DEPTH = 12
MAX_VALUES = 4096
_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}\Z")


class InvalidInput(ValueError):
    """Expected boundary rejection; messages never contain supplied input text."""


def require(condition: bool, message: str = "schema validation failed") -> None:
    if not condition:
        raise InvalidInput(message)


def read_input(path: Path) -> bytes:
    """Open bounded regular input without final-link traversal or FIFO blocking."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        require(stat.S_ISREG(os.fstat(descriptor).st_mode), "input must be a regular file")
    except BaseException:
        os.close(descriptor)
        raise
    with os.fdopen(descriptor, "rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, "input byte limit exceeded")
    return data


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in items:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _constant(_: str) -> Any:
    raise InvalidInput("nonfinite number")


def _shape(value: Any, keys: set[str]) -> dict:
    require(type(value) is dict and set(value) == keys)
    return value


def _list(value: Any, low: int, high: int) -> list:
    require(type(value) is list and low <= len(value) <= high)
    return value


def _text(value: Any, maximum: int) -> str:
    require(type(value) is str and bool(value.strip()) and len(value) <= maximum)
    return value


def _identifier(value: Any) -> str:
    require(type(value) is str and bool(_ID.fullmatch(value)))
    return value


def _ids(value: Any, low: int, high: int) -> tuple[str, ...]:
    result = tuple(_identifier(x) for x in _list(value, low, high))
    require(len(set(result)) == len(result), "duplicate identifier")
    return result


def _number(value: Any, low: float, high: float) -> float:
    require(type(value) in (int, float))
    # Bounds before float conversion also reject integers too large to convert safely.
    require(low <= value <= high and math.isfinite(value))
    return float(value)


def _integer(value: Any, low: int, high: int) -> int:
    require(type(value) is int and low <= value <= high)
    return value


def parse(data: bytes) -> Request:
    """Validate strict bounded JSON and references, then attach original-byte identity."""
    require(len(data) <= MAX_BYTES, "input byte limit exceeded")
    try:
        root = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise InvalidInput("invalid JSON or UTF-8") from error
    count = 0
    stack = [(root, 1)]
    while stack:
        value, depth = stack.pop()
        count += 1
        require(depth <= MAX_DEPTH and count <= MAX_VALUES, "JSON structure limit exceeded")
        if type(value) is dict:
            stack.extend((x, depth + 1) for pair in value.items() for x in pair)
        elif type(value) is list:
            stack.extend((x, depth + 1) for x in value)
        elif type(value) is str:
            require(len(value) <= 2048 and not any(0xD800 <= ord(c) <= 0xDFFF for c in value), "invalid or oversized string")
        elif type(value) is float:
            require(math.isfinite(value), "nonfinite number")
    root = _shape(root, {"schema_version", "corpus_id", "topics", "required_sources", "sources", "constraints", "measurements"})
    _integer(root["schema_version"], 1, 1)
    corpus_id = _identifier(root["corpus_id"])
    topics = []
    for value in _list(root["topics"], 2, 8):
        topic = _shape(value, {"id", "label"})
        topics.append(Topic(_identifier(topic["id"]), _text(topic["label"], 120)))
    topic_ids = {t.id for t in topics}
    require(len(topic_ids) == len(topics), "duplicate topic")
    required = _ids(root["required_sources"], 1, 8)
    sources = []
    papers = []
    for value in _list(root["sources"], 0, 8):
        source = _shape(value, {"id", "papers"})
        source_id = _identifier(source["id"])
        require(source_id in required and source_id not in sources, "invalid source declaration")
        sources.append(source_id)
        for value in _list(source["papers"], 0, 16):
            paper = _shape(value, {"id", "title", "topics", "effect", "evidence", "citations"})
            paper_id = _identifier(paper["id"])
            paper_topics = tuple(sorted(_ids(paper["topics"], 1, 2)))
            require(set(paper_topics) <= topic_ids, "unknown topic")
            citations = _ids(paper["citations"], 0, 8)
            require(paper_id not in citations, "self citation")
            papers.append(Paper(paper_id, _text(paper["title"], 200), paper_topics, _number(paper["effect"], -100, 100), _text(paper["evidence"], 1000), citations, source_id))
    require(len(papers) <= 64 and len({p.id for p in papers}) == len(papers), "paper count or identity violation")
    constraints = _shape(root["constraints"], {"max_runs", "max_cost", "tolerance"})
    budget = Constraints(_integer(constraints["max_runs"], 0, 100), _number(constraints["max_cost"], 0, 1000), _number(constraints["tolerance"], 0, 100))
    measurements = []
    for value in _list(root["measurements"], 0, 28):
        measurement = _shape(value, {"pair", "values"})
        pair = tuple(sorted(_ids(measurement["pair"], 2, 2)))
        require(set(pair) <= topic_ids, "unknown measurement topic")
        values = tuple(_number(x, -200, 200) for x in _list(measurement["values"], 3, 3))
        measurements.append(Measurement((pair[0], pair[1]), values))
    require(len({m.pair for m in measurements}) == len(measurements), "duplicate measurement pair")
    corpus = CorpusRecord(corpus_id, tuple(topics), required, tuple(sources), tuple(papers))
    return Request(corpus, budget, tuple(measurements), hashlib.sha256(data).hexdigest())
