"""Validate the bundled policy identity before the interpreter can report success.

The document identifies one fixed synthetic rule. It is not executable policy or
an extension mechanism. Its exact bytes supply the report's comparison digest.
"""

from dataclasses import dataclass
import hashlib
import json

MAX_POLICY_BYTES = 4096
POLICY_ID = "local-sensitive-log"
POLICY_VERSION = "1.0.0"
RULE_ID = "LSL001"
SCOPE = "Synthetic straight-line Python snippets with labeled values and modeled logger calls."
EXPECTED_POLICY = {
    "schema_version": 1,
    "policy_id": POLICY_ID,
    "version": POLICY_VERSION,
    "rule_id": RULE_ID,
    "scope": SCOPE,
}


class PolicyError(ValueError):
    """Policy bytes failed validation. The exception never includes their contents."""


@dataclass(frozen=True)
class Policy:
    """Validated policy provenance. Rule semantics remain in trusted host code."""

    sha256: str

    def to_dict(self) -> dict[str, object]:
        return {**EXPECTED_POLICY, "sha256": self.sha256}


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise PolicyError("Invalid bundled policy.")
        result[key] = value
    return result


def decode_policy(raw: bytes) -> Policy:
    """Accept at most 4,096 UTF-8 bytes with exactly the supported fields and values."""
    if len(raw) > MAX_POLICY_BYTES:
        raise PolicyError("Invalid bundled policy.")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError):
        raise PolicyError("Invalid bundled policy.") from None
    if type(document) is not dict or document.keys() != EXPECTED_POLICY.keys():
        raise PolicyError("Invalid bundled policy.")
    # Equality alone would accept True as schema 1. Both type and value are fixed.
    for key, expected in EXPECTED_POLICY.items():
        if type(document[key]) is not type(expected) or document[key] != expected:
            raise PolicyError("Invalid bundled policy.")
    return Policy(hashlib.sha256(raw).hexdigest())
