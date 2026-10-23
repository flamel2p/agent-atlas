"""Pure run-local discovery state machine over validated synthetic records.

The host selects a corpus gap, extrapolates singleton effects, checks virtual
budgets, then compares supplied measurements. Nothing learns or acts externally.
A gap is an absent pair in a declared corpus, never evidence of global novelty.
"""
from dataclasses import asdict, dataclass
from itertools import combinations
from statistics import fmean
from typing import Literal

Pair = tuple[str, str]
Status = Literal["coverage_incomplete", "no_gap", "constraint_blocked", "awaiting_measurements", "completed"]


@dataclass(frozen=True)
class Topic:
    id: str
    label: str


@dataclass(frozen=True)
class Paper:
    """One supplied synthetic assertion; provenance is retained without verification."""
    id: str
    title: str
    topics: tuple[str, ...]
    effect: float
    evidence: str
    citations: tuple[str, ...]
    source_id: str


@dataclass(frozen=True)
class CorpusRecord:
    """Immutable declared coverage scope and supplied records for one run."""
    id: str
    topics: tuple[Topic, ...]
    required_sources: tuple[str, ...]
    sources: tuple[str, ...]
    papers: tuple[Paper, ...]


@dataclass(frozen=True)
class Constraints:
    max_runs: int
    max_cost: float
    tolerance: float


@dataclass(frozen=True)
class Measurement:
    pair: Pair
    values: tuple[float, ...]


@dataclass(frozen=True)
class Request:
    corpus: CorpusRecord
    constraints: Constraints
    measurements: tuple[Measurement, ...]
    input_sha256: str


@dataclass(frozen=True)
class TestedPair:
    pair: Pair
    paper_ids: tuple[str, ...]


@dataclass(frozen=True)
class CoverageRecord:
    """Completeness only against caller-declared sources and local prerequisites."""
    complete: bool
    declared_sources: tuple[str, ...]
    observed_sources: tuple[str, ...]
    tested_pairs: tuple[TestedPair, ...]
    missing_sources: tuple[str, ...]
    empty_sources: tuple[str, ...]
    missing_citations: tuple[str, ...]
    missing_singleton_topics: tuple[str, ...]


@dataclass(frozen=True)
class GapCandidate:
    pair: Pair


@dataclass(frozen=True)
class TopicEstimate:
    """All singleton assertions contribute equally; range exposes disagreement."""
    topic: str
    mean_effect: float
    effect_range: tuple[float, float]
    evidence: tuple[Paper, ...]


@dataclass(frozen=True)
class Hypothesis:
    pair: Pair
    statement: str
    prediction: float
    tolerance: float
    falsification_rule: str
    estimates: tuple[TopicEstimate, ...]


@dataclass(frozen=True)
class Arm:
    topics: tuple[str, ...]
    predicted_effect: float
    repeats: int = 3


@dataclass(frozen=True)
class ExperimentPlan:
    """Proposed virtual controls; supplied data covers only the combined arm."""
    mode: str
    metric: str
    arms: tuple[Arm, ...]
    required_runs: int
    cost_per_run: int
    required_cost: int
    feasible: bool
    blocked_by: tuple[str, ...]
    measurement_scope: str


@dataclass(frozen=True)
class MeasurementFeedback:
    """Descriptive absolute error, with no significance or causal guarantee."""
    pair: Pair
    supplied_values: tuple[float, ...]
    prediction: float
    measured_mean: float
    absolute_error: float
    assessment: str
    update: str


@dataclass(frozen=True)
class Novelty:
    scope: str
    global_: str
    corpus_gap: str


@dataclass(frozen=True)
class Report:
    schema_version: int
    status: Status
    input_sha256: str
    corpus_id: str
    coverage: CoverageRecord
    novelty: Novelty
    candidates: tuple[GapCandidate, ...]
    hypothesis: Hypothesis | None
    experiment: ExperimentPlan | None
    feedback: MeasurementFeedback | None
    trace: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        result = asdict(self)
        # Python's reserved word has a JSON-facing spelling owned by this schema.
        result["novelty"]["global"] = result["novelty"].pop("global_")
        return result


def discover(request: Request) -> Report:
    """Return exactly one bounded terminal report; trust the parsed typed boundary."""
    corpus = request.corpus
    paper_ids = {paper.id for paper in corpus.papers}
    missing_sources = tuple(sorted(set(corpus.required_sources) - set(corpus.sources)))
    empty_sources = tuple(sorted(source for source in corpus.sources if not any(p.source_id == source for p in corpus.papers)))
    missing_citations = tuple(sorted({c for p in corpus.papers for c in p.citations if c not in paper_ids}))
    singleton_ids = {p.topics[0] for p in corpus.papers if len(p.topics) == 1}
    missing_singletons = tuple(sorted(t.id for t in corpus.topics if t.id not in singleton_ids))
    tested = {tuple(sorted(p.topics)) for p in corpus.papers if len(p.topics) == 2}
    tested_pairs = tuple(TestedPair((pair[0], pair[1]), tuple(sorted(p.id for p in corpus.papers if tuple(sorted(p.topics)) == pair))) for pair in sorted(tested))
    coverage = CoverageRecord(not any((missing_sources, empty_sources, missing_citations, missing_singletons)), tuple(sorted(corpus.required_sources)), tuple(sorted(corpus.sources)), tested_pairs, missing_sources, empty_sources, missing_citations, missing_singletons)
    trace = ["validated", "coverage_checked"]
    candidates: tuple[GapCandidate, ...] = ()
    hypothesis = None
    experiment = None
    feedback = None
    gap_state = "unverified"

    def finish(status: Status) -> Report:
        return Report(1, status, request.input_sha256, corpus.id, coverage,
                      Novelty("supplied_synthetic_corpus", "unverified", gap_state),
                      candidates, hypothesis, experiment, feedback, tuple(trace + [status]),
                      ("Synthetic assertions and simulated measurements only; no scientific validity or global novelty established.",
                       "Supplied measurements cover the combined arm only; planned controls are not observed.",
                       "Feedback records error only; no model, corpus, or host policy is updated."))

    # Missing evidence blocks interpretation before the host can consume simulation data.
    if not coverage.complete:
        return finish("coverage_incomplete")
    candidates = tuple(GapCandidate(pair) for pair in combinations(sorted(t.id for t in corpus.topics), 2) if pair not in tested)
    trace.append("gaps_enumerated")
    gap_state = "observed" if candidates else "absent"
    if not candidates:
        return finish("no_gap")
    pair = candidates[0].pair
    estimates = []
    for topic in pair:
        papers = tuple(sorted((p for p in corpus.papers if p.topics == (topic,)), key=lambda p: p.id))
        values = tuple(p.effect for p in papers)
        estimates.append(TopicEstimate(topic, fmean(values), (min(values), max(values)), papers))
    prediction = sum(e.mean_effect for e in estimates)
    tolerance = request.constraints.tolerance
    hypothesis = Hypothesis(pair, f"The combined {pair[0]} and {pair[1]} effect will be within {tolerance:g} response points of the additive prediction {prediction:g}.",
                            prediction, tolerance, "Refuted when abs(prediction - mean(supplied_combined_measurements)) > tolerance.", tuple(estimates))
    trace.append("hypothesis_proposed")
    blocked = tuple(name for name, fails in (("max_runs", request.constraints.max_runs < 12), ("max_cost", request.constraints.max_cost < 24)) if fails)
    experiment = ExperimentPlan("virtual_only", "synthetic_response_points", (Arm((), 0.0), Arm((pair[0],), estimates[0].mean_effect), Arm((pair[1],), estimates[1].mean_effect), Arm(pair, prediction)), 12, 2, 24, not blocked, blocked, "supplied_combined_arm_only")
    trace.append("experiment_budget_checked")
    if blocked:
        return finish("constraint_blocked")
    measurement = next((m for m in request.measurements if m.pair == pair), None)
    if measurement is None:
        return finish("awaiting_measurements")
    # Absolute error remains finite for zero outcomes; equality is accepted explicitly.
    measured = fmean(measurement.values)
    error = abs(prediction - measured)
    feedback = MeasurementFeedback(pair, measurement.values, prediction, measured, error,
                                   "consistent_with_prediction" if error <= tolerance else "prediction_refuted", "none")
    trace.append("simulated_feedback_recorded")
    return finish("completed")
