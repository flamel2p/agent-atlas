"""Request validation and the shared lexical vocabulary for retrieval and replay.

Normalization affects matching only; citations retain the original source text.
"""

from dataclasses import dataclass
from datetime import date
import json
import re
import unicodedata


class AgentError(Exception):
    """Carry a stable, caller-visible reason without raw input/provider details."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


# These small, explicit tables are part of SPEC.md, not general English stemming.
STOPWORDS = frozenset(
    "a an and are as at be by can could do does for from how i in is it me my of on "
    "or our please the their them there these they this to us was we what when where "
    "which who will with would you your".split()
)
ALIASES = {
    "cancellation": "cancel", "cancellations": "cancel", "cancelled": "cancel",
    "canceled": "cancel", "cancelling": "cancel", "canceling": "cancel",
    "subscriptions": "subscription", "payments": "payment", "refunds": "refund",
}
WORD = re.compile(r"[^\W_]+", re.UNICODE)
VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}\Z")


def raw_tokens(text: str) -> list[str]:
    """Normalize Unicode/case and split alphanumeric words, including at underscores."""
    return WORD.findall(unicodedata.normalize("NFKC", text).casefold())


def tokens(text: str) -> tuple[str, ...]:
    """Keep informative terms, applying the same aliases to questions and evidence."""
    return tuple(ALIASES.get(word, word) for word in raw_tokens(text) if word not in STOPWORDS)


def iso_date(value: object) -> date:
    """Accept only YYYY-MM-DD, then check that it denotes a real calendar date."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value, re.ASCII):
        raise ValueError("invalid date")
    return date.fromisoformat(value)


def safe_string(value: object, limit: int) -> bool:
    """Check bounded text for control/surrogate characters and edge whitespace."""
    return (
        isinstance(value, str) and 0 < len(value) <= limit and value.strip() == value
        and all(unicodedata.category(char) not in {"Cc", "Cs"} for char in value)
    )


def strict_json(raw: str | bytes) -> object:
    """Reject duplicate keys and nonfinite literals before domain validation.

    Duplicate keys would otherwise silently overwrite earlier values, making
    corpus metadata or a provider selection ambiguous to a reviewer.
    """
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError("nonfinite number")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


@dataclass(frozen=True, slots=True)
class Request:
    """Validated question and host-selected scope for one stateless query.

    Audience is a simulated access context, not proof of authenticated identity.
    The selector receives this scope but cannot change it.
    """

    question: str
    backend: str
    audience: str
    version: str
    as_of: date

    @classmethod
    def validate(cls, question, backend="replay", audience="public", version="2.0", as_of=None):
        """Validate without coercion; the engine supplies the default UTC date."""
        try:
            if not safe_string(question, 1000) or len(raw_tokens(question)) > 128:
                raise ValueError
            if backend not in ("replay", "openai") or audience not in ("public", "staff"):
                raise ValueError
            if not isinstance(version, str) or not VERSION.fullmatch(version):
                raise ValueError
            day = iso_date(as_of)
        except (ValueError, TypeError):
            raise AgentError("invalid_input") from None
        return cls(question, backend, audience, version, day)

    def scope(self) -> dict:
        """Expose the fixed product and caller scope used for filtering and audit."""
        return {"product": "atlasdesk", "version": self.version, "audience": self.audience,
                "as_of": self.as_of.isoformat()}
