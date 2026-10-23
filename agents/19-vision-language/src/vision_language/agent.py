"""Apply host-owned exact-answer gates to one image and one bounded question.

The language parser only selects an intent. Perception issues always veto an
exact answer. Singular relations require unique, distinguishable color selectors.
There is no inference loop, retry, model proposal, or effect beyond the image read.
"""

from pathlib import Path

from .domain import Answered, CountIntent, InputFailure, Invalid, RelationIntent, Result, Scene, Uncertain, Unsupported
from .perception import inspect_image
from .questions import parse_question


def _resolve(scene: Scene, intent: CountIntent | RelationIntent):
    if scene.issues:
        return Uncertain("scene_uncertain")
    if isinstance(intent, CountIntent):
        count = sum(intent.color is None or item.color == intent.color for item in scene.observations)
        return Answered(count, "exact_count")
    subjects = [item for item in scene.observations if item.color == intent.subject_color]
    references = [item for item in scene.observations if item.color == intent.reference_color]
    if intent.subject_color == intent.reference_color or len(subjects) != 1 or len(references) != 1:
        return Uncertain("selector_ambiguous")
    subject, reference = subjects[0].bbox, references[0].bbox
    predicates = {
        "left of": subject[2] <= reference[0],
        "right of": reference[2] <= subject[0],
        "above": subject[3] <= reference[1],
        "below": reference[3] <= subject[1],
    }
    return Answered(predicates[intent.relation], "exact_relation")


def answer_image(path: str | Path, question: str) -> Result:
    """Return a terminal tagged result without persisting any request state."""

    intent = None
    try:
        intent = parse_question(question)
        scene = inspect_image(path)
    except InputFailure as error:
        return Result(Invalid(error.reason), question, intent, error.image)
    if intent is None:
        outcome = Unsupported()
        rules = ("rule:finite_question_grammar",)
    else:
        outcome = _resolve(scene, intent)
        rules = ("rule:complete_rectangles", "rule:global_scene_gate", "rule:count" if isinstance(intent, CountIntent) else "rule:unique_selectors", "rule:exclusive_bounds")
    return Result(
        outcome, question, intent, scene.image, scene.observations, scene.issues,
        (f"sha256:{scene.image.sha256}", *(item.id for item in scene.observations), *rules),
    )
