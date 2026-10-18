import asyncio
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from .backends import ProposalFailure
from .contracts import Handoff, Mode, Proposal, Reason, Route, RunReport, StatusEvidence, Ticket, TraceEntry
from .policy import arbitrate, evidence_error, hard_gate, priority_for, render_response

PROPOSAL_TIMEOUT_SECONDS = 20.0


class StatusTool(Protocol):
    def get_service_status(self, service: str) -> object: ...


class Cognition(Protocol):
    async def propose(self, ticket: Ticket, evidence: StatusEvidence) -> object: ...


@dataclass(frozen=True)
class Outcome:
    report: RunReport
    exit_code: int


def stopped_outcome(reason: Reason, mode: Mode = "replay", *, cancelled: bool = False) -> Outcome:
    return Outcome(
        RunReport(
            ticket_id=None, mode=mode, route=None, status="cancelled" if cancelled else "failed",
            priority=None, policy_reason=reason, proposal=None, evidence=None, response=None,
            handoff=None, trace=(TraceEntry(stage="terminal", event="stopped", reason=reason),),
            lookup_attempts=0, cognition_attempts=0,
        ),
        130 if cancelled else 2,
    )


async def run_decision(raw_ticket: object, tool: StatusTool, cognition: Cognition, *, mode: Mode = "replay") -> Outcome:
    try:
        ticket = Ticket.model_validate(raw_ticket)
        if mode not in {"replay", "live"}:
            return stopped_outcome("invalid_configuration")
    except (ValidationError, ValueError, TypeError):
        return stopped_outcome("invalid_input", mode if mode in {"replay", "live"} else "replay")

    trace = [TraceEntry(stage="intake", event="validated")]
    evidence = None
    proposal = None
    lookup_attempts = 0
    cognition_attempts = 0

    def finish(route: Route, reason: Reason, *, failed: bool = False) -> Outcome:
        trace.append(TraceEntry(stage="policy", event="selected", reason=reason))
        handoff = None
        if route == "handoff":
            handoff = Handoff(
                ticket_id=ticket.ticket_id, reason=reason,
                evidence_ref=evidence.evidence_id if evidence else None,
                state="ready" if ticket.human_available else "queued",
            )
        response = render_response(route, evidence) if evidence else None
        trace.append(TraceEntry(stage="action", event="prepared", reason=reason))
        trace.append(TraceEntry(stage="terminal", event="stopped", reason=reason))
        return Outcome(
            RunReport(
                ticket_id=ticket.ticket_id, mode=mode, route=route,
                status="failed" if failed else "handoff" if route == "handoff" else "completed",
                priority=priority_for(ticket), policy_reason=reason, proposal=proposal, evidence=evidence,
                response=response, handoff=handoff, trace=tuple(trace),
                lookup_attempts=lookup_attempts, cognition_attempts=cognition_attempts,
            ),
            2 if failed else 0,
        )

    gate = hard_gate(ticket)
    if gate:
        trace.append(TraceEntry(stage="policy", event="blocked", reason=gate))
        return finish("handoff", gate)

    try:
        lookup_attempts += 1
        trace.append(TraceEntry(stage="tool", event="started"))
        try:
            raw_evidence = tool.get_service_status(ticket.service)
        except Exception:
            trace.append(TraceEntry(stage="tool", event="failed", reason="tool_failure"))
            return finish("handoff", "tool_failure", failed=True)
        try:
            candidate_evidence = (
                StatusEvidence.model_validate_json(raw_evidence)
                if isinstance(raw_evidence, (str, bytes))
                else StatusEvidence.model_validate(raw_evidence)
            )
        except (ValidationError, ValueError, TypeError):
            trace.append(TraceEntry(stage="tool", event="failed", reason="invalid_evidence"))
            return finish("handoff", "invalid_evidence", failed=True)
        reason = evidence_error(ticket, candidate_evidence)
        if reason:
            trace.append(TraceEntry(stage="tool", event="failed", reason=reason))
            return finish("handoff", reason, failed=True)
        evidence = candidate_evidence
        trace.append(TraceEntry(stage="tool", event="succeeded"))

        cognition_attempts += 1
        trace.append(TraceEntry(stage="cognition", event="started"))
        try:
            async with asyncio.timeout(PROPOSAL_TIMEOUT_SECONDS):
                raw_proposal = await cognition.propose(ticket, evidence)
        except TimeoutError:
            trace.append(TraceEntry(stage="cognition", event="failed", reason="provider_timeout"))
            return finish("handoff", "provider_timeout", failed=True)
        except ProposalFailure as failure:
            trace.append(TraceEntry(stage="cognition", event="failed", reason=failure.reason))
            return finish("handoff", failure.reason, failed=True)
        except Exception:
            trace.append(TraceEntry(stage="cognition", event="failed", reason="provider_failure"))
            return finish("handoff", "provider_failure", failed=True)
        try:
            proposal = (
                Proposal.model_validate_json(raw_proposal)
                if isinstance(raw_proposal, (str, bytes))
                else Proposal.model_validate(raw_proposal)
            )
        except (ValidationError, ValueError, TypeError):
            trace.append(TraceEntry(stage="cognition", event="failed", reason="invalid_proposal"))
            return finish("handoff", "invalid_proposal", failed=True)
        trace.append(TraceEntry(stage="cognition", event="succeeded"))
        route, reason, failed = arbitrate(proposal, evidence)
        return finish(route, reason, failed=failed)
    except asyncio.CancelledError:
        trace.append(TraceEntry(stage="terminal", event="stopped", reason="cancelled"))
        return Outcome(
            RunReport(
                ticket_id=ticket.ticket_id, mode=mode, route=None, status="cancelled", priority=priority_for(ticket),
                policy_reason="cancelled", proposal=None, evidence=evidence, response=None, handoff=None,
                trace=tuple(trace), lookup_attempts=lookup_attempts, cognition_attempts=cognition_attempts,
            ),
            130,
        )
