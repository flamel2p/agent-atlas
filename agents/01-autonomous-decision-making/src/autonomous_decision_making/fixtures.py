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
    ticket: Ticket
    observation_json: str
    proposal_override: dict | None


def load_example(name: str) -> Example:
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
    """Read one preselected snapshot; the controller validates its contents."""

    def __init__(self, observation_json: str):
        self._observation_json = observation_json

    def get_service_status(self, service: str) -> str:
        if service not in {"api", "dashboard"}:
            raise ValueError("invalid_service")
        return self._observation_json
