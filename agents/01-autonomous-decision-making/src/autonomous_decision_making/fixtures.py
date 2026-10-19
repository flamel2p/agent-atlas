"""Case-local synthetic intake, observations and replay-only proposal overrides.

The bundled examples stand in for authenticated intake and a status service.
Reading a fixture grants no extra authority: the controller still validates
observation integrity and applies the same policy used for live cognition.
"""

import json
from dataclasses import dataclass
from importlib.resources import files

from .contracts import Ticket

EXAMPLES = (
    "routine-outage", "healthy-service", "low-confidence", "medium-confidence",
    "refund-request", "human-request", "unavailable-human", "restricted-proposal",
    "missing-confidence", "high-impact", "injection-attempt",
)


@dataclass(frozen=True)
class Example:
    """Validated intake plus raw dependency data for one synthetic scenario.

    Keep observations/proposal overrides unvalidated here so the normal controller
    boundaries can exercise malformed or policy-denied results in teaching examples.
    """

    ticket: Ticket
    observation_json: str
    proposal_override: dict | None


def load_example(name: str) -> Example:
    """Load an allowlisted package resource; names cannot select arbitrary paths."""
    if name not in EXAMPLES:
        raise ValueError("invalid_example")
    data = json.loads(files("autonomous_decision_making").joinpath("fixtures", f"{name}.json").read_text())
    if set(data) - {"ticket", "observation", "proposal"}:
        raise ValueError("invalid_example")
    return Example(
        ticket=Ticket.model_validate_json(json.dumps(data["ticket"])),
        observation_json=json.dumps(data["observation"]),
        proposal_override=data.get("proposal"),
    )


class SyntheticStatusTool:
    """Read one preselected snapshot with no network, writes or model arguments.

    The allowlist constrains requested service names. The controller separately
    checks that the returned snapshot actually matches that requested service.
    """

    def __init__(self, observation_json: str):
        self._observation_json = observation_json

    def get_service_status(self, service: str) -> str:
        if service not in {"api", "dashboard"}:
            raise ValueError("invalid_service")
        return self._observation_json
