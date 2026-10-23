"""The complete language authority is a finite full-match grammar.

Parsing proposes a count or relation intent. It cannot relax scene validation,
request tools, or smuggle instructions through a partially matched question.
"""

import re
import unicodedata
from typing import cast

from .domain import Color, CountIntent, InputFailure, Intent, Relation, RelationIntent

MAX_QUESTION_CHARS = 256
_COLOR = r"(red|green|blue)"
_COUNT = re.compile(rf"how many (?:{_COLOR} )?objects are visible")
_RELATION = re.compile(rf"is the {_COLOR} object (left of|right of|above|below) the {_COLOR} object")


def parse_question(question: str) -> Intent | None:
    """Reject structural input failures before normalizing benign whitespace."""

    if not isinstance(question, str):
        raise InputFailure("invalid_question_type")
    if len(question) > MAX_QUESTION_CHARS:
        raise InputFailure("question_too_long")
    # Control and format characters are not whitespace aliases or instructions.
    if any(unicodedata.category(char).startswith("C") for char in question):
        raise InputFailure("question_control_character")
    normalized = " ".join(question.lower().split())
    if normalized.endswith("?"):
        normalized = normalized[:-1].rstrip()
    if match := _COUNT.fullmatch(normalized):
        return CountIntent(cast(Color | None, match.group(1)))
    if match := _RELATION.fullmatch(normalized):
        return RelationIntent(
            cast(Color, match.group(1)),
            cast(Relation, match.group(2)),
            cast(Color, match.group(3)),
        )
    return None
