"""One governed learning cycle over immutable synthetic FAQ snapshots.

Selection sees only replay traces, untrusted corrections, separate host curator
records, and development controls. It may change one configuration field for
one topic. The coordinator freezes that proposal before heldout evaluation.
All values and reports live for one call; no version is activated or persisted.
The exact-document-ID metric measures this fixture policy, not semantic quality.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
import json
from typing import TypeAlias


SCHEMA_VERSION = 1
ALGORITHM_VERSION = "topic-revision-tiebreak-v1"
MIN_SUPPORT = 2


def _canonical(value: object) -> str:
    """Serialize detached JSON data or frozen records without volatile values."""
    def encode(item: object) -> object:
        if hasattr(item, "__dataclass_fields__"):
            return asdict(item)
        raise TypeError(f"Cannot encode {type(item).__name__}")

    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False, default=encode)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Document:
    document_id: str
    topic: str
    revision: int
    tokens: tuple[str, ...]
    answer: str


@dataclass(frozen=True)
class Query:
    query_id: str
    topic: str
    tokens: tuple[str, ...]

    @property
    def signature(self) -> tuple[str, tuple[str, ...]]:
        """Identity of normalized query content, excluding the arbitrary ID."""
        return self.topic, self.tokens


@dataclass(frozen=True)
class RetrievalConfig:
    """The only adaptation field enables a revision tie-breaker for one topic."""
    recency_topic: str | None


@dataclass(frozen=True)
class BehaviorVersion:
    """Content identity binds config, corpus, parent, algorithm, and support.

    Frozen records prevent in-run mutation. SHA-256 gives an integrity identity,
    not authentication, a signature, or protection from a hostile fixture editor.
    """
    version_id: str
    algorithm_version: str
    corpus_digest: str
    config: RetrievalConfig
    parent_version_id: str | None
    evidence_digest: str | None


def _version(corpus_digest: str, config: RetrievalConfig,
             parent_version_id: str | None = None,
             evidence_digest: str | None = None) -> BehaviorVersion:
    payload = dict(algorithm_version=ALGORITHM_VERSION,
                   corpus_digest=corpus_digest, config=config,
                   parent_version_id=parent_version_id,
                   evidence_digest=evidence_digest)
    return BehaviorVersion(version_id=_digest(payload), **payload)


@dataclass(frozen=True)
class Trace:
    trace_id: str
    query: Query
    baseline_version_id: str
    observed_document_id: str | None


@dataclass(frozen=True)
class Feedback:
    feedback_id: str
    trace_id: str
    target_document_id: str
    curator_record_id: str


@dataclass(frozen=True)
class CuratorRecord:
    """Host fixture-author assertion, kept separate from untrusted feedback.

    The local author supplies labels; this demo does not authenticate people or
    independently verify those labels as truth.
    """
    record_id: str
    trace_id: str
    target_document_id: str


class Group(StrEnum):
    CORRECTION = "correction"
    DEVELOPMENT = "development"
    RECENT = "recent"
    STABLE = "stable"


@dataclass(frozen=True)
class LabeledCase:
    query: Query
    expected_document_id: str | None
    group: Group


@dataclass(frozen=True)
class SelectionInput:
    """Proposal-visible input deliberately has no holdout query or label field."""
    corpus: tuple[Document, ...]
    baseline: BehaviorVersion
    traces: tuple[Trace, ...]
    feedback: tuple[Feedback, ...]
    curator_records: tuple[CuratorRecord, ...]
    development_controls: tuple[LabeledCase, ...]


@dataclass(frozen=True)
class ScenarioData:
    """Validated loader output. All nested collections are frozen tuples."""
    name: str
    selection: SelectionInput
    holdout: tuple[LabeledCase, ...]


@dataclass(frozen=True)
class RankedDocument:
    document_id: str
    overlap: int
    revision: int


@dataclass(frozen=True)
class Retrieval:
    selected_document_id: str | None
    answer: str | None
    ranking: tuple[RankedDocument, ...]


def _retrieve(query: Query, corpus: tuple[Document, ...],
              behavior: BehaviorVersion) -> Retrieval:
    """Rank positive-overlap documents in the declared topic only.

    Revision can resolve an overlap tie. It cannot overpower relevance or grant
    topic authority. Revisions are synthetic order, not verified timestamps.
    """
    ranked = tuple(RankedDocument(doc.document_id,
                                 len(set(query.tokens).intersection(doc.tokens)),
                                 doc.revision)
                   for doc in corpus if doc.topic == query.topic
                   and set(query.tokens).intersection(doc.tokens))
    use_revision = behavior.config.recency_topic == query.topic
    ranked = tuple(sorted(ranked, key=lambda doc: (
        -doc.overlap, -doc.revision if use_revision else 0, doc.document_id)))
    if not ranked:
        return Retrieval(None, None, ())
    selected = next(doc for doc in corpus if doc.document_id == ranked[0].document_id)
    return Retrieval(selected.document_id, selected.answer, ranked)


class FeedbackDisposition(StrEnum):
    ELIGIBLE = "eligible"
    EXCLUDED = "excluded"


class FeedbackReason(StrEnum):
    ELIGIBLE = "eligible"
    CONFLICTED_TRACE = "conflicted_trace"
    UNKNOWN_TRACE = "unknown_trace"
    UNKNOWN_TARGET = "unknown_target"
    WRONG_BASELINE = "wrong_baseline"
    REPLAY_MISMATCH = "replay_mismatch"
    CROSS_TOPIC = "cross_topic"
    IRRELEVANT_TARGET = "irrelevant_target"
    UNKNOWN_CURATOR = "unknown_curator"
    CURATOR_MISMATCH = "curator_mismatch"
    NOT_BASELINE_FAILURE = "not_baseline_failure"
    NOT_NEWER = "not_newer"
    DUPLICATE_TRACE = "duplicate_trace"
    DUPLICATE_QUERY = "duplicate_query_signature"


@dataclass(frozen=True)
class FeedbackDecision:
    feedback_id: str
    trace_id: str
    target_document_id: str
    disposition: FeedbackDisposition
    reason: FeedbackReason


@dataclass(frozen=True)
class SupportingEvidence:
    """Replayed observation and its separate authority record travel together."""
    feedback: Feedback
    trace: Trace
    curator_record: CuratorRecord


@dataclass(frozen=True)
class Proposal:
    candidate: BehaviorVersion
    topic: str
    supporting_feedback_ids: tuple[str, ...]
    evidence_digest: str
    supporting_evidence: tuple[SupportingEvidence, ...]


class NoProposalStatus(StrEnum):
    INSUFFICIENT = "no_proposal_insufficient"
    AMBIGUOUS = "no_proposal_ambiguous"


@dataclass(frozen=True)
class _NoProposal:
    status: NoProposalStatus
    qualifying_topics: tuple[str, ...]
    feedback: tuple[FeedbackDecision, ...]


@dataclass(frozen=True)
class _SelectedProposal:
    proposal: Proposal
    corrections: tuple[LabeledCase, ...]
    feedback: tuple[FeedbackDecision, ...]


def _select(data: SelectionInput) -> _NoProposal | _SelectedProposal:
    """Curate and select once, without any access to the heldout partition."""
    documents = {doc.document_id: doc for doc in data.corpus}
    traces = {trace.trace_id: trace for trace in data.traces}
    curators = {record.record_id: record for record in data.curator_records}
    targets_by_trace: dict[str, set[str]] = {}
    for feedback in data.feedback:
        targets_by_trace.setdefault(feedback.trace_id, set()).add(feedback.target_document_id)
    conflicted = {trace_id for trace_id, targets in targets_by_trace.items() if len(targets) > 1}
    decisions = []
    eligible: list[tuple[Feedback, Trace, CuratorRecord]] = []
    used_traces: set[str] = set()
    used_queries: set[tuple[str, tuple[str, ...]]] = set()
    for feedback in data.feedback:
        trace = traces.get(feedback.trace_id)
        target = documents.get(feedback.target_document_id)
        curator = curators.get(feedback.curator_record_id)
        reason = FeedbackReason.ELIGIBLE
        # Conflict is trace-wide, so a second target cannot leave the first counted.
        if feedback.trace_id in conflicted:
            reason = FeedbackReason.CONFLICTED_TRACE
        elif trace is None:
            reason = FeedbackReason.UNKNOWN_TRACE
        elif target is None:
            reason = FeedbackReason.UNKNOWN_TARGET
        elif trace.baseline_version_id != data.baseline.version_id:
            reason = FeedbackReason.WRONG_BASELINE
        elif _retrieve(trace.query, data.corpus, data.baseline).selected_document_id != trace.observed_document_id:
            reason = FeedbackReason.REPLAY_MISMATCH
        elif target.topic != trace.query.topic:
            reason = FeedbackReason.CROSS_TOPIC
        elif not set(target.tokens).intersection(trace.query.tokens):
            reason = FeedbackReason.IRRELEVANT_TARGET
        elif curator is None:
            reason = FeedbackReason.UNKNOWN_CURATOR
        elif (curator.trace_id, curator.target_document_id) != (trace.trace_id, target.document_id):
            reason = FeedbackReason.CURATOR_MISMATCH
        elif trace.observed_document_id is None or target.document_id == trace.observed_document_id:
            reason = FeedbackReason.NOT_BASELINE_FAILURE
        elif target.revision <= documents[trace.observed_document_id].revision:
            reason = FeedbackReason.NOT_NEWER
        elif trace.trace_id in used_traces:
            reason = FeedbackReason.DUPLICATE_TRACE
        elif trace.query.signature in used_queries:
            reason = FeedbackReason.DUPLICATE_QUERY
        if reason == FeedbackReason.ELIGIBLE:
            eligible.append((feedback, trace, curator))
            used_traces.add(trace.trace_id)
            used_queries.add(trace.query.signature)
        decisions.append(FeedbackDecision(
            feedback.feedback_id, feedback.trace_id, feedback.target_document_id,
            FeedbackDisposition.ELIGIBLE if reason == FeedbackReason.ELIGIBLE
            else FeedbackDisposition.EXCLUDED, reason))
    topics = sorted({trace.query.topic for _, trace, _ in eligible})
    qualifying = tuple(topic for topic in topics if sum(
        trace.query.topic == topic for _, trace, _ in eligible) >= MIN_SUPPORT)
    if len(qualifying) != 1:
        status = NoProposalStatus.AMBIGUOUS if qualifying else NoProposalStatus.INSUFFICIENT
        return _NoProposal(status, qualifying, tuple(decisions))
    topic = qualifying[0]
    support = tuple(item for item in eligible if item[1].query.topic == topic)
    supporting_evidence = tuple(SupportingEvidence(feedback, trace, curator)
                                for feedback, trace, curator in support)
    evidence_digest = _digest(supporting_evidence)
    candidate = _version(data.baseline.corpus_digest, RetrievalConfig(topic),
                         data.baseline.version_id, evidence_digest)
    proposal = Proposal(candidate, topic,
                        tuple(item[0].feedback_id for item in support), evidence_digest,
                        supporting_evidence)
    corrections = tuple(LabeledCase(trace.query, feedback.target_document_id, Group.CORRECTION)
                        for feedback, trace, _ in support)
    return _SelectedProposal(proposal, corrections, tuple(decisions))


@dataclass(frozen=True)
class CaseResult:
    query: Query
    group: Group
    expected_document_id: str | None
    baseline: Retrieval
    candidate: Retrieval
    baseline_correct: bool
    candidate_correct: bool


@dataclass(frozen=True)
class GroupCount:
    group: Group
    cases: int
    baseline_correct: int
    candidate_correct: int


@dataclass(frozen=True)
class Evaluation:
    """Paired exact-ID outcomes include all cases, not only the aggregate gain."""
    cases: tuple[CaseResult, ...]
    groups: tuple[GroupCount, ...]
    baseline_correct: int
    candidate_correct: int
    gained_query_ids: tuple[str, ...]
    lost_query_ids: tuple[str, ...]


def _evaluate(corpus: tuple[Document, ...], baseline: BehaviorVersion,
              candidate: BehaviorVersion, cases: tuple[LabeledCase, ...]) -> Evaluation:
    results = []
    for case in cases:
        before = _retrieve(case.query, corpus, baseline)
        after = _retrieve(case.query, corpus, candidate)
        results.append(CaseResult(case.query, case.group, case.expected_document_id,
                                  before, after,
                                  before.selected_document_id == case.expected_document_id,
                                  after.selected_document_id == case.expected_document_id))
    group_counts = tuple(GroupCount(group, sum(case.group == group for case in results),
                                    sum(case.baseline_correct for case in results if case.group == group),
                                    sum(case.candidate_correct for case in results if case.group == group))
                         for group in Group if any(case.group == group for case in results))
    return Evaluation(tuple(results), group_counts,
                      sum(case.baseline_correct for case in results),
                      sum(case.candidate_correct for case in results),
                      tuple(case.query.query_id for case in results
                            if not case.baseline_correct and case.candidate_correct),
                      tuple(case.query.query_id for case in results
                            if case.baseline_correct and not case.candidate_correct))


class DevelopmentStatus(StrEnum):
    REJECTED = "rejected_development"


class EvaluatedStatus(StrEnum):
    REVIEW_REQUIRED = "review_required"
    REGRESSION = "rejected_regression"
    NO_GAIN = "rejected_no_gain"


@dataclass(frozen=True)
class _Report:
    """Common provenance for mutually exclusive terminal report variants.

    Returned dictionaries are detached serialization values. The report itself
    stays frozen and has no capability to approve or activate a candidate.
    """
    schema_version: int
    algorithm_version: str
    scenario_name: str
    corpus_digest: str
    selection_digest: str
    holdout_digest: str
    baseline: BehaviorVersion
    serving_version_id: str
    feedback: tuple[FeedbackDecision, ...]
    gate_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["report_digest"] = _digest(payload)
        # Round-tripping converts enums and tuples into their public JSON forms.
        return json.loads(_canonical(payload))

    def to_json(self) -> str:
        return _canonical(self.to_dict())


@dataclass(frozen=True)
class NoCandidateReport(_Report):
    status: NoProposalStatus
    qualifying_topics: tuple[str, ...]


@dataclass(frozen=True)
class DevelopmentRejectedReport(_Report):
    status: DevelopmentStatus
    proposal: Proposal
    development: Evaluation


@dataclass(frozen=True)
class EvaluatedReport(_Report):
    status: EvaluatedStatus
    proposal: Proposal
    development: Evaluation
    heldout: Evaluation


ExperimentReport: TypeAlias = NoCandidateReport | DevelopmentRejectedReport | EvaluatedReport


def run_experiment(scenario: ScenarioData) -> ExperimentReport:
    """Run one validated scenario, return its terminal record, and retain baseline.

    `load_scenario` owns external validation. This pure library operation trusts
    that boundary rather than rechecking frozen internal records at every call.
    Proposal creation receives only SelectionInput. No heldout failure can cause
    a second proposal or change its version/support identity.
    """
    selection = scenario.selection
    selected = _select(selection)
    common = dict(schema_version=SCHEMA_VERSION, algorithm_version=ALGORITHM_VERSION,
                  scenario_name=scenario.name, corpus_digest=selection.baseline.corpus_digest,
                  selection_digest=_digest(selection), holdout_digest=_digest(scenario.holdout),
                  baseline=selection.baseline, serving_version_id=selection.baseline.version_id,
                  feedback=selected.feedback)
    if isinstance(selected, _NoProposal):
        reason = "multiple_topics_meet_support_floor" if selected.qualifying_topics else "fewer_than_two_independent_failures_per_topic"
        return NoCandidateReport(**common, status=selected.status,
                                 qualifying_topics=selected.qualifying_topics,
                                 gate_reasons=(reason,))
    proposal = selected.proposal
    development = _evaluate(selection.corpus, selection.baseline, proposal.candidate,
                            selected.corrections + selection.development_controls)
    reasons = []
    if any(case.group == Group.CORRECTION and not case.candidate_correct
           for case in development.cases):
        reasons.append("candidate_does_not_fix_all_supporting_corrections")
    if development.lost_query_ids:
        reasons.append("candidate_loses_baseline_correct_development_control")
    if reasons:
        return DevelopmentRejectedReport(**common, status=DevelopmentStatus.REJECTED,
                                          proposal=proposal, development=development,
                                          gate_reasons=tuple(reasons))
    # The immutable proposal is complete before this first heldout evaluation.
    heldout = _evaluate(selection.corpus, selection.baseline, proposal.candidate,
                        scenario.holdout)
    recent = next(group for group in heldout.groups if group.group == Group.RECENT)
    if heldout.lost_query_ids:
        reasons.append("baseline_correct_heldout_case_became_wrong")
    if recent.candidate_correct <= recent.baseline_correct:
        reasons.append("no_strict_recent_group_gain")
    if heldout.candidate_correct <= heldout.baseline_correct:
        reasons.append("no_strict_total_gain")
    if heldout.lost_query_ids:
        status = EvaluatedStatus.REGRESSION
    elif reasons:
        status = EvaluatedStatus.NO_GAIN
    else:
        status = EvaluatedStatus.REVIEW_REQUIRED
        reasons.append("strict_recent_and_total_gain_without_lost_correct_cases")
    return EvaluatedReport(**common, status=status, proposal=proposal,
                           development=development, heldout=heldout,
                           gate_reasons=tuple(reasons))
