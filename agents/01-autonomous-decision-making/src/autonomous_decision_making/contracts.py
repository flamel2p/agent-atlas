from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator

Service = Literal["api", "dashboard"]
Route = Literal["autonomous", "guided", "handoff"]
Mode = Literal["replay", "live"]
Priority = Literal["normal", "elevated", "high"]
TicketID = Annotated[str, StringConstraints(pattern=r"^TKT-[A-Z0-9-]{1,32}$", max_length=36)]
EvidenceID = Annotated[str, StringConstraints(pattern=r"^SYN-[A-Z0-9-]{1,40}$", max_length=44)]
Reason = Literal[
    "human_requested", "high_impact", "restricted_request", "unknown_request",
    "restricted_action", "candidate_handoff", "low_confidence", "guided_candidate",
    "medium_confidence", "healthy_service", "supported_incident", "invalid_input",
    "invalid_configuration", "tool_failure", "invalid_evidence", "unknown_status",
    "stale_evidence", "future_evidence", "service_mismatch", "invalid_proposal",
    "provider_refusal", "provider_incomplete", "provider_invalid_output",
    "provider_timeout", "provider_failure", "cancelled",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")


class Ticket(StrictModel):
    ticket_id: TicketID
    message: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    service: Service
    request_kind: Literal["status", "troubleshooting", "refund", "account_change", "security", "unknown"]
    impact: Literal["low", "high"]
    customer_tier: Literal["standard", "premium"]
    urgency: Literal["normal", "urgent"]
    human_requested: bool
    human_available: bool
    scenario_time: AwareDatetime

    @field_validator("message")
    @classmethod
    def nonblank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank_message")
        return value


class StatusEvidence(StrictModel):
    service: Service
    status: Literal["operational", "degraded", "outage", "unknown"]
    observed_at: AwareDatetime
    evidence_id: EvidenceID


class Proposal(StrictModel):
    route: Route
    confidence: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    action: Literal["status_reply", "ask_clarification", "handoff", "refund", "account_change"]
    reason_code: Literal["incident_detected", "context_missing", "uncertain", "human_preferred", "restricted_effect"]


class TraceEntry(StrictModel):
    stage: Literal["intake", "policy", "tool", "cognition", "action", "terminal"]
    event: Literal["validated", "blocked", "started", "succeeded", "failed", "selected", "prepared", "stopped"]
    reason: Reason | None = None


class Handoff(StrictModel):
    ticket_id: TicketID
    reason: Reason
    evidence_ref: EvidenceID | None
    state: Literal["ready", "queued"]


class RunReport(StrictModel):
    ticket_id: TicketID | None
    mode: Mode
    route: Route | None
    status: Literal["completed", "handoff", "failed", "cancelled"]
    priority: Priority | None
    policy_reason: Reason
    proposal: Proposal | None
    evidence: StatusEvidence | None
    response: str | None
    handoff: Handoff | None
    trace: tuple[TraceEntry, ...]
    lookup_attempts: int
    cognition_attempts: int
