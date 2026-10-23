"""Pure fictional evidence kernel with run-owned immutable records.

A belief is an exact distribution over three invented patterns. Likelihoods are
fixture assumptions P(band | pattern), not calibrated medical probabilities.
The parser constructs trusted records; this module owns evidence and review
transitions. No record, source label, or simulated review grants tool authority.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Literal

CONDITIONS = ("amber-pattern", "violet-pattern", "teal-pattern")
SIGNALS = ("glimmer", "ripple")
type Signal = Literal["glimmer", "ripple"]
type Band = Literal["low", "high"]
type ReviewDecision = Literal["pending", "acknowledged", "rejected"]
type Outcome = Literal["unresolved", "review_required", "simulated_reviewed", "review_rejected"]
type Vector = tuple[Fraction, Fraction, Fraction]


def stamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class BeliefDistribution:
    """Exact condition masses in CONDITIONS order, normalized by the boundary/kernel."""
    values: Vector

    def to_json(self) -> list[dict[str, str | float]]:
        return [{"condition": name, "probability": float(value), "exact": str(value)}
                for name, value in zip(CONDITIONS, self.values, strict=True)]


@dataclass(frozen=True, slots=True)
class Observation:
    """One unique signal's canonical ticks and source time, scoped to one run."""
    id: str
    signal: Signal
    ticks: Fraction
    observed_at: datetime

    @property
    def band(self) -> Band:
        return "high" if self.ticks >= Fraction(1, 2) else "low"


@dataclass(frozen=True, slots=True)
class KnowledgeRecord:
    """A supplied likelihood vector and its provenance, without authenticity claims."""
    id: str
    signal: Signal
    band: Band
    source: str
    version: str
    retrieved_at: datetime
    likelihoods: Vector

    def provenance(self) -> dict[str, str]:
        return {"id": self.id, "source": self.source, "version": self.version,
                "retrieved_at": stamp(self.retrieved_at)}


@dataclass(frozen=True, slots=True)
class Request:
    """Validated whole-run input. There is no persistent memory or identity."""
    as_of: datetime
    priors: BeliefDistribution
    observations: tuple[Observation, ...]
    knowledge: tuple[KnowledgeRecord, ...]
    review: ReviewDecision


@dataclass(frozen=True, slots=True)
class EvidenceEvent:
    """Normalized observation plus every matched record, including disputed sources."""
    observation: Observation
    records: tuple[KnowledgeRecord, ...]

    def to_json(self) -> dict:
        return {"observation_id": self.observation.id,
                "observed_at": stamp(self.observation.observed_at),
                "signal": self.observation.signal, "ticks": str(self.observation.ticks),
                "band": self.observation.band,
                "provenance": [record.provenance() for record in self.records]}


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    signal: Signal | None = None
    record_ids: tuple[str, ...] = ()

    def to_json(self) -> dict:
        return {"code": self.code, "signal": self.signal, "record_ids": list(self.record_ids)}


@dataclass(frozen=True, slots=True)
class ReviewResult:
    """A simulation decision that always has zero external approval/effect authority."""
    decision: ReviewDecision

    def to_json(self) -> dict:
        return {"decision": self.decision, "real_approval": False, "effect": "none"}


@dataclass(frozen=True, slots=True)
class Report:
    outcome: Outcome
    as_of: datetime
    priors: BeliefDistribution
    posterior: BeliefDistribution | None
    evidence: tuple[EvidenceEvent, ...]
    issues: tuple[Issue, ...]
    review: ReviewResult

    def to_json(self) -> dict:
        return {"schema_version": "synthetic-1", "mode": "fixture", "outcome": self.outcome,
                "as_of": stamp(self.as_of), "priors": self.priors.to_json(),
                "posterior": self.posterior.to_json() if self.posterior else None,
                "evidence": [event.to_json() for event in self.evidence],
                "issues": [issue.to_json() for issue in self.issues],
                "review": self.review.to_json()}


def evaluate(request: Request) -> Report:
    """Check evidence gates, update exact masses once per signal, then simulate review.

    Missing/stale/conflicting evidence invalidates the whole inference. Returning
    no partial posterior prevents an incomplete calculation looking conclusive.
    The two-signal and sixteen-record boundary bounds all loops here.
    """
    observations = {obs.signal: obs for obs in request.observations}
    events: list[EvidenceEvent] = []
    issues: list[Issue] = []
    vectors: list[Vector] = []
    for signal in SIGNALS:
        obs = observations.get(signal)
        if obs is None:
            issues.append(Issue("missing_observation", signal))
            continue
        records = tuple(sorted((record for record in request.knowledge
                                if record.signal == signal and record.band == obs.band),
                               key=lambda record: record.id))
        events.append(EvidenceEvent(obs, records))
        if request.as_of - obs.observed_at > timedelta(hours=24):
            issues.append(Issue("stale_observation", signal, (obs.id,)))
        if not records:
            issues.append(Issue("missing_knowledge", signal))
            continue
        stale = tuple(record.id for record in records
                      if request.as_of - record.retrieved_at > timedelta(days=30))
        if stale:
            issues.append(Issue("stale_knowledge", signal, stale))
        if any(record.likelihoods != records[0].likelihoods for record in records[1:]):
            # A newer source cannot silently erase a conflicting supplied source.
            issues.append(Issue("conflicting_knowledge", signal,
                                tuple(record.id for record in records)))
        # Identical sources add provenance, never another independent observation.
        vectors.append(records[0].likelihoods)

    posterior = None
    outcome: Outcome = "unresolved"
    if not issues:
        masses = list(request.priors.values)
        for vector in vectors:
            masses = [prior * likelihood for prior, likelihood in zip(masses, vector, strict=True)]
        total = sum(masses, Fraction(0))
        if total == 0:
            issues.append(Issue("zero_mass"))
        else:
            posterior = BeliefDistribution(tuple(mass / total for mass in masses))
            outcome = {"pending": "review_required", "acknowledged": "simulated_reviewed",
                       "rejected": "review_rejected"}[request.review]
    return Report(outcome, request.as_of, request.priors, posterior, tuple(events),
                  tuple(issues), ReviewResult(request.review))
