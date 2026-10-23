"""Render audience views from one trace and gate the released priority.

Renderers have no classification authority. Every claim comes from fixed
templates over validated events. Exact expected-view comparison deliberately
limits the prose so fabricated reasons and altered references are rejectable.
"""

from collections.abc import Callable
from dataclasses import asdict
import json

from .contracts import (
    AUDIENCES, Audience, Claim, ContractError, EvidenceEvent, Explanation,
    FinalEvent, Outcome, RuleEvent, Trace,
)
from .decision import load_trace, trace_to_dict

type Renderer = Callable[[Trace, Audience], Explanation]


def render(trace: Trace, audience: Audience) -> Explanation:
    """Produce one immutable view using only observations and actual events.

    Call through explain(), which validates the trace and all views together.
    The audience changes detail, never the priority or policy precedence.
    """
    if audience not in AUDIENCES:
        raise ContractError("audience_invalid")
    evidence = tuple(event for event in trace.events if isinstance(event, EvidenceEvent))
    final = trace.events[-1]
    if not isinstance(final, FinalEvent):
        raise ContractError("trace_invalid")
    if final.status == "needs_review":
        missing = tuple(event for event in evidence if event.availability == "missing")
        claims = tuple(Claim(f"Evidence for {event.name} is unavailable.", (event.event_id,)) for event in missing)
        claims += (Claim("Priority is withheld because required evidence is missing.",
                         (*final.evidence_ids, final.event_id)),)
        return Explanation(audience, "incomplete", None, claims)

    rules = tuple(event for event in trace.events if isinstance(event, RuleEvent))
    selected = next(event for event in rules if event.rule_id == final.selected_rule)
    if audience == "user":
        claims = [Claim(f"Priority is {final.decision}.", (final.event_id,))]
        for event in evidence:
            value = json.dumps(event.value)
            claims.append(Claim(f"Recorded {event.name} is {value}.", (event.event_id,)))
        claims.append(Claim(f"Rule {selected.rule_id} matched and was selected.",
                            (selected.event_id, final.event_id)))
    else:
        prefix = "Execution" if audience == "engineer" else "Audit record"
        claims = [Claim(f"{prefix} under {trace.policy_version} selected priority {final.decision}.",
                        (final.event_id,))]
        claims.extend(Claim(f"Evidence {event.name} has value {json.dumps(event.value)}.", (event.event_id,))
                      for event in evidence)
        claims.extend(Claim(f"Rule {event.rule_id} evaluated to {json.dumps(event.matched)} for priority {event.priority}.",
                            (*event.evidence_ids, event.event_id)) for event in rules)
        claims.append(Claim(f"First matching rule {selected.rule_id} selected priority {final.decision}.",
                            (selected.event_id, final.event_id)))
    return Explanation(audience, "complete", final.decision, tuple(claims))


def unavailable(code: str, trace: Trace | None = None) -> Outcome:
    """Withhold the released decision and all partial explanations on failure."""
    return Outcome("needs_review", None, "unavailable", (), trace, (code,))


def explain(trace: Trace, renderer: Renderer = render) -> Outcome:
    """Validate once, render once per audience, and release all views atomically.

    The canonical view is the executable fidelity contract. Arbitrary prose is
    outside it. A renderer exception or mismatch withholds every audience view.
    The detached validated trace remains the sole source of authority.
    """
    try:
        snapshot = trace_to_dict(trace)
        trusted = load_trace(snapshot)
        snapshot_json = json.dumps(snapshot, sort_keys=True)
    except (ContractError, TypeError, ValueError, RecursionError):
        return unavailable("trace_invalid")

    views = []
    try:
        for audience in AUDIENCES:
            expected = render(trusted, audience)
            proposed = renderer(trusted, audience)
            # Reference existence alone cannot validate an invented sentence.
            # Exact typed claims enforce both factual wording and provenance.
            if type(proposed) is not Explanation or proposed != expected:
                return unavailable("explanation_invalid", load_trace(snapshot))
            if json.dumps(trace_to_dict(trusted), sort_keys=True) != snapshot_json:
                return unavailable("trace_invalid")
            views.append(proposed)
    except Exception:
        return unavailable("renderer_failed", load_trace(snapshot))

    final = trusted.events[-1]
    if final.status == "needs_review":
        return Outcome("needs_review", None, "incomplete", tuple(views), trusted, ("evidence_missing",))
    return Outcome("completed", final.decision, "complete", tuple(views), trusted, ())


def outcome_to_dict(outcome: Outcome) -> dict:
    """Convert immutable values to an independent JSON-ready output snapshot."""
    return asdict(outcome)
