"""Own the bounded retrieval flow and its terminal JSON outcomes.

This agent performs at most one search and one evidence selection, without a
retry loop or persistent memory. The host filters scope and validates citations;
the optional model can only propose passage IDs from supplied candidates.
"""

from contextlib import ExitStack
from datetime import datetime, timezone

from .contracts import AgentError, Request
from .corpus import eligible, load_bundled, validate_corpus
from .provider import preflight_openai
from .retrieval import candidate_passages, render_selection, replay_select, retrieve


def empty_result() -> dict:
    """Start with no answer/evidence so early failures cannot imply partial success."""
    return {"status": "failed", "reason": "invalid_input", "backend": None,
            "question": None, "scope": None, "snapshot_digest": None,
            "answer_mode": "extractive", "answer": "", "citations": [],
            "retrieved_chunks": [], "trace": [], "counts": {"search_calls": 0, "model_calls": 0}}


def run(question, *, backend="replay", audience="public", version="2.0", as_of=None,
        corpus_loader=None, provider_factory=None, selector=None) -> tuple[dict, int]:
    """Return one result and CLI exit code, sanitizing failures and cancellation.

    Optional loaders/factories/selectors are Python test seams, not CLI powers.
    OpenAI configuration is checked before corpus access, even for evidence gaps.
    """
    result = empty_result()
    try:
        request = Request.validate(question, backend, audience, version,
                                   as_of if as_of is not None else datetime.now(timezone.utc).date().isoformat())
        result.update(backend=request.backend, question=request.question, scope=request.scope())
        result["trace"].append("input_validated")
        # Cleanup stays inside the handler: interruption during close cancels even
        # an already constructed answer and removes its quotations/citations.
        with ExitStack() as cleanup:
            provider = None
            if backend == "openai":
                provider = (provider_factory or preflight_openai)()
                cleanup.callback(close_provider, provider)
                result["trace"].append("provider_ready")
            return retrieve_and_select(request, result, provider, corpus_loader, selector)
    except KeyboardInterrupt:
        result.update(status="cancelled", reason="interrupted", answer="", citations=[])
        return result, 130
    except AgentError as error:
        result.update(status="failed", reason=error.reason, answer="", citations=[])
        return result, 2 if error.reason == "invalid_input" else 1
    except Exception:
        result.update(status="failed", reason="internal_error", answer="", citations=[])
        return result, 1


def close_provider(provider):
    """Ignore ordinary cleanup errors; let interruption reach run's cancellation path."""
    try:
        provider.close()
    except Exception:
        pass


def retrieve_and_select(request, result, provider, corpus_loader, selector):
    """Execute the single pass; abstain early when eligible evidence is unavailable."""
    trace = result["trace"]
    try:
        snapshot = validate_corpus((corpus_loader or load_bundled)())
    except AgentError:
        raise
    except Exception:
        raise AgentError("corpus_unavailable") from None
    result["snapshot_digest"] = snapshot.digest
    trace.append("corpus_validated")
    # Filter before scores, serialized chunks, or model payloads can reveal sources.
    documents = eligible(snapshot, request)
    trace.append("scope_filtered")
    if not documents:
        result.update(status="abstained", reason="no_eligible_evidence")
        return result, 0
    result["counts"]["search_calls"] = 1
    chunks = retrieve(documents, request.question)
    result["retrieved_chunks"] = [chunk.public() for chunk in chunks]
    trace.append("retrieval_complete")
    if not chunks:
        result.update(status="abstained", reason="no_lexical_matches")
        return result, 0
    candidates = candidate_passages(chunks)
    if request.backend == "openai":
        # Count the attempt before dispatch so a failed request still consumes it.
        result["counts"]["model_calls"] = 1
        selection = provider.select(request, candidates)
    else:
        selection = (selector or replay_select)(request.question, candidates)
    trace.append("selection_complete")
    answer, citations = render_selection(selection, candidates, snapshot)
    if citations:
        result.update(status="answered", reason="evidence_selected", answer=answer, citations=citations)
    else:
        result.update(status="abstained", reason="evidence_gap")
    trace.append("selection_validated")
    return result, 0
