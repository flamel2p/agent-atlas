from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from uuid import uuid4

from .contracts import Failure, Request, terminal, timestamp, validate_name
from .knowledge import candidates, render, validate_selection
from .provider import live_select
from .storage import CASE_ROOT, Store


def ask(request: Request, *, case_root: Path = CASE_ROOT, now: datetime | None = None, selector=None) -> dict:
    mode = request.mode if request.mode in ("replay", "live") else "unknown"
    trace = []
    try:
        request.validate()
        now = now if now is not None else datetime.now(UTC)
        created_at = timestamp(now)
        trace.append({"event": "request_validated"})
        with Store(request.store, case_root=case_root) as store:
            remembered, episodes = store.recall(request.user, request.query, now)
            preference = remembered or {
                "style": "concise", "source": "default", "remembered": False,
                "record_id": None, "source_session": None, "created_at": None,
            }
            if request.remember_style is not None:
                preference = {
                    "style": request.remember_style, "source": "current", "remembered": True,
                    "record_id": "pref-" + uuid4().hex, "source_session": request.session, "created_at": created_at,
                }
            trace.append({"event": "memory_recalled", "episodes": len(episodes), "style_source": preference["source"]})
            choices = candidates(request.query)
            trace.append({"event": "faq_retrieved", "candidate_ids": [entry["id"] for entry in choices]})
            if not choices:
                selected = []
                trace.append({"event": "selection_skipped", "reason": "no_candidates"})
            elif request.mode == "replay":
                selected = [choices[0]["id"]]
                trace.append({"event": "replay_selected"})
            else:
                trace.append({"event": "provider_requested", "calls": 1})
                selected = (selector or live_select)(request.query, preference["style"], episodes, choices)
            selected = validate_selection(selected, choices)
            answer, evidence = render(selected, choices, preference["style"])
            record_id = store.persist(request, preference, selected, now)
            trace.append({"event": "memory_committed", "episode_record_id": record_id})
        result = terminal("answered" if selected else "insufficient_knowledge", mode)
        result.update(evidence=evidence, preference=preference, recalled_episodes=episodes, trace=trace,
                      answer=answer, memory_committed=True)
        return result
    except KeyboardInterrupt:
        result = terminal("cancelled", mode, code="interrupted")
    except Failure as error:
        result = terminal("failed", mode, code=error.code)
    except (sqlite3.Error, OSError):
        result = terminal("failed", mode, code="storage_failure")
    except Exception:
        result = terminal("failed", mode, code="internal_failure")
    result["trace"] = trace + [{"event": result["status"]}]
    return result


def forget(user: str, name: str = "demo", *, case_root: Path = CASE_ROOT) -> dict:
    try:
        validate_name(user)
        validate_name(name)
        with Store(name, case_root=case_root) as store:
            deleted = store.forget(user)
        result = terminal("forgotten", "local")
        result.update(deleted=deleted, memory_committed=True, trace=[{"event": "user_records_deleted"}])
        return result
    except KeyboardInterrupt:
        return terminal("cancelled", "local", code="interrupted")
    except Failure as error:
        return terminal("failed", "local", code=error.code)
    except (sqlite3.Error, OSError):
        return terminal("failed", "local", code="storage_failure")


def exit_code(result: dict) -> int:
    if result["status"] == "cancelled":
        return 130
    return 0 if result["status"] in ("answered", "forgotten") else 2
