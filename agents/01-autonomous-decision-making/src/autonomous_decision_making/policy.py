"""Deterministic host authority and response templates, independent of cognition.

The controller applies these checks in order: hard gate, evidence validation,
proposal arbitration, then rendering. Provider suggestions cannot skip a stage.
"""

from .contracts import Priority, Proposal, Reason, Route, StatusEvidence, Ticket


def priority_for(ticket: Ticket) -> Priority:
    """Assign operational priority without granting additional action authority."""
    if ticket.urgency == "urgent" or ticket.impact == "high" or ticket.request_kind == "security":
        return "high"
    return "elevated" if ticket.customer_tier == "premium" else "normal"


def hard_gate(ticket: Ticket) -> Reason | None:
    """Return the first mandatory handoff reason before tools or cognition run."""
    if ticket.human_requested:
        return "human_requested"
    if ticket.impact == "high":
        return "high_impact"
    if ticket.request_kind in {"refund", "account_change", "security"}:
        return "restricted_request"
    if ticket.request_kind == "unknown":
        return "unknown_request"
    return None


def evidence_error(ticket: Ticket, evidence: StatusEvidence) -> Reason | None:
    """Require a matching, known snapshot within the inclusive 300-second window."""
    if evidence.service != ticket.service:
        return "service_mismatch"
    age = (ticket.scenario_time - evidence.observed_at).total_seconds()
    if age < 0:
        return "future_evidence"
    if age > 300:
        return "stale_evidence"
    if evidence.status == "unknown":
        return "unknown_status"
    return None


def arbitrate(proposal: Proposal, evidence: StatusEvidence) -> tuple[Route, Reason, bool]:
    """Return (selected route, host reason, failure flag) for validated evidence.

    The caller must first apply hard_gate and evidence_error. Ordered early returns
    encode precedence: restrictions and consistency checks precede confidence, and
    explicit handoff/guided proposals cannot be promoted by a high confidence score.
    The flag separates malformed proposals from intentional policy handoffs.
    """
    if proposal.action in {"refund", "account_change"}:
        return "handoff", "restricted_action", False
    ordinary_pairs = {("autonomous", "status_reply"), ("guided", "ask_clarification"), ("handoff", "handoff")}
    if (proposal.route, proposal.action) not in ordinary_pairs:
        return "handoff", "invalid_proposal", True
    if proposal.route == "handoff":
        return "handoff", "candidate_handoff", False
    if proposal.confidence < 0.50:
        return "handoff", "low_confidence", False
    if proposal.route == "guided":
        return "guided", "guided_candidate", False
    if proposal.confidence < 0.80:
        return "guided", "medium_confidence", False
    if evidence.status == "operational":
        return "guided", "healthy_service", False
    # Unknown evidence was rejected upstream; only degraded/outage can reach here.
    return "autonomous", "supported_incident", False


def render_response(route: Route, evidence: StatusEvidence) -> str | None:
    """Prepare host-authored text from accepted evidence; send no message.

    No model-authored prose is rendered, and a status observation never establishes
    that an issue was resolved or that a restoration time is known.
    """
    if route == "handoff":
        return None
    observation = (
        f"The synthetic {evidence.service} snapshot shows {evidence.status} "
        f"service (evidence {evidence.evidence_id})."
    )
    if route == "guided":
        return f"{observation} Which operation failed, and what error did you see?"
    return f"{observation} A restoration time has not been confirmed."
