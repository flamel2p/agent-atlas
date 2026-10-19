"""Read-only semantic memory: retrieve and render the packaged course FAQ.

Here, semantic memory means curated factual knowledge, not embedding search.
Neither user history nor generated answers can extend this corpus at runtime.
"""

from functools import lru_cache
from importlib.resources import files
import json
import re

from .contracts import Failure, STYLES


STOP_WORDS = frozenset("a an and are as at be by can do for from how i in is it me my of on or that the this to was what when with you your".split())


def tokens(text: str) -> frozenset[str]:
    """Use distinct lowercase ASCII tokens; repeated words do not boost overlap."""
    return frozenset(re.findall(r"[a-z0-9]+", text.lower())) - STOP_WORDS


@lru_cache(maxsize=1)
def faq() -> tuple[dict, ...]:
    """Load and validate the bounded packaged corpus once per process."""
    try:
        document = json.loads(files("memory_agent").joinpath("data/faq.json").read_text())
        entries = document["entries"]
        if document["version"] != 1 or not isinstance(entries, list) or not 1 <= len(entries) <= 30:
            raise ValueError
        seen = set()
        for entry in entries:
            if set(entry) != {"id", "title", "keywords", "answers"}:
                raise ValueError
            if not re.fullmatch(r"faq-[a-z-]{1,40}", entry["id"]) or entry["id"] in seen:
                raise ValueError
            seen.add(entry["id"])
            if not isinstance(entry["title"], str) or not 1 <= len(entry["title"]) <= 100:
                raise ValueError
            if not isinstance(entry["keywords"], list) or not 1 <= len(entry["keywords"]) <= 30:
                raise ValueError
            if any(not isinstance(word, str) or not 1 <= len(word) <= 40 for word in entry["keywords"]):
                raise ValueError
            if set(entry["answers"]) != set(STYLES):
                raise ValueError
            if any(not isinstance(answer, str) or not 1 <= len(answer) <= 1200 for answer in entry["answers"].values()):
                raise ValueError
        return tuple(entries)
    except (OSError, KeyError, TypeError, ValueError):
        raise Failure("knowledge_invalid") from None


def candidates(query: str) -> list[dict]:
    """Return at most three positive-overlap FAQ entries, breaking ties by ID."""
    query_tokens = tokens(query)
    ranked = []
    for entry in faq():
        # Search metadata only; answer wording and stored episodes do not set ranking.
        overlap = len(query_tokens & tokens(entry["title"] + " " + " ".join(entry["keywords"])))
        if overlap:
            ranked.append((overlap, entry))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [entry for _, entry in ranked[:3]]


def validate_selection(selection: object, choices: list[dict]) -> list[str]:
    """Require distinct retrieved IDs; an empty list is a valid abstention.

    This host-side authority check is separate from the provider's JSON schema:
    well-formed output still cannot cite knowledge outside this turn's candidates.
    """
    if not isinstance(selection, list) or len(selection) > 3:
        raise Failure("provider_selection")
    if any(not isinstance(item, str) for item in selection) or len(set(selection)) != len(selection):
        raise Failure("provider_selection")
    allowed = {entry["id"] for entry in choices}
    if any(item not in allowed for item in selection):
        raise Failure("provider_selection")
    return selection


def render(selection: list[str], choices: list[dict], style: str) -> tuple[str, list[dict]]:
    """Render validated evidence using curated style variants and explicit citations.

    The caller validates the selection first. Model prose is never an input to
    the final answer, and a style preference changes presentation only.
    """
    selected = {entry["id"]: entry for entry in choices}
    evidence = [{"id": key, "title": selected[key]["title"], "version": 1} for key in selection]
    if not selection:
        return "The packaged course FAQ does not support an answer to this question.", []
    answer = "\n\n".join(f"{selected[key]['answers'][style]} [{key}]" for key in selection)
    return answer, evidence
