import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from autonomous_decision_making.backends import LiveBackend, MODEL, REQUEST_TIMEOUT_SECONDS
from autonomous_decision_making.contracts import Proposal, StatusEvidence, Ticket
from autonomous_decision_making.controller import PROPOSAL_TIMEOUT_SECONDS, run_decision
from conftest import ToolProbe


def message(text, *, kind="output_text", role="assistant", status="completed"):
    return NS(type="message", role=role, status=status, content=[NS(type=kind, text=text)])


def response(proposal):
    return NS(status="completed", output=[message(json.dumps(proposal))])


class ClientFactory:
    def __init__(self, response=None, error=None):
        self.response, self.error = response, error
        self.options, self.requests = [], []
        self.closed = 0

    def __call__(self, **options):
        self.options.append(options)
        outer = self

        class Client:
            async def __aenter__(self):
                self.responses = self
                return self

            async def __aexit__(self, *args):
                outer.closed += 1

            async def create(self, **request):
                outer.requests.append(request)
                if outer.error:
                    raise outer.error
                return outer.response

        return Client()


def run_live(ticket, evidence, factory):
    backend = LiveBackend("synthetic-test-key", client_factory=factory)
    backend.validate_configuration()
    return asyncio.run(run_decision(ticket, ToolProbe(evidence), backend, mode="live"))


def test_mocked_live_call_has_strict_transport_and_request_contract(ticket, evidence, proposal):
    factory = ClientFactory(response(proposal))
    result = run_live(ticket, evidence, factory)
    assert result.exit_code == 0 and result.report.route == "autonomous" and result.report.mode == "live"
    assert len(factory.options) == len(factory.requests) == factory.closed == 1
    options, request = factory.options[0], factory.requests[0]
    assert options["max_retries"] == 0
    assert options["timeout"] == REQUEST_TIMEOUT_SECONDS == PROPOSAL_TIMEOUT_SECONDS == 20
    assert options["base_url"] == "https://api.openai.com/v1"
    assert request["model"] == MODEL == "gpt-6-luna"
    assert request["store"] is False and request["max_output_tokens"] == 400
    assert "tools" not in request and "tool_choice" not in request
    format = request["text"]["format"]
    assert format["type"] == "json_schema" and format["strict"] is True
    schema = format["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"]) == {"route", "confidence", "action", "reason_code"}
    context = json.loads(request["input"][1]["content"])
    assert context["ticket"]["ticket_id"] == ticket["ticket_id"]
    assert context["evidence"]["evidence_id"] == evidence["evidence_id"]
    assert "synthetic-test-key" not in result.report.model_dump_json()


@pytest.mark.parametrize("status", ["incomplete", "failed", "queued", "in_progress", "cancelled", None])
def test_noncompleted_provider_response_never_uses_partial_text(ticket, evidence, proposal, status):
    value = response(proposal)
    value.status = status
    factory = ClientFactory(value)
    result = run_live(ticket, evidence, factory)
    assert result.exit_code == 2 and result.report.policy_reason == "provider_incomplete"
    assert result.report.proposal is None and len(factory.requests) == 1


def test_refusal_is_sanitized_and_never_retried(ticket, evidence):
    factory = ClientFactory(NS(status="completed", output=[message("PRIVATE_REFUSAL", kind="refusal")]))
    result = run_live(ticket, evidence, factory)
    assert result.exit_code == 2 and result.report.policy_reason == "provider_refusal"
    assert len(factory.requests) == 1 and "PRIVATE_REFUSAL" not in result.report.model_dump_json()


@pytest.mark.parametrize("output", [
    None, [], [NS(type="function_call", arguments="PRIVATE_CALL")],
    [message("PRIVATE_PROSE")], [message("{}")], [message('{"route":"autonomous","confidence":true}')],
    [message("x" * 10001)], [message("")], [message(123)],
    [message("{}", kind="unknown")], [message("{}", role="user")], [message("{}", status="in_progress")],
    [message("{}"), message("{}")],
])
def test_invalid_provider_output_is_safe_failure(ticket, evidence, output):
    factory = ClientFactory(NS(status="completed", output=output))
    result = run_live(ticket, evidence, factory)
    assert result.exit_code == 2 and result.report.policy_reason == "provider_invalid_output"
    assert result.report.proposal is None and result.report.response is None
    assert "PRIVATE" not in result.report.model_dump_json()
    assert len(factory.requests) == 1


def test_reasoning_metadata_is_ignored_without_inspecting_it(ticket, evidence, proposal):
    class Reasoning:
        type = "reasoning"

        @property
        def summary(self):
            raise AssertionError("must not inspect reasoning")

        @property
        def content(self):
            raise AssertionError("must not inspect reasoning")

    value = response(proposal)
    value.output.insert(0, Reasoning())
    result = run_live(ticket, evidence, ClientFactory(value))
    assert result.exit_code == 0 and result.report.route == "autonomous"


@pytest.mark.parametrize("output", [[NS(type="reasoning")], [NS(type="reasoning"), NS(type="function_call")]])
def test_reasoning_without_valid_message_is_rejected(ticket, evidence, output):
    result = run_live(ticket, evidence, ClientFactory(NS(status="completed", output=output)))
    assert result.exit_code == 2 and result.report.policy_reason == "provider_invalid_output"


@pytest.mark.parametrize("error,reason", [(RuntimeError("PRIVATE_TRANSPORT_ERROR"), "provider_failure"), (TimeoutError("PRIVATE_TIMEOUT"), "provider_timeout")])
def test_transport_failure_or_timeout_has_no_retry(ticket, evidence, error, reason):
    factory = ClientFactory(error=error)
    result = run_live(ticket, evidence, factory)
    assert result.exit_code == 2 and result.report.policy_reason == reason
    assert len(factory.requests) == factory.closed == 1
    assert "PRIVATE" not in result.report.model_dump_json()


def test_factory_is_not_called_by_configuration_preflight():
    factory = ClientFactory()
    backend = LiveBackend("synthetic-test-key", client_factory=factory)
    backend.validate_configuration()
    assert factory.options == [] and factory.requests == []
