import json

import pytest

from autonomous_decision_making.contracts import StatusEvidence
from autonomous_decision_making.fixtures import load_example


@pytest.fixture
def ticket():
    return load_example("routine-outage").ticket.model_dump()


@pytest.fixture
def evidence():
    raw = load_example("routine-outage").observation_json
    return StatusEvidence.model_validate_json(raw).model_dump()


@pytest.fixture
def proposal():
    return {"route": "autonomous", "confidence": 0.95, "action": "status_reply", "reason_code": "incident_detected"}


class ToolProbe:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def get_service_status(self, service):
        self.calls.append(service)
        if self.error:
            raise self.error
        return self.result


class CognitionProbe:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def propose(self, ticket, evidence):
        self.calls.append((ticket, evidence))
        if self.error:
            raise self.error
        return self.result
