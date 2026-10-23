"""Host-owned synthetic teaching policy and run-scoped learner transitions.

The boundary parser constructs immutable domain records. A session assesses fixed
answer keys, applies observation then learning, and chooses eligible practice or
due review. BKT mastery is an illustrative probability, not a certification. The
DAG is a directed acyclic prerequisite graph, limited to the local catalog.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import json
import math
import re
from typing import Literal

THRESHOLD = 0.8
MAX_BYTES = 32768
MAX_ANSWERS = 12
MAX_ATTEMPTS = 10000
CATALOG = {
    "count": ("How many stones are in [stone, stone, stone]?", "3",
              ("Count each stone once.", "Point to each stone as you count.", "Ask a teacher to count with you.")),
    "add": ("What is 2 + 3?", "5",
            ("Start with two counters.", "Add three more counters and count all of them.", "Ask a teacher to model this sum.")),
    "multiply": ("What is 2 * 3?", "6",
                 ("Think of two groups of three.", "Count three counters twice.", "Ask a teacher to model equal groups.")),
}


class InvalidInput(Exception):
    """Only fixed host codes cross the CLI error boundary."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def probability(value: object) -> float:
    if type(value) not in (int, float):
        raise InvalidInput("invalid_probability")
    try:
        result = float(value)
    except OverflowError:
        raise InvalidInput("invalid_probability") from None
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise InvalidInput("invalid_probability")
    return result


@dataclass(frozen=True)
class BKTParameters:
    """Guess, slip, and learn probabilities shared by this synthetic session."""

    guess: float
    slip: float
    learn: float

    def __post_init__(self):
        for value in (self.guess, self.slip, self.learn):
            probability(value)


@dataclass(frozen=True)
class ObjectiveGraph:
    """Validated unique catalog nodes and direct prerequisite edges."""

    nodes: tuple[tuple[str, tuple[str, ...]], ...]

    def eligible(self, state: dict[str, "LearnerState"]) -> list[str]:
        return sorted(name for name, parents in self.nodes
                      if all(state[parent].mastery >= THRESHOLD for parent in parents))


@dataclass(frozen=True)
class ReviewSchedule:
    """Last assessed evidence and due review time; both absent for a cold start."""

    last_evidence: datetime | None
    due_at: datetime | None


@dataclass(frozen=True)
class LearnerState:
    """Caller-supplied per-objective belief and counters, owned by one run."""

    objective: str
    mastery: float
    attempts: int
    failures: int
    schedule: ReviewSchedule

    def record(self) -> dict:
        return {"objective": self.objective, "mastery": self.mastery,
                "attempts": self.attempts, "failures": self.failures,
                "last_evidence": stamp(self.schedule.last_evidence),
                "due_at": stamp(self.schedule.due_at)}


@dataclass(frozen=True)
class AnswerEvidence:
    """Synthetic answer data. A null answer supplies no assessment evidence."""

    objective: str
    answer: str | None
    observed_at: datetime


@dataclass(frozen=True)
class Session:
    """Fully parsed request. No input file handle or persistent state survives."""

    now: datetime
    parameters: BKTParameters
    graph: ObjectiveGraph
    state: tuple[LearnerState, ...]
    answers: tuple[AnswerEvidence, ...]


@dataclass(frozen=True)
class LearningResult:
    """Terminal report. Returned state can be supplied explicitly next time."""

    status: Literal["teacher_review", "evidence_required", "completed", "practice_required"]
    state: tuple[LearnerState, ...]
    trace: tuple[dict, ...]
    eligible: tuple[str, ...]
    practice: tuple[str, ...]
    due_reviews: tuple[dict, ...]
    next_activity: dict | None
    unprocessed_answers: int

    def record(self) -> dict:
        return {"status": self.status, "threshold": THRESHOLD,
                "state": [item.record() for item in self.state],
                "trace": list(self.trace), "eligible": list(self.eligible),
                "practice": list(self.practice), "due_reviews": list(self.due_reviews),
                "next_activity": self.next_activity,
                "unprocessed_answers": self.unprocessed_answers,
                "limits": {"answers": 12, "objectives": 3, "hints": 3, "attempts": 10000}}


def stamp(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


def timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value):
        raise InvalidInput("invalid_time")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise InvalidInput("invalid_time") from None


def fields(value: object, names: str) -> dict:
    if type(value) is not dict or set(value) != set(names.split()):
        raise InvalidInput("invalid_schema")
    return value


def array(value: object, maximum: int, minimum: int = 0) -> list:
    if type(value) is not list:
        raise InvalidInput("invalid_schema")
    if not minimum <= len(value) <= maximum:
        raise InvalidInput("bound_exceeded")
    return value


def identifier(value: object, allowed: set[str]) -> str:
    if type(value) is not str or value not in allowed:
        raise InvalidInput("invalid_graph")
    return value


def integer(value: object, maximum: int) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise InvalidInput("invalid_state")
    return value


def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidInput("invalid_json")
        result[key] = value
    return result


def reject_constant(_: str):
    raise InvalidInput("invalid_json")


def depth(value: object, level: int = 1):
    if level > 12:
        raise InvalidInput("bound_exceeded")
    if type(value) is dict:
        for item in value.values():
            depth(item, level + 1)
    elif type(value) is list:
        for item in value:
            depth(item, level + 1)
    elif type(value) is float and not math.isfinite(value):
        raise InvalidInput("invalid_json")


def parse_request(raw: bytes) -> Session:
    """Validate the entire external JSON boundary before any state transition."""
    if len(raw) > MAX_BYTES:
        raise InvalidInput("bound_exceeded")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs,
                          parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise InvalidInput("invalid_json") from None
    depth(data)
    data = fields(data, "now parameters graph state answers")
    now = timestamp(data["now"])
    if now.date().isoformat() > "2099-12-24":
        raise InvalidInput("invalid_time")
    parameters = fields(data["parameters"], "guess slip learn")
    params = BKTParameters(*(probability(parameters[name]) for name in ("guess", "slip", "learn")))
    nodes = []
    for value in array(data["graph"], 3, 1):
        node = fields(value, "objective prerequisites")
        name = identifier(node["objective"], set(CATALOG))
        parents = tuple(identifier(p, set(CATALOG)) for p in array(node["prerequisites"], 2))
        if name in parents or len(set(parents)) != len(parents):
            raise InvalidInput("invalid_graph")
        nodes.append((name, parents))
    names = {name for name, _ in nodes}
    if len(names) != len(nodes) or any(p not in names for _, parents in nodes for p in parents):
        raise InvalidInput("invalid_graph")
    # Removing all ready nodes proves acyclicity without recursive graph traversal.
    remaining = dict(nodes)
    visited = set()
    while remaining:
        ready = {name for name, parents in remaining.items() if set(parents) <= visited}
        if not ready:
            raise InvalidInput("invalid_graph")
        visited.update(ready)
        remaining = {name: parents for name, parents in remaining.items() if name not in ready}
    states = []
    for value in array(data["state"], 3, 1):
        item = fields(value, "objective mastery attempts failures last_evidence due_at")
        name = identifier(item["objective"], names)
        mastery = probability(item["mastery"])
        attempts = integer(item["attempts"], MAX_ATTEMPTS)
        failures = integer(item["failures"], 3)
        last = timestamp(item["last_evidence"]) if item["last_evidence"] is not None else None
        due = timestamp(item["due_at"]) if item["due_at"] is not None else None
        if failures > attempts or (attempts == 0 and (last is not None or due is not None)):
            raise InvalidInput("invalid_state")
        if attempts > 0 and (last is None or due is None or last > now or due <= last):
            raise InvalidInput("invalid_state")
        states.append(LearnerState(name, mastery, attempts, failures, ReviewSchedule(last, due)))
    if len({s.objective for s in states}) != len(states) or {s.objective for s in states} != names:
        raise InvalidInput("invalid_state")
    answers = []
    previous = None
    for value in array(data["answers"], MAX_ANSWERS):
        item = fields(value, "objective answer observed_at")
        name = identifier(item["objective"], names)
        answer = item["answer"]
        if answer is not None and type(answer) is not str:
            raise InvalidInput("invalid_schema")
        if answer is not None and len(answer) > 128:
            raise InvalidInput("bound_exceeded")
        observed = timestamp(item["observed_at"])
        if observed > now or (previous is not None and observed < previous):
            raise InvalidInput("invalid_time")
        previous = observed
        answers.append(AnswerEvidence(name, answer, observed))
    return Session(now, params, ObjectiveGraph(tuple(nodes)), tuple(states), tuple(answers))


def update_mastery(prior: float, correct: bool, params: BKTParameters) -> tuple[float, float]:
    """Return observation posterior then post-learning belief, in that order."""
    p = probability(prior)
    likelihood_known = 1 - params.slip if correct else params.slip
    likelihood_unknown = params.guess if correct else 1 - params.guess
    numerator = p * likelihood_known
    denominator = numerator + (1 - p) * likelihood_unknown
    if denominator == 0:
        raise InvalidInput("impossible_observation")
    posterior = numerator / denominator
    learned = posterior + (1 - posterior) * params.learn
    return probability(posterior), probability(learned)


def run(session: Session) -> LearningResult:
    """Apply evidence atomically on a private copy, then plan one next activity.

    Dynamic validation errors discard the whole run. Teacher review is a valid
    terminal state and keeps only the processed prefix, explicitly counted.
    """
    state = {item.objective: item for item in session.state}
    trace = []
    teacher = any(item.failures == 3 for item in state.values())
    missing = False
    for answer in session.answers:
        if teacher:
            break
        name = answer.objective
        item = state[name]
        if name not in session.graph.eligible(state):
            raise InvalidInput("ineligible_objective")
        if answer.answer is None:
            missing = True
            trace.append({"objective": name, "assessment": "missing", "prior": item.mastery,
                          "posterior": None, "mastery": item.mastery, "hint_level": item.failures, "hint": None})
            continue
        if item.schedule.last_evidence is not None and answer.observed_at <= item.schedule.last_evidence:
            raise InvalidInput("replayed_evidence")
        if item.attempts == MAX_ATTEMPTS:
            raise InvalidInput("bound_exceeded")
        correct = answer.answer.strip() == CATALOG[name][1]
        posterior, mastery = update_mastery(item.mastery, correct, session.parameters)
        failures = 0 if correct else item.failures + 1
        interval = 7 if correct and mastery >= THRESHOLD else 1
        # Schedule from evidence time so old observations do not postpone due work.
        schedule = ReviewSchedule(answer.observed_at, answer.observed_at + timedelta(days=interval))
        state[name] = replace(item, mastery=mastery, attempts=item.attempts + 1,
                              failures=failures, schedule=schedule)
        trace.append({"objective": name, "assessment": "correct" if correct else "incorrect",
                      "prior": item.mastery, "posterior": posterior, "mastery": mastery,
                      "hint_level": failures, "hint": CATALOG[name][2][failures - 1] if failures else None})
        teacher = failures == 3
    eligible = session.graph.eligible(state)
    practice = [name for name in eligible if state[name].mastery < THRESHOLD]
    due = sorted(({"objective": name, "due_at": stamp(state[name].schedule.due_at)}
                  for name in eligible if state[name].schedule.due_at is not None
                  and state[name].schedule.due_at <= session.now), key=lambda item: (item["due_at"], item["objective"]))
    status = ("teacher_review" if teacher else "evidence_required" if missing else
              "completed" if all(item.mastery >= THRESHOLD for item in state.values()) else "practice_required")
    next_activity = None
    if not teacher and (due or practice):
        name = due[0]["objective"] if due else practice[0]
        next_activity = {"kind": "review" if due else "practice", "objective": name, "prompt": CATALOG[name][0]}
    return LearningResult(status, tuple(state[name] for name in sorted(state)), tuple(trace), tuple(eligible),
                          tuple(practice), tuple(due), next_activity, len(session.answers) - len(trace))
