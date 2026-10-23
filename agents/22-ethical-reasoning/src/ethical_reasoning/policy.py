"""Host-owned synthetic rules. Every rule runs and every finding denies dispatch.

Disparity here means the smallest observed selection rate divided by the largest.
Exact fractions avoid a rounded threshold comparison. This ratio and minimum group
size are teaching choices, not statistical, causal, ethical, or legal guarantees.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType

from .domain import ActionKind, PUBLISHABLE_FIELDS, Recipient, Request


@dataclass(frozen=True)
class Finding:
    """A host rule failure with a stable identifier and bounded evidence summary."""

    policy_id: str
    code: str
    evidence: str


@dataclass(frozen=True)
class Policy:
    policy_id: str
    check: Callable[[Request], tuple[Finding, ...]]


def _action(request: Request) -> tuple[Finding, ...]:
    if request.action.kind != ActionKind.PUBLISH_SUMMARY:
        return (Finding("SYN-ACTION-1", "forbidden_action", "only aggregate publication is permitted"),)
    return ()


def _recipient(request: Request) -> tuple[Finding, ...]:
    if request.action.recipient != Recipient.INTERNAL:
        return (Finding("SYN-RECIPIENT-1", "forbidden_recipient", "only the internal dashboard is permitted"),)
    return ()


def _restricted_fields(request: Request) -> tuple[Finding, ...]:
    if any(field not in PUBLISHABLE_FIELDS for field in request.action.fields):
        return (Finding("SYN-FIELDS-1", "restricted_fields", "symbolic personal fields require redaction"),)
    return ()


def _remaining_fields(request: Request) -> tuple[Finding, ...]:
    if not any(field in PUBLISHABLE_FIELDS for field in request.action.fields):
        return (Finding("SYN-FIELDS-2", "no_publishable_fields", "no aggregate field is available to publish"),)
    return ()


def _sample(request: Request) -> tuple[Finding, ...]:
    if any(group.eligible < 20 for group in request.groups):
        return (Finding("SYN-SAMPLE-1", "insufficient_group_size", "each synthetic group requires at least 20 observations"),)
    return ()


def _disparity(request: Request) -> tuple[Finding, ...]:
    rates = tuple(Fraction(group.selected, group.eligible) for group in request.groups)
    maximum = max(rates)
    if maximum == 0:
        return (Finding("SYN-DISPARITY-1", "undefined_ratio", "all rates are zero; min/max is undefined"),)
    ratio = min(rates) / maximum
    if ratio < Fraction(4, 5):
        return (Finding("SYN-DISPARITY-1", "disparity_below_threshold", f"observed min/max={ratio}; required>=4/5"),)
    return ()


# Both the registry and its records are immutable. JSON cannot choose checks,
# override thresholds, or omit an independent failure during redaction.
POLICIES: Mapping[str, Policy] = MappingProxyType({
    policy.policy_id: policy
    for policy in (
        Policy("SYN-ACTION-1", _action),
        Policy("SYN-RECIPIENT-1", _recipient),
        Policy("SYN-FIELDS-1", _restricted_fields),
        Policy("SYN-FIELDS-2", _remaining_fields),
        Policy("SYN-SAMPLE-1", _sample),
        Policy("SYN-DISPARITY-1", _disparity),
    )
})


def evaluate(request: Request) -> tuple[Finding, ...]:
    """Collect every rule failure. A finding is a denial regardless of severity."""

    return tuple(finding for policy in POLICIES.values() for finding in policy.check(request))
