"""Validate, filter, score, and explain one independent recommendation decision.

Private frozen records own one call's validated state. Topics are binary item
features. Weighted topic overlap sums explicitly supplied weights for matching
features. It is a similarity rule, not confidence or predicted learner benefit.
Prerequisites are caller-asserted skills, independent of topic preferences.
The host enforces all gates and terminal policies. There is no model authority.
"""

import re
import unicodedata
from dataclasses import dataclass

from .documents import InputError, check_json_value

_DIFFICULTIES = ("beginner", "intermediate", "advanced")
_IDENTIFIER = re.compile(r"[a-z][a-z0-9-]{0,63}\Z", re.ASCII)
_REQUEST_FIELDS = {
    "topic_weights", "max_duration_minutes", "max_difficulty", "completed_skills",
    "excluded_exercise_ids", "limit",
}
_EXERCISE_FIELDS = {"id", "title", "topics", "duration_minutes", "difficulty", "required_skills"}


@dataclass(frozen=True)
class _Exercise:
    identifier: str
    title: str
    topics: frozenset[str]
    duration: int
    difficulty: int
    required_skills: frozenset[str]


@dataclass(frozen=True)
class _Catalogue:
    version: str
    topics: frozenset[str]
    skills: frozenset[str]
    exercises: tuple[_Exercise, ...]


@dataclass(frozen=True)
class _Request:
    weights: tuple[tuple[str, int], ...]
    max_duration: int
    max_difficulty: int
    completed: frozenset[str]
    excluded: frozenset[str]
    limit: int


@dataclass(frozen=True)
class _Candidate:
    """An eligible item and its exact, alphabetically ordered score evidence."""

    exercise: _Exercise
    contributions: tuple[tuple[str, int], ...]
    score: int


def _object(value: object, fields: set[str]) -> dict:
    if type(value) is not dict or set(value) != fields:
        raise InputError()
    return value


def _integer(value: object, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise InputError()
    return value


def _identifier(value: object) -> str:
    if type(value) is not str or not _IDENTIFIER.fullmatch(value):
        raise InputError()
    return value


def _identifiers(value: object, maximum: int, minimum: int = 0) -> frozenset[str]:
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise InputError()
    identifiers = [_identifier(item) for item in value]
    if len(set(identifiers)) != len(identifiers):
        raise InputError()
    return frozenset(identifiers)


def _text(value: object, maximum: int) -> str:
    if (type(value) is not str or not 1 <= len(value) <= maximum or not value.strip()
            or any(unicodedata.category(char) == "Cc" for char in value)):
        raise InputError()
    return value


def _difficulty(value: object) -> int:
    if type(value) is not str or value not in _DIFFICULTIES:
        raise InputError()
    return _DIFFICULTIES.index(value)


def _catalogue(value: object) -> _Catalogue:
    record = _object(value, {"version", "topics", "skills", "exercises"})
    version = _text(record["version"], 64)
    topics = _identifiers(record["topics"], 100)
    skills = _identifiers(record["skills"], 100)
    raw_exercises = record["exercises"]
    if type(raw_exercises) is not list or len(raw_exercises) > 200:
        raise InputError()
    exercises = []
    seen = set()
    for raw in raw_exercises:
        item = _object(raw, _EXERCISE_FIELDS)
        identifier = _identifier(item["id"])
        tags = _identifiers(item["topics"], 10, 1)
        required = _identifiers(item["required_skills"], 20)
        if identifier in seen or not tags <= topics or not required <= skills:
            raise InputError()
        seen.add(identifier)
        exercises.append(_Exercise(
            identifier, _text(item["title"], 120), tags,
            _integer(item["duration_minutes"], 1, 480),
            _difficulty(item["difficulty"]), required,
        ))
    return _Catalogue(version, topics, skills, tuple(exercises))


def _request(value: object, catalogue: _Catalogue) -> _Request:
    record = _object(value, _REQUEST_FIELDS)
    weights = record["topic_weights"]
    if type(weights) is not dict or len(weights) > len(catalogue.topics):
        raise InputError()
    normalized_weights = []
    for topic, weight in weights.items():
        if _identifier(topic) not in catalogue.topics:
            raise InputError()
        normalized_weights.append((topic, _integer(weight, 1, 100)))
    completed = _identifiers(record["completed_skills"], len(catalogue.skills))
    excluded = _identifiers(record["excluded_exercise_ids"], len(catalogue.exercises))
    known_ids = {item.identifier for item in catalogue.exercises}
    if not completed <= catalogue.skills or not excluded <= known_ids:
        raise InputError()
    return _Request(
        tuple(sorted(normalized_weights)), _integer(record["max_duration_minutes"], 1, 480),
        _difficulty(record["max_difficulty"]), completed, excluded,
        _integer(record["limit"], 1, 20),
    )


def recommend(request: object, catalogue: object) -> dict:
    """Return a deterministic JSON report or raise sanitized InputError.

    Both arguments are validated before ranking. No caller objects are mutated
    or retained. Hard constraints precede scoring and are never relaxed. One
    scan over at most 200 items collects all rejection reasons. Bounded sorts
    make the entire report invariant under catalogue and collection order.
    """
    check_json_value(catalogue)
    check_json_value(request)
    items = _catalogue(catalogue)
    selection = _request(request, items)
    candidates = []
    rejected = []
    for item in items.exercises:
        missing = sorted(item.required_skills - selection.completed)
        reasons = []
        if item.identifier in selection.excluded:
            reasons.append("excluded")
        if item.duration > selection.max_duration:
            reasons.append("duration")
        if item.difficulty > selection.max_difficulty:
            reasons.append("difficulty")
        if missing:
            reasons.append("missing_skills")
        if reasons:
            rejected.append({"id": item.identifier, "reasons": reasons, "missing_skills": missing})
            continue
        contributions = tuple((topic, weight) for topic, weight in selection.weights if topic in item.topics)
        candidates.append(_Candidate(item, contributions, sum(weight for _, weight in contributions)))

    matching = [candidate for candidate in candidates if candidate.score > 0]
    # Cold start means no stated interests. The baseline never implies inferred
    # preferences. A stated preference with no overlap must not fall back to it.
    if not candidates:
        status, reason, population = "empty", "no_eligible_exercises", []
    elif not selection.weights:
        status, reason, population = "cold_start", "non_personalized_baseline", candidates
    elif not matching:
        status, reason, population = "no_match", "no_positive_topic_overlap", []
    else:
        status, reason, population = "personalized", "positive_topic_overlap", matching
    ordered = sorted(population, key=lambda candidate: (
        -candidate.score, candidate.exercise.duration, candidate.exercise.identifier,
    ))[:selection.limit]
    recommendations = [{
        "id": candidate.exercise.identifier,
        "title": candidate.exercise.title,
        "duration_minutes": candidate.exercise.duration,
        "difficulty": _DIFFICULTIES[candidate.exercise.difficulty],
        "score": candidate.score,
        "matched_topics": [{"topic": topic, "weight": weight} for topic, weight in candidate.contributions],
    } for candidate in ordered]
    return {
        "policy_version": "1",
        "catalogue_version": items.version,
        "provenance": "independent_project_extension",
        "status": status,
        "reason": reason,
        "request": {
            "topic_weights": dict(selection.weights),
            "max_duration_minutes": selection.max_duration,
            "max_difficulty": _DIFFICULTIES[selection.max_difficulty],
            "completed_skills": sorted(selection.completed),
            "excluded_exercise_ids": sorted(selection.excluded),
            "limit": selection.limit,
        },
        "counts": {
            "catalogue": len(items.exercises), "eligible": len(candidates),
            "matching": len(matching), "returned": len(recommendations), "rejected": len(rejected),
        },
        "recommendations": recommendations,
        "rejected": sorted(rejected, key=lambda item: item["id"]),
        "unmatched_eligible_ids": sorted(candidate.exercise.identifier for candidate in candidates if candidate.score == 0),
        "score_meaning": "sum_of_matching_topic_weights_not_confidence",
        "ordering_policy": ["score_desc", "duration_minutes_asc", "id_asc"],
    }
