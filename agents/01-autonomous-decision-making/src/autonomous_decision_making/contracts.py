"""Validated boundaries for one support-triage decision.

Contracts establish shape and vocabulary; policy establishes permission. A valid
proposal is therefore not authorization to perform its requested action.
"""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator

# Finite vocabularies keep tool scope and report labels independent of model text.
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


# Reject extra/coerced fields, freeze field assignment, and revalidate model inputs
# at boundaries. JSON datetime parsing is handled by Pydantic's JSON validators.
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")


# Metadata represents trusted upstream intake; only message is untrusted prose.
# scenario_time anchors the synthetic snapshot, not the machine's current clock.
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


# Shape validation alone does not establish relevance or freshness; policy checks
# those against the ticket before this observation enters the accepted run state.
class StatusEvidence(StrictModel):
    service: Service
    status: Literal["operational", "degraded", "outage", "unknown"]
    observed_at: AwareDatetime
    evidence_id: EvidenceID


# Advisory cognition output. Confidence is an uncalibrated routing input.
# Restricted actions remain representable so the host can demonstrate denial;
# the schema deliberately cannot enforce the full route/action policy by itself.
class Proposal(StrictModel):
    route: Route
    confidence: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    action: Literal["status_reply", "ask_clarification", "handoff", "refund", "account_change"]
    reason_code: Literal["incident_detected", "context_missing", "uncertain", "human_preferred", "restricted_effect"]


# Fixed labels explain control flow without retaining ticket/provider/error text.
class TraceEntry(StrictModel):
    stage: Literal["intake", "policy", "tool", "cognition", "action", "terminal"]
    event: Literal["validated", "blocked", "started", "succeeded", "failed", "selected", "prepared", "stopped"]
    reason: Reason | None = None


# A local record only: ready/queued describes human availability, not delivery.
class Handoff(StrictModel):
    ticket_id: TicketID
    reason: Reason
    evidence_ref: EvidenceID | None
    state: Literal["ready", "queued"]


# A handoff route can accompany either a successful policy decision or a failed
# dependency. status and the controller's exit code preserve that distinction.
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
