"""Immutable request state shared across perception, question parsing, and answers.

An observation is one complete rectangle measured from pixels. Its bounding box
uses zero-based coordinates and exclusive right/bottom edges. Provenance hashes
the original image bytes, so it identifies the read input, not inferred truth.
Outcomes carry either an exact integer/boolean or a tagged null-answer state.
No state survives a request and no field authorizes any external effect.
"""

from dataclasses import asdict, dataclass
from typing import Literal

type Color = Literal["red", "green", "blue"]
type Relation = Literal["left of", "right of", "above", "below"]
type Bounds = tuple[int, int, int, int]

SCOPE = "Visible complete rectangles in the supported diagram grammar; no claim about completely hidden objects."


@dataclass(frozen=True)
class ImageProvenance:
    """Byte identity remains available when later decoding rejects the image."""

    sha256: str
    byte_count: int
    width: int | None = None
    height: int | None = None
    format: str | None = None
    mode: str | None = None


@dataclass(frozen=True)
class Observation:
    id: str
    color: Color
    bbox: Bounds
    pixel_count: int


@dataclass(frozen=True)
class Scene:
    """Issues block every exact answer, including counts of unaffected colors."""

    image: ImageProvenance
    observations: tuple[Observation, ...]
    issues: tuple[str, ...]


@dataclass(frozen=True)
class CountIntent:
    color: Color | None = None
    kind: Literal["count"] = "count"


@dataclass(frozen=True)
class RelationIntent:
    subject_color: Color
    relation: Relation
    reference_color: Color
    kind: Literal["relation"] = "relation"


type Intent = CountIntent | RelationIntent


@dataclass(frozen=True)
class Answered:
    answer: int | bool
    reason: Literal["exact_count", "exact_relation"]
    status: Literal["answered"] = "answered"


@dataclass(frozen=True)
class Uncertain:
    reason: Literal["scene_uncertain", "selector_ambiguous"]
    status: Literal["uncertain"] = "uncertain"
    answer: None = None


@dataclass(frozen=True)
class Unsupported:
    reason: Literal["unsupported_question"] = "unsupported_question"
    status: Literal["unsupported"] = "unsupported"
    answer: None = None


@dataclass(frozen=True)
class Invalid:
    reason: str
    status: Literal["invalid"] = "invalid"
    answer: None = None


type Outcome = Answered | Uncertain | Unsupported | Invalid


@dataclass(frozen=True)
class Result:
    """The envelope preserves measured evidence even when the host abstains."""

    outcome: Outcome
    question: str
    intent: Intent | None = None
    image: ImageProvenance | None = None
    observations: tuple[Observation, ...] = ()
    scene_issues: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            **asdict(self.outcome),
            "question": self.question,
            "intent": asdict(self.intent) if self.intent is not None else None,
            "image": asdict(self.image) if self.image is not None else None,
            "observations": [asdict(item) for item in self.observations],
            "scene_issues": list(self.scene_issues),
            "evidence_refs": list(self.evidence_refs),
            "scope": SCOPE,
        }


class InputFailure(Exception):
    """A machine-readable boundary failure, never a raw path or file content."""

    def __init__(self, reason: str, image: ImageProvenance | None = None):
        super().__init__(reason)
        self.reason = reason
        self.image = image
