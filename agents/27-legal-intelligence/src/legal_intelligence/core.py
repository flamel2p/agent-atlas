"""Pure retrieve, draft, verify transitions for an original fictional corpus.

An issue is a requested research topic; a rule is an exact host-owned conclusion
tag. Applicability means exact issue/rule support in this snapshot, not semantic
similarity or real legal reasoning. Frozen records live for one invocation only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Any

from .boundary import InvalidInput, choice, fields, identifier, sequence

ISSUE_RULE = MappingProxyType({"notice": "notice_before_pause", "export": "export_opt_in",
                               "retention": "retention_cap"})
RULE_TEXT = MappingProxyType({
    "notice_before_pause": "In this fictional system, give a notice token before pausing a lantern lease.",
    "export_opt_in": "In this fictional system, export of lantern logs requires an opt-in token.",
    "retention_cap": "In this fictional system, lantern log retention has a fixed cap.",
})
JURISDICTIONS = ("ALDER", "BRUME")
SNAPSHOT = "alder-brume-2026-10-01"
RECORDED_AT = "2026-10-01T00:00:00Z"


@dataclass(frozen=True)
class Matter:
    """Validated requested topics, scoped to one fictional jurisdiction."""
    matter_id: str
    jurisdiction: str
    issues: tuple[str, ...]


@dataclass(frozen=True)
class FictionalAuthority:
    """A versioned source; explicit status belongs only to the fixed snapshot.

    Rank 1 precedes rank 2. Provenance identifies original fixture authorship,
    not an authenticated court or external currency guarantee.
    """
    authority_id: str
    version: str
    jurisdiction: str
    authority_rank: int
    status: str
    issue: str
    rule: str
    holding: str
    provenance: str


@dataclass(frozen=True)
class Citation:
    authority_id: str
    version: str


@dataclass(frozen=True)
class DraftClaim:
    """Untrusted proposal with tags and citation pairs, never arbitrary prose."""
    issue: str
    rule: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class CitationFinding:
    """Host verdict for one citation, or one empty claim's missing evidence."""
    claim_index: int
    authority_id: str | None
    requested_version: str | None
    source: FictionalAuthority | None
    passed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class MemoResult:
    """Returned simulation record. It never records actual human approval."""
    outcome: str
    transitions: tuple[str, ...]
    matter: Matter
    corpus_snapshot: str
    corpus_recorded_at: str
    retrieval: dict[str, tuple[FictionalAuthority, ...]]
    memo: tuple[dict[str, Any], ...]
    citation_findings: tuple[CitationFinding, ...]
    uncovered_issues: tuple[str, ...]
    blockers: tuple[str, ...]
    simulated_release: bool
    review_required: bool = True
    human_approval: str = "not_granted"
    reviewer: str = "fictional-review-desk"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_request(value: Any) -> tuple[Matter, tuple[DraftClaim, ...] | None]:
    root = fields(value, {"matter"}, {"draft"})
    data = fields(root["matter"], {"matter_id", "jurisdiction", "issues"})
    issues = tuple(choice(x, ISSUE_RULE) for x in sequence(data["issues"], 1, 3))
    if len(set(issues)) != len(issues):
        raise InvalidInput("duplicate_issue")
    matter = Matter(identifier(data["matter_id"]), choice(data["jurisdiction"], JURISDICTIONS), issues)
    if "draft" not in root:
        return matter, None
    claims = []
    for item in sequence(root["draft"], 0, 6):
        claim = fields(item, {"issue", "rule", "citations"})
        citations = []
        for item in sequence(claim["citations"], 0, 4):
            citation = fields(item, {"authority_id", "version"})
            citations.append(Citation(identifier(citation["authority_id"]), identifier(citation["version"])))
        if len(set(citations)) != len(citations):
            raise InvalidInput("duplicate_citation")
        claims.append(DraftClaim(choice(claim["issue"], ISSUE_RULE), choice(claim["rule"], RULE_TEXT),
                                 tuple(citations)))
    if len({c.issue for c in claims}) != len(claims):
        raise InvalidInput("duplicate_claim_issue")
    return matter, tuple(claims)


def parse_corpus(value: Any) -> tuple[FictionalAuthority, ...]:
    """Validate trusted fixture metadata; missing/unknown status never upgrades."""
    root = fields(value, {"snapshot", "recorded_at", "authorities"})
    if root["snapshot"] != SNAPSHOT or root["recorded_at"] != RECORDED_AT:
        raise InvalidInput("corpus_snapshot")
    authorities = []
    required = set(FictionalAuthority.__dataclass_fields__)
    for item in sequence(root["authorities"], 1, 16):
        source = fields(item, required)
        source_id = identifier(source["authority_id"])
        rank = source["authority_rank"]
        if type(rank) is not int or rank not in (1, 2):
            raise InvalidInput("authority_rank")
        rule = choice(source["rule"], RULE_TEXT)
        if source["holding"] != RULE_TEXT[rule] or source["provenance"] != f"original-fiction:{source_id}":
            raise InvalidInput("corpus_provenance_or_holding")
        authorities.append(FictionalAuthority(source_id, identifier(source["version"]),
            choice(source["jurisdiction"], JURISDICTIONS), rank,
            choice(source["status"], ("current", "superseded", "unknown")),
            choice(source["issue"], ISSUE_RULE), rule, source["holding"], source["provenance"]))
    if len({x.authority_id for x in authorities}) != len(authorities):
        raise InvalidInput("duplicate_authority")
    return tuple(authorities)


def retrieve(matter: Matter, corpus: tuple[FictionalAuthority, ...]) -> dict[str, tuple[FictionalAuthority, ...]]:
    """Filter applicability before rank; prestige cannot repair wrong support."""
    return {issue: tuple(sorted((a for a in corpus if a.issue == issue
        and a.rule == ISSUE_RULE[issue] and a.jurisdiction == matter.jurisdiction and a.status == "current"),
        key=lambda a: (a.authority_rank, a.authority_id))) for issue in matter.issues}


def run(matter: Matter, corpus: tuple[FictionalAuthority, ...],
        draft: tuple[DraftClaim, ...] | None = None) -> MemoResult:
    """Execute one finite pass. Only passing evidence can reach simulated release.

    Public callers construct records through parse_request/parse_corpus; there
    are no tool adapters inside this core and no retries or external effects.
    """
    retrieval = retrieve(matter, corpus)
    if draft is None:
        draft = tuple(DraftClaim(issue, ISSUE_RULE[issue], (Citation(sources[0].authority_id,
            sources[0].version),)) for issue, sources in retrieval.items() if sources)
    sources = {a.authority_id: a for a in corpus}
    findings = []
    covered: set[str] = set()
    blockers = [] if draft else ["empty_draft"]
    for index, claim in enumerate(draft):
        claim_reasons = []
        if claim.issue not in matter.issues:
            claim_reasons.append("issue_not_requested")
        if claim.rule != ISSUE_RULE[claim.issue]:
            claim_reasons.append("rule_not_applicable")
        claim_passed = bool(claim.citations)
        if not claim.citations:
            findings.append(CitationFinding(index, None, None, None, False,
                                            tuple(claim_reasons + ["empty_citations"])))
        for citation in claim.citations:
            reasons = claim_reasons.copy()
            source = sources.get(citation.authority_id)
            if source is None:
                reasons.append("unknown_authority")
            else:
                if citation.version != source.version:
                    reasons.append("version_mismatch")
                if source.jurisdiction != matter.jurisdiction:
                    reasons.append("wrong_jurisdiction")
                if source.status != "current":
                    reasons.append("status_" + source.status)
                if source.issue != claim.issue or source.rule != claim.rule:
                    reasons.append("source_not_applicable")
            passed = not reasons
            claim_passed = claim_passed and passed
            findings.append(CitationFinding(index, citation.authority_id, citation.version, source,
                                            passed, tuple(reasons)))
        if claim_passed:
            covered.add(claim.issue)
        else:
            blockers.append(f"claim_{index}_failed")
    uncovered = tuple(issue for issue in matter.issues if issue not in covered)
    if uncovered:
        blockers.append("uncovered_issues")
    released = not blockers
    outcome = "simulated_reviewer_handoff" if released else "blocked_review"
    memo = tuple({"issue": c.issue, "rule": c.rule, "text": RULE_TEXT[c.rule],
                  "citations": tuple(asdict(x) for x in c.citations)} for c in draft)
    return MemoResult(outcome, ("validated", "retrieved", "drafted", "verified", outcome),
        matter, SNAPSHOT, RECORDED_AT, retrieval, memo, tuple(findings), uncovered,
        tuple(blockers), released)
