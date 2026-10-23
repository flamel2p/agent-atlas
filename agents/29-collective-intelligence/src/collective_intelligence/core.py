"""Host-owned proposal, review, and synthesis state machine.

All records are frozen and run scoped. A proposal is an attributed criterion,
not a vote. A critique is one directed reviewer-to-criterion edge. Consensus
means only that two bounded review matrices satisfy the host predicate; it
provides no correctness guarantee. Role adapters have no tools or side effects.
"""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal


class InvalidInput(ValueError):
    """Untrusted data violated the local contract; messages never echo data."""


@dataclass(frozen=True)
class Role:
    id: str
    weight: Fraction


@dataclass(frozen=True)
class Problem:
    id: str
    statement: str
    capacity: int


@dataclass(frozen=True)
class Criterion:
    id: str
    author_id: str
    text: str


@dataclass(frozen=True)
class Proposal:
    """Snapshot identity proves every adapter started from the same context."""

    author_id: str
    snapshot: Problem
    criterion: Criterion


@dataclass(frozen=True)
class Critique:
    id: str
    reviewer_id: str
    criterion_id: str
    score: Fraction
    reason: str


@dataclass(frozen=True)
class ReviewInput:
    number: int
    critiques: tuple[Critique, ...]


@dataclass(frozen=True)
class Request:
    problem_id: str
    max_rounds: int
    review_rounds: tuple[ReviewInput, ...] | None


@dataclass(frozen=True)
class Decision:
    """Score is absent when coverage is incomplete; weights never renormalize."""

    criterion: Criterion
    selection: Literal["accept", "reject", "defer"]
    score: Fraction | None
    expected_weight: Fraction
    observed_weight: Fraction
    critique_ids: tuple[str, ...]
    issues: tuple[str, ...]


@dataclass(frozen=True)
class RoundRecord:
    number: int
    critiques: tuple[Critique, ...]
    expected_edges: tuple[tuple[str, str], ...]
    missing_edges: tuple[tuple[str, str], ...]
    decisions: tuple[Decision, ...]
    converged: bool


@dataclass(frozen=True)
class ConsensusResult:
    status: Literal["converged", "unresolved"]
    problem: Problem
    roles: tuple[Role, ...]
    proposals: tuple[Proposal, ...]
    rounds: tuple[RoundRecord, ...]
    rubric: tuple[Criterion, ...]
    dissent: tuple[Critique, ...]
    unresolved: tuple[str, ...]

    def to_dict(self) -> dict:
        """Serialize provenance without rounding values used by host policy."""
        def criterion(c: Criterion) -> dict:
            return {"id": c.id, "author_id": c.author_id, "text": c.text}

        def critique(c: Critique) -> dict:
            return {"id": c.id, "reviewer_id": c.reviewer_id,
                    "criterion_id": c.criterion_id, "score": display(c.score),
                    "score_exact": exact(c.score), "reason": c.reason}

        return {
            "status": self.status, "mode": "fixture", "correctness_claim": False,
            "provisional": self.status != "converged",
            "problem": {"id": self.problem.id, "statement": self.problem.statement,
                        "capacity": self.problem.capacity},
            "roles": [{"id": r.id, "weight": display(r.weight)} for r in self.roles],
            "proposals": [{"author_id": p.author_id,
                           "snapshot_id": p.snapshot.id,
                           "criterion": criterion(p.criterion)} for p in self.proposals],
            "rounds": [{"number": r.number, "converged": r.converged,
                        "expected_edges": [list(e) for e in r.expected_edges],
                        "missing_edges": [list(e) for e in r.missing_edges],
                        "critiques": [critique(c) for c in r.critiques],
                        "decisions": [{"criterion": criterion(d.criterion),
                                       "selection": d.selection,
                                       "score": display(d.score),
                                       "score_exact": exact(d.score),
                                       "expected_weight": display(d.expected_weight),
                                       "observed_weight": display(d.observed_weight),
                                       "critique_ids": list(d.critique_ids),
                                       "issues": list(d.issues)} for d in r.decisions]}
                       for r in self.rounds],
            "rubric": [criterion(c) for c in self.rubric],
            "dissent": [critique(c) for c in self.dissent],
            "unresolved": list(self.unresolved),
        }


def exact(value: Fraction | None) -> dict | None:
    return None if value is None else {"numerator": value.numerator, "denominator": value.denominator}


def display(value: Fraction | None) -> float | None:
    return None if value is None else round(float(value), 6)


ROLES = (Role("pedagogy", Fraction(3)), Role("domain", Fraction(2)),
         Role("assessment", Fraction(1)))
PROBLEM = Problem("bounded-queue-v1",
                  "Implement a queue of capacity 3 that preserves FIFO order and "
                  "rejects overflow without mutating its state.", 3)
CRITERIA = (
    Criterion("c-pedagogy", "pedagogy", "Demonstrate observable FIFO behavior with examples."),
    Criterion("c-domain", "domain", "Enforce capacity and preserve state on rejected overflow."),
    Criterion("c-assessment", "assessment", "Explain representation invariants in a short rationale."),
)
THRESHOLD = Fraction(6)


def propose(role: Role, snapshot: Problem) -> Proposal:
    """Each adapter sees only its role and immutable problem, never prior work."""
    return Proposal(role.id, snapshot, next(c for c in CRITERIA if c.author_id == role.id))


def validate_roles(roles: tuple[Role, ...]) -> None:
    if (tuple(r.id for r in roles) != ("pedagogy", "domain", "assessment")
            or any(type(r.weight) is not Fraction or r.weight <= 0 for r in roles)):
        raise InvalidInput("Invalid host roles")


def expected_edges(proposals: tuple[Proposal, ...]) -> tuple[tuple[str, str], ...]:
    return tuple((r.id, p.criterion.id) for p in proposals for r in ROLES
                 if r.id != p.author_id)


def validate_reviews(number: int, critiques: tuple[Critique, ...],
                     proposals: tuple[Proposal, ...]) -> None:
    """Missing edges are evidence gaps; duplicate or forged edges are invalid."""
    allowed = set(expected_edges(proposals))
    seen: set[tuple[str, str]] = set()
    if len(critiques) > 6:
        raise InvalidInput("Invalid review count")
    for c in critiques:
        edge = (c.reviewer_id, c.criterion_id)
        if (edge not in allowed or edge in seen
                or c.id != f"r{number}-{c.reviewer_id}-{c.criterion_id}"
                or type(c.score) is not Fraction or not 0 <= c.score <= 10
                or type(c.reason) is not str or not c.reason.strip() or len(c.reason) > 240):
            raise InvalidInput("Invalid review graph")
        seen.add(edge)


def fixture_reviews(number: int, proposals: tuple[Proposal, ...]) -> tuple[Critique, ...]:
    """Original illustrative judgments, with no expert-accuracy interpretation."""
    scores = {("domain", "c-pedagogy"): 8, ("assessment", "c-pedagogy"): 9,
              ("pedagogy", "c-domain"): 9, ("assessment", "c-domain"): 8,
              ("pedagogy", "c-assessment"): 3, ("domain", "c-assessment"): 4}
    return tuple(Critique(f"r{number}-{reviewer}-{cid}", reviewer, cid,
                         Fraction(scores[reviewer, cid]),
                         "Observable evidence supports this criterion." if scores[reviewer, cid] > 6
                         else "Rationale alone provides weak observable assessment evidence.")
                 for reviewer, cid in expected_edges(proposals))


def aggregate(criterion: Criterion, critiques: tuple[Critique, ...]) -> Decision:
    peers = tuple(r for r in ROLES if r.id != criterion.author_id)
    relevant = tuple(c for c in critiques if c.criterion_id == criterion.id)
    weights = {r.id: r.weight for r in peers}
    expected = sum(weights.values(), Fraction())
    observed = sum((weights[c.reviewer_id] for c in relevant), Fraction())
    issues = []
    score = None
    if observed != expected:
        issues.append("missing_reviews")
    else:
        score = sum((weights[c.reviewer_id] * c.score for c in relevant), Fraction()) / expected
        if score == THRESHOLD:
            issues.append("threshold_tie")
        if any(c.score == THRESHOLD for c in relevant):
            issues.append("reviewer_tie")
        if any(c.score < THRESHOLD for c in relevant) and any(c.score > THRESHOLD for c in relevant):
            issues.append("contradictory_scores")
    selection = "defer" if issues else "accept" if score > THRESHOLD else "reject"
    return Decision(criterion, selection, score, expected, observed,
                    tuple(c.id for c in relevant), tuple(issues))


def convergence(previous: RoundRecord | None, decisions: tuple[Decision, ...],
                missing: tuple[tuple[str, str], ...]) -> bool:
    """Require two complete resolved rounds and exact score movement <= 1/4."""
    if previous is None or previous.missing_edges or missing:
        return False
    return all(a.selection == b.selection != "defer"
               and a.score is not None and b.score is not None
               and abs(a.score - b.score) <= Fraction(1, 4)
               for a, b in zip(previous.decisions, decisions, strict=True))


def run_session(request: Request) -> ConsensusResult:
    """Execute only validated requests; bounded adapters return validated data.

    Shared state starts after all independent proposals have been collected.
    The host owns convergence and synthesis. No adapter may certify its output.
    """
    validate_roles(ROLES)
    if (request.problem_id != PROBLEM.id or type(request.max_rounds) is not int
            or request.max_rounds not in (1, 2)
            or (request.review_rounds is not None
                and len(request.review_rounds) != request.max_rounds)):
        raise InvalidInput("Invalid session")
    proposals = tuple(propose(role, PROBLEM) for role in ROLES)
    if (tuple(p.author_id for p in proposals) != tuple(r.id for r in ROLES)
            or tuple(p.criterion for p in proposals) != CRITERIA
            or any(p.snapshot is not PROBLEM for p in proposals)):
        raise InvalidInput("Invalid proposals")
    records: list[RoundRecord] = []
    expected = expected_edges(proposals)
    for number in range(1, request.max_rounds + 1):
        source = None if request.review_rounds is None else request.review_rounds[number - 1]
        if source is not None and (type(source.number) is not int or source.number != number):
            raise InvalidInput("Invalid round")
        critiques = fixture_reviews(number, proposals) if source is None else source.critiques
        validate_reviews(number, critiques, proposals)
        edges = {(c.reviewer_id, c.criterion_id) for c in critiques}
        missing = tuple(e for e in expected if e not in edges)
        decisions = tuple(aggregate(p.criterion, critiques) for p in proposals)
        stable = convergence(records[-1] if records else None, decisions, missing)
        records.append(RoundRecord(number, critiques, expected, missing, decisions, stable))
        if stable:
            break
    last = records[-1]
    selected = tuple(d.criterion for d in last.decisions if d.selection == "accept")
    deferred = {d.criterion.id for d in last.decisions if d.selection == "defer"}
    dissent = tuple(c for c in last.critiques
                    if c.score <= THRESHOLD or c.criterion_id in deferred)
    unresolved = () if last.converged else ("budget_exhausted",) + tuple(
        f"{d.criterion.id}:{issue}" for d in last.decisions for issue in d.issues)
    return ConsensusResult("converged" if last.converged else "unresolved", PROBLEM,
                           ROLES, proposals, tuple(records), selected, dissent, unresolved)
