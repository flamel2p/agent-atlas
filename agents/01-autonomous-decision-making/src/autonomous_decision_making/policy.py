from .contracts import Priority, Proposal, Reason, Route, StatusEvidence, Ticket


def priority_for(ticket: Ticket) -> Priority:
    if ticket.urgency == "urgent" or ticket.impact == "high" or ticket.request_kind == "security":
        return "high"
    return "elevated" if ticket.customer_tier == "premium" else "normal"


def hard_gate(ticket: Ticket) -> Reason | None:
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
    return "autonomous", "supported_incident", False


def render_response(route: Route, evidence: StatusEvidence) -> str | None:
    if route == "handoff":
        return None
    observation = (
        f"The synthetic {evidence.service} snapshot shows {evidence.status} "
        f"service (evidence {evidence.evidence_id})."
    )
    if route == "guided":
        return f"{observation} Which operation failed, and what error did you see?"
    return f"{observation} A restoration time has not been confirmed."
