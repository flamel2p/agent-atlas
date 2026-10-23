"""Validate synthetic evidence, apply the policy, and record actual events.

This pure module owns the priority policy and canonical trace representation.
Replay reconstructs the exact execution from recorded evidence. It detects
inconsistent history but cannot authenticate evidence supplied by an operator.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
import re

from .contracts import (
    CompleteEvidence, ContractError, EVIDENCE_NAMES, Evidence, EvidenceEvent,
    Event, FinalEvent, Priority, Request, RuleEvent, Trace,
)

SCHEMA_VERSION = 1
POLICY_VERSION = "task-priority-v1"


@dataclass(frozen=True)
class Rule:
    """Policy-owned predicate, priority, and evidence positions.

    The tuple order in RULES is the selection order. Keeping predicates and
    evidence references together prevents a renderer from choosing new reasons.
    """

    rule_id: str
    priority: Priority
    evidence_positions: tuple[int, ...]
    evaluate: Callable[[CompleteEvidence], bool]


RULES = (
    Rule("urgent-outage", "urgent", (0, 1), lambda e: e.outage and e.blocked_users >= 5),
    Rule("high-impact-or-due", "high", (1, 2), lambda e: e.blocked_users >= 1 or e.due_hours <= 24),
    Rule("routine-default", "routine", (), lambda e: True),
)


def _object(value: object, keys: set[str], code: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise ContractError(code)
    return value


def parse_request(raw: object) -> Request:
    """Parse the external request once. Unknown fields cannot alter authority."""
    item = _object(raw, {"task_id", "evidence"}, "input_invalid")
    task_id = item["task_id"]
    if type(task_id) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", task_id):
        raise ContractError("input_invalid")
    source = item["evidence"]
    if type(source) is not dict or not set(source).issubset(EVIDENCE_NAMES):
        raise ContractError("input_invalid")
    outage, users, due = (source.get(name) for name in EVIDENCE_NAMES)
    if outage is not None and type(outage) is not bool:
        raise ContractError("input_invalid")
    for value, maximum in ((users, 10000), (due, 720)):
        # bool is an int subclass in Python. JSON booleans are not counts.
        if value is not None and (type(value) is not int or not 0 <= value <= maximum):
            raise ContractError("input_invalid")
    return Request(task_id, Evidence(outage, users, due))


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _seal(task_id: str, events: tuple[Event, ...]) -> Trace:
    body = {"schema_version": SCHEMA_VERSION, "policy_version": POLICY_VERSION,
            "task_id": task_id, "events": [asdict(event) for event in events]}
    digest = hashlib.sha256(_canonical(body)).hexdigest()
    return Trace(SCHEMA_VERSION, POLICY_VERSION, task_id, events, digest)


def classify(request: Request) -> Trace:
    """Record three observations, then either stop for gaps or evaluate all rules.

    Missing observations cannot become defaults. Complete execution records all
    rule results, while first-match precedence owns the one final priority.
    """
    values = (request.evidence.outage, request.evidence.blocked_users, request.evidence.due_hours)
    evidence = tuple(EvidenceEvent(f"E{i + 1}", name, value, "missing" if value is None else "present")
                     for i, (name, value) in enumerate(zip(EVIDENCE_NAMES, values, strict=True)))
    missing = tuple(event.event_id for event in evidence if event.availability == "missing")
    if missing:
        return _seal(request.task_id, (*evidence, FinalEvent("E4", "needs_review", None, None, missing)))

    observations = CompleteEvidence(*values)
    rules = tuple(RuleEvent(f"E{i + 4}", rule.rule_id, rule.evaluate(observations), rule.priority,
                            tuple(evidence[position].event_id for position in rule.evidence_positions))
                  for i, rule in enumerate(RULES))
    selected = next(event for event in rules if event.matched)
    final = FinalEvent("E7", "completed", selected.priority, selected.rule_id, (selected.event_id,))
    return _seal(request.task_id, (*evidence, *rules, final))


def trace_to_dict(trace: Trace) -> dict:
    """Return a detached JSON snapshot. Editing it never edits the frozen trace."""
    return json.loads(_canonical(asdict(trace)))


def load_trace(raw: object) -> Trace:
    """Accept a trace only when schema, digest, and exact policy replay agree.

    Canonical JSON comparison preserves type distinctions such as 1 and true.
    This is integrity validation, not proof that the original evidence is true.
    """
    try:
        item = _object(raw, {"schema_version", "policy_version", "task_id", "events", "digest"}, "trace_invalid")
        if type(item["schema_version"]) is not int or item["schema_version"] != SCHEMA_VERSION:
            raise ContractError("trace_invalid")
        if item["policy_version"] != POLICY_VERSION:
            raise ContractError("trace_invalid")
        events = item["events"]
        if type(events) is not list or len(events) not in (4, 7):
            raise ContractError("trace_invalid")
        source = {}
        for position, name in enumerate(EVIDENCE_NAMES):
            event = _object(events[position], {"event_id", "kind", "name", "value", "availability"}, "trace_invalid")
            if event["name"] != name:
                raise ContractError("trace_invalid")
            source[name] = event["value"]
        request = parse_request({"task_id": item["task_id"], "evidence": source})
        digest = item["digest"]
        if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ContractError("trace_invalid")
        body = {key: value for key, value in item.items() if key != "digest"}
        if not hmac.compare_digest(digest, hashlib.sha256(_canonical(body)).hexdigest()):
            raise ContractError("trace_invalid")
        expected = classify(request)
        if _canonical(item) != _canonical(trace_to_dict(expected)):
            raise ContractError("trace_invalid")
        return expected
    except (ContractError, TypeError, ValueError, OverflowError, RecursionError):
        raise ContractError("trace_invalid") from None
