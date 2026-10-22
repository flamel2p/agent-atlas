"""Bounded fixture decoding is the sole external-data boundary.

Three separately inspectable files hold selection data, host curator assertions,
and heldout labels. This module rejects malformed host bundles and constructs
frozen values. Structurally valid but ineligible feedback remains untrusted data
for the experiment to exclude with a reason. No arbitrary path is a CLI input.
"""

from enum import StrEnum
from importlib.resources import files
import json
import re
from typing import BinaryIO

from .experiment import (
    CuratorRecord, Document, Feedback, Group, LabeledCase, Query, RetrievalConfig,
    SCHEMA_VERSION, ScenarioData, SelectionInput, Trace, _digest, _version,
)


MAX_FILE_BYTES = 1_048_576
MAX_JSON_DEPTH = 16
MAX_RECORDS = 100
MAX_TOKENS = 64
MAX_TOKEN_CHARS = 32
MAX_ID_CHARS = 64
MAX_ANSWER_CHARS = 2_000
MAX_REVISION = 1_000_000


class ScenarioName(StrEnum):
    IMPROVEMENT = "improvement"
    REGRESSION = "regression"
    INSUFFICIENT = "insufficient"
    POISONED = "poisoned"
    DEVELOPMENT_REJECTION = "development-rejection"
    NO_GAIN = "no-gain"


class ScenarioError(ValueError):
    """The fixture violates the bounded host schema; no experiment completed."""


def _read_bounded(stream: BinaryIO) -> bytes:
    data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ScenarioError(f"Fixture exceeds {MAX_FILE_BYTES} bytes")
    return data


def _decode_json(data: bytes) -> object:
    if len(data) > MAX_FILE_BYTES:
        raise ScenarioError(f"Fixture exceeds {MAX_FILE_BYTES} bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ScenarioError("Fixture must be UTF-8") from error
    # Bound nesting before the JSON parser can recurse. Brackets inside strings
    # do not count, and the parser still owns full syntax validation afterward.
    depth, in_string, escaped = 0, False, False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise ScenarioError(f"JSON nesting exceeds {MAX_JSON_DEPTH}")
        elif char in "]}":
            depth -= 1

    def unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ScenarioError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise ScenarioError(f"Nonfinite JSON number: {value}")

    try:
        return json.loads(text, object_pairs_hook=unique_keys, parse_constant=reject_constant)
    except (ValueError, RecursionError) as error:
        raise ScenarioError(f"Invalid fixture JSON: {error}") from error


def _object(value: object, keys: set[str], where: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys:
        raise ScenarioError(f"{where} requires exactly these keys: {', '.join(sorted(keys))}")
    return value


def _list(value: object, where: str, maximum: int = MAX_RECORDS,
          nonempty: bool = False) -> list[object]:
    if type(value) is not list or len(value) > maximum or (nonempty and not value):
        raise ScenarioError(f"{where} must be a {'nonempty ' if nonempty else ''}list of at most {maximum}")
    return value


def _identifier(value: object, where: str) -> str:
    if (type(value) is not str or len(value) > MAX_ID_CHARS
            or re.fullmatch(r"[a-z][a-z0-9_-]*", value, flags=re.ASCII) is None):
        raise ScenarioError(f"{where} must be a lowercase identifier of at most {MAX_ID_CHARS} characters")
    return value


def _optional_identifier(value: object, where: str) -> str | None:
    return None if value is None else _identifier(value, where)


def _integer(value: object, where: str, minimum: int, maximum: int) -> int:
    # bool subclasses int in Python, so isinstance would silently accept True.
    if type(value) is not int or not minimum <= value <= maximum:
        raise ScenarioError(f"{where} must be an integer in [{minimum}, {maximum}]")
    return value


def _tokens(value: object, where: str) -> tuple[str, ...]:
    tokens = _list(value, where, MAX_TOKENS, nonempty=True)
    for token in tokens:
        if (type(token) is not str or len(token) > MAX_TOKEN_CHARS
                or re.fullmatch(r"[a-z0-9]+", token, flags=re.ASCII) is None):
            raise ScenarioError(f"{where} requires normalized ASCII tokens of at most {MAX_TOKEN_CHARS} characters")
    if len(set(tokens)) != len(tokens):
        raise ScenarioError(f"{where} has duplicate tokens")
    return tuple(sorted(tokens))


def _query(value: object, where: str) -> Query:
    obj = _object(value, {"query_id", "topic", "tokens"}, where)
    return Query(_identifier(obj["query_id"], f"{where}.query_id"),
                 _identifier(obj["topic"], f"{where}.topic"),
                 _tokens(obj["tokens"], f"{where}.tokens"))


def _document(value: object) -> Document:
    obj = _object(value, {"document_id", "topic", "revision", "tokens", "answer"}, "document")
    answer = obj["answer"]
    if (type(answer) is not str or not answer.strip() or len(answer) > MAX_ANSWER_CHARS
            or any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in answer)):
        raise ScenarioError(f"document.answer must be nonempty text of at most {MAX_ANSWER_CHARS} characters without controls")
    return Document(_identifier(obj["document_id"], "document.document_id"),
                    _identifier(obj["topic"], "document.topic"),
                    _integer(obj["revision"], "document.revision", 1, MAX_REVISION),
                    _tokens(obj["tokens"], "document.tokens"), answer)


def _trace(value: object) -> Trace:
    obj = _object(value, {"trace_id", "query", "baseline_version_id", "observed_document_id"}, "trace")
    baseline_id = obj["baseline_version_id"]
    if type(baseline_id) is not str or re.fullmatch(r"[0-9a-f]{64}", baseline_id) is None:
        raise ScenarioError("trace.baseline_version_id must be a SHA-256 hex identifier")
    return Trace(_identifier(obj["trace_id"], "trace.trace_id"),
                 _query(obj["query"], "trace.query"), baseline_id,
                 _optional_identifier(obj["observed_document_id"], "trace.observed_document_id"))


def _feedback(value: object) -> Feedback:
    obj = _object(value, {"feedback_id", "trace_id", "target_document_id", "curator_record_id"}, "feedback")
    return Feedback(*(_identifier(obj[key], f"feedback.{key}") for key in
                      ("feedback_id", "trace_id", "target_document_id", "curator_record_id")))


def _curator(value: object) -> CuratorRecord:
    obj = _object(value, {"record_id", "trace_id", "target_document_id"}, "curator")
    return CuratorRecord(*(_identifier(obj[key], f"curator.{key}") for key in
                           ("record_id", "trace_id", "target_document_id")))


def _case(value: object, development: bool) -> LabeledCase:
    obj = _object(value, {"query", "expected_document_id", "group"}, "case")
    allowed = {Group.DEVELOPMENT} if development else {Group.RECENT, Group.STABLE}
    if type(obj["group"]) is not str or obj["group"] not in allowed:
        raise ScenarioError(f"case.group must be one of {', '.join(sorted(allowed))}")
    return LabeledCase(_query(obj["query"], "case.query"),
                       _optional_identifier(obj["expected_document_id"], "case.expected_document_id"),
                       Group(obj["group"]))


def _unique(values: tuple[object, ...], key: str, where: str) -> None:
    ids = [getattr(value, key) for value in values]
    if len(ids) != len(set(ids)):
        raise ScenarioError(f"Duplicate {where} IDs")


def _eligible_label(query: Query, document_id: str, documents: dict[str, Document],
                    where: str) -> None:
    target = documents.get(document_id)
    if (target is None or target.topic != query.topic
            or not set(target.tokens).intersection(query.tokens)):
        raise ScenarioError(f"{where} must reference a same-topic positive-overlap document")


def _decode_bundle(name: str, selection_bytes: bytes, curator_bytes: bytes,
                   holdout_bytes: bytes) -> ScenarioData:
    """Internal decoding seam used by mutation tests, with the same byte bounds."""
    selection_obj = _object(_decode_json(selection_bytes),
                            {"schema_version", "corpus", "baseline", "traces", "feedback", "development_controls"},
                            "selection")
    curator_obj = _object(_decode_json(curator_bytes), {"schema_version", "records"}, "curators")
    holdout_obj = _object(_decode_json(holdout_bytes), {"schema_version", "cases"}, "holdout")
    for where, envelope in (("selection", selection_obj), ("curators", curator_obj), ("holdout", holdout_obj)):
        if _integer(envelope["schema_version"], f"{where}.schema_version", 1, 1) != SCHEMA_VERSION:
            raise ScenarioError("Unsupported schema version")
    baseline_obj = _object(selection_obj["baseline"], {"config"}, "baseline")
    config_obj = _object(baseline_obj["config"], {"recency_topic"}, "baseline.config")
    if config_obj["recency_topic"] is not None:
        raise ScenarioError("Baseline recency_topic must be null")
    corpus = tuple(sorted((_document(item) for item in _list(selection_obj["corpus"], "corpus", nonempty=True)),
                          key=lambda doc: doc.document_id))
    traces = tuple(sorted((_trace(item) for item in _list(selection_obj["traces"], "traces")),
                          key=lambda trace: trace.trace_id))
    feedback = tuple(sorted((_feedback(item) for item in _list(selection_obj["feedback"], "feedback")),
                            key=lambda record: record.feedback_id))
    curators = tuple(sorted((_curator(item) for item in _list(curator_obj["records"], "curators.records")),
                            key=lambda record: record.record_id))
    controls = tuple(sorted((_case(item, True) for item in _list(selection_obj["development_controls"], "development_controls")),
                            key=lambda case: case.query.query_id))
    holdout = tuple(sorted((_case(item, False) for item in _list(holdout_obj["cases"], "holdout.cases", nonempty=True)),
                           key=lambda case: case.query.query_id))
    for values, key, where in ((corpus, "document_id", "document"), (traces, "trace_id", "trace"),
                               (feedback, "feedback_id", "feedback"), (curators, "record_id", "curator")):
        _unique(values, key, where)
    trace_queries = tuple(trace.query for trace in traces)
    control_queries = tuple(case.query for case in controls)
    heldout_queries = tuple(case.query for case in holdout)
    for queries, where in ((trace_queries, "trace query"), (control_queries, "development query"),
                           (heldout_queries, "heldout query")):
        _unique(queries, "query_id", where)
    trace_ids = {query.query_id for query in trace_queries}
    trace_signatures = {query.signature for query in trace_queries}
    control_ids = {query.query_id for query in control_queries}
    control_signatures = {query.signature for query in control_queries}
    heldout_ids = {query.query_id for query in heldout_queries}
    heldout_signatures = {query.signature for query in heldout_queries}
    if (trace_ids.intersection(control_ids) or trace_signatures.intersection(control_signatures)
            or len(control_signatures) != len(control_queries)):
        raise ScenarioError("Development controls must have independent IDs and query signatures")
    if (heldout_ids.intersection(trace_ids | control_ids)
            or heldout_signatures.intersection(trace_signatures | control_signatures)
            or len(heldout_signatures) != len(heldout_queries)):
        raise ScenarioError("Holdout must have independent IDs and query signatures, disjoint from selection")
    if {case.group for case in holdout} != {Group.RECENT, Group.STABLE}:
        raise ScenarioError("Holdout requires nonempty recent and stable groups")
    documents = {doc.document_id: doc for doc in corpus}
    trace_map = {trace.trace_id: trace for trace in traces}
    for trace in traces:
        if trace.observed_document_id is not None and trace.observed_document_id not in documents:
            raise ScenarioError("Trace observation references an unknown document")
    curator_trace_ids = set()
    for record in curators:
        if record.trace_id not in trace_map:
            raise ScenarioError("Curator record references an unknown trace")
        if record.trace_id in curator_trace_ids:
            raise ScenarioError("Host curator manifest permits only one record per trace")
        curator_trace_ids.add(record.trace_id)
        _eligible_label(trace_map[record.trace_id].query, record.target_document_id,
                        documents, "Curator target")
    for case in controls + holdout:
        if case.expected_document_id is not None:
            _eligible_label(case.query, case.expected_document_id, documents, "Expected label")
    baseline = _version(_digest(corpus), RetrievalConfig(None))
    return ScenarioData(name, SelectionInput(corpus, baseline, traces, feedback, curators, controls), holdout)


def load_scenario(name: ScenarioName) -> ScenarioData:
    """Read one allowlisted bundled fixture, using no caller-supplied file path."""
    if not isinstance(name, ScenarioName):
        raise ScenarioError("load_scenario requires a ScenarioName enum")
    root = files("self_improving").joinpath("fixtures", name.value)
    contents = []
    try:
        for filename in ("selection.json", "curators.json", "holdout.json"):
            with root.joinpath(filename).open("rb") as stream:
                contents.append(_read_bounded(stream))
    except OSError as error:
        raise ScenarioError(f"Cannot read bundled scenario {name.value}: {error}") from error
    return _decode_bundle(name.value, *contents)
