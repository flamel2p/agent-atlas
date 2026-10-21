"""Validate bounded packaged snapshots before the manager delegates any work.

Identifiers use 1..64 ASCII letters/digits/dot/underscore/hyphen, beginning with
a letter or digit. Record text is 0..500 characters without control characters
other than tab/newline. There are at most 100 records per role and 256 KiB per
UTF-8 resource. Unknown/duplicate keys and implicit type coercion are rejected.
"""

import hashlib
from importlib.resources import files
import json
import re

from .contracts import Record, Role, Scope, Snapshot

MAX_BYTES = 256 * 1024
MAX_RECORDS_PER_ROLE = 100
SCENARIOS = (
    "consistent", "contradictory", "negative", "missing-evidence",
    "prerequisite-failure", "downstream-failure", "timeout", "scoped",
)
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class InputError(ValueError):
    """Bounded diagnostic codes only; never attach arbitrary source contents."""


def identifier(value: object) -> str:
    if type(value) is not str or not _IDENTIFIER.fullmatch(value):
        raise InputError("invalid_identifier")
    return value


def _object(value: object, keys: set[str]) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise InputError("invalid_object_fields")
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate_json_key")
        result[key] = value
    return result


def _constant(_: str) -> None:
    raise InputError("invalid_json_constant")


def parse_snapshot(raw: bytes, target_release: str | None = None) -> Snapshot:
    """Parse untrusted bytes into immutable records, preserving literal assertions.

    Identity is the globally unique (source_id, record_id) pair. A source may
    hold multiple records, but a record cannot be reassigned to another role.
    Target overrides must occur in the snapshot; they never fetch more data.
    """
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise InputError("snapshot_too_large_or_not_bytes")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("malformed_json") from None
    data = _object(data, {"target_release", "environment", "records"})
    declared = identifier(data["target_release"])
    environment = identifier(data["environment"])
    if type(data["records"]) is not list or len(data["records"]) > 300:
        raise InputError("invalid_record_count")
    records = []
    identities = set()
    counts = {role: 0 for role in Role}
    for value in data["records"]:
        value = _object(value, {"role", "source_id", "record_id", "release",
                                "feature_id", "environment", "works", "text"})
        if type(value["role"]) is not str or value["role"] not in Role:
            raise InputError("invalid_role")
        role = Role(value["role"])
        source_id, record_id = identifier(value["source_id"]), identifier(value["record_id"])
        identity = source_id, record_id
        if identity in identities:
            raise InputError("duplicate_record_identity")
        identities.add(identity)
        counts[role] += 1
        if counts[role] > MAX_RECORDS_PER_ROLE:
            raise InputError("too_many_role_records")
        if type(value["works"]) is not bool:
            raise InputError("assertion_must_be_boolean")
        text = value["text"]
        if (type(text) is not str or len(text) > 500
                or any(not c.isprintable() and c not in "\t\n" for c in text)):
            raise InputError("invalid_record_text")
        scope = Scope(identifier(value["release"]), identifier(value["feature_id"]),
                      identifier(value["environment"]))
        records.append(Record(role, source_id, record_id, scope, value["works"], text))
    releases = {record.scope.release for record in records}
    target = declared if target_release is None else identifier(target_release)
    if declared not in releases or target not in releases:
        raise InputError("unsupported_release")
    return Snapshot(target, environment, hashlib.sha256(raw).hexdigest(), tuple(records))


def load_snapshot(scenario: str, target_release: str | None = None) -> Snapshot:
    """Resolve a closed fixture name, never a caller-supplied filesystem path."""
    if type(scenario) is not str or scenario not in SCENARIOS:
        raise InputError("unknown_scenario")
    try:
        with files("chain_orchestrator").joinpath("fixtures", scenario + ".json").open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
    except OSError:
        raise InputError("fixture_unavailable") from None
    return parse_snapshot(raw, target_release)

