"""Immutable synthetic action and evidence records, plus the JSON schema boundary.

Counts describe observed synthetic groups. They do not authenticate source data or
establish population completeness. Empty Action.fields exists only so the host can
recheck a redaction that removed everything. The input boundary forbids it.
"""

from dataclasses import dataclass
from enum import StrEnum
import re

SCHEMA_VERSION = 1
POLICY_VERSION = "synthetic-v1"
_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,32}\Z")


class InputError(ValueError):
    """A fixed machine-readable code. Never stores untrusted input text."""


class ActionKind(StrEnum):
    PUBLISH_SUMMARY = "publish_summary"
    EXPORT_RECORDS = "export_records"
    RANK_INDIVIDUALS = "rank_individuals"


class Recipient(StrEnum):
    INTERNAL = "internal_dashboard"
    EXTERNAL = "external"


class Field(StrEnum):
    COUNT = "aggregate_count"
    RATE = "selection_rate"
    NAME = "synthetic_name"
    EMAIL = "synthetic_email"


PUBLISHABLE_FIELDS = frozenset({Field.COUNT, Field.RATE})


def _identifier(value: object) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise InputError("invalid_identifier")


@dataclass(frozen=True)
class Action:
    """A proposal, never a permission. Fields name symbols, not personal values."""

    action_id: str
    kind: ActionKind
    recipient: Recipient
    fields: tuple[Field, ...]

    def __post_init__(self) -> None:
        _identifier(self.action_id)
        if not isinstance(self.kind, ActionKind) or not isinstance(self.recipient, Recipient):
            raise InputError("invalid_action_type")
        if (not isinstance(self.fields, tuple) or len(self.fields) > 4
                or any(not isinstance(field, Field) for field in self.fields)
                or len(set(self.fields)) != len(self.fields)):
            raise InputError("invalid_fields")


@dataclass(frozen=True)
class GroupCount:
    """Observed denominators and selections for one synthetic group, owned by a run."""

    group_id: str
    eligible: int
    selected: int

    def __post_init__(self) -> None:
        _identifier(self.group_id)
        if type(self.eligible) is not int or not 1 <= self.eligible <= 10_000:
            raise InputError("invalid_eligible_count")
        if type(self.selected) is not int or not 0 <= self.selected <= self.eligible:
            raise InputError("invalid_selected_count")


@dataclass(frozen=True)
class Request:
    """Validated immutable context. Mitigation may change only symbolic fields."""

    action: Action
    groups: tuple[GroupCount, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.action, Action):
            raise InputError("invalid_action_type")
        if (not isinstance(self.groups, tuple) or not 2 <= len(self.groups) <= 8
                or any(not isinstance(group, GroupCount) for group in self.groups)):
            raise InputError("invalid_groups")
        if len({group.group_id for group in self.groups}) != len(self.groups):
            raise InputError("duplicate_group")


def _object(value: object, keys: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise InputError("invalid_object_fields")
    return value


def parse_request(value: object) -> Request:
    """Reject schema drift before any dispatcher exists. Input cannot supply policy."""

    root = _object(value, {"schema_version", "policy_version", "synthetic", "action", "groups"})
    if type(root["schema_version"]) is not int or root["schema_version"] != SCHEMA_VERSION:
        raise InputError("unsupported_schema_version")
    if root["policy_version"] != POLICY_VERSION:
        raise InputError("unsupported_policy_version")
    if root["synthetic"] is not True:
        raise InputError("synthetic_input_required")
    proposal = _object(root["action"], {"action_id", "kind", "recipient", "fields"})
    fields = proposal["fields"]
    if not isinstance(fields, list) or not 1 <= len(fields) <= 4:
        raise InputError("invalid_fields")
    try:
        action = Action(proposal["action_id"], ActionKind(proposal["kind"]),
                        Recipient(proposal["recipient"]), tuple(Field(field) for field in fields))
    except (TypeError, ValueError) as exc:
        raise InputError("invalid_action") from exc
    groups = root["groups"]
    if not isinstance(groups, list) or not 2 <= len(groups) <= 8:
        raise InputError("invalid_groups")
    parsed = []
    for group in groups:
        record = _object(group, {"group_id", "eligible", "selected"})
        parsed.append(GroupCount(record["group_id"], record["eligible"], record["selected"]))
    return Request(action, tuple(parsed))
