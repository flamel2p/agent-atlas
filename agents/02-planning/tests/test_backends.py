import asyncio
import importlib
import json
import logging
from types import SimpleNamespace

import pytest

from planning_agent import backends
from planning_agent.backends import OpenAIPlanner, ReplayPlanner
from planning_agent.contracts import Failure, MAX_OUTPUT_TOKENS, MODEL, REQUEST_SECONDS, WORKERS
from planning_agent.controller import run
from planning_agent.fixtures import load_example


def context():
    return {"objective": "Synthetic objective", "availability": dict.fromkeys(WORKERS, True),
            "deadline": 20, "current_tick": 0, "fixed_tasks": [], "completed": [],
            "running": [], "prior_plan": None}


def response(plan=None):
    proposal = plan if plan is not None else ReplayPlanner().propose(context(), timeout=1).model_dump()
    return {"status": "completed", "error": None, "incomplete_details": None,
            "output": [{"type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": json.dumps(proposal)}]}]}


@pytest.fixture
def sdk(monkeypatch):
    monkeypatch.delenv("OPENAI_CUSTOM_HEADERS", raising=False)
    captured = {"clients": [], "http": [], "calls": [], "closed": 0}

    class MockClient:
        def __init__(self, **kwargs):
            captured["clients"].append(kwargs)
            self.responses = self

        async def create(self, **kwargs):
            captured["calls"].append(kwargs)
            behavior = captured.get("behavior")
            if behavior is not None:
                return await behavior(kwargs)
            return response()

        async def close(self):
            captured["closed"] += 1

    def http_client(**kwargs):
        captured["http"].append(kwargs)
        return SimpleNamespace()

    fake_sdk = SimpleNamespace(AsyncOpenAI=MockClient, DefaultAsyncHttpx2Client=http_client,
                               APITimeoutError=type("APITimeoutError", (Exception,), {}))
    original = importlib.import_module
    monkeypatch.setattr(backends.importlib, "import_module",
                        lambda name, *args: fake_sdk if name == "openai" else original(name, *args))
    return captured


def test_official_endpoint_key_only_no_proxy_redirects_retry_or_logging(sdk, monkeypatch):
    for name, value in {"OPENAI_BASE_URL": "https://untrusted.invalid/v1", "HTTPS_PROXY": "http://untrusted.invalid",
                        "OPENAI_ORG_ID": "ambient-org", "OPENAI_PROJECT_ID": "ambient-project",
                        "OPENAI_ADMIN_KEY": "ambient-admin", "OPENAI_LOG": "debug"}.items():
        monkeypatch.setenv(name, value)
    logger = logging.getLogger("openai.http_client")
    logger.disabled = False
    planner = OpenAIPlanner("synthetic-test-key")
    assert planner.propose(context(), timeout=80).status == "plan"
    client = sdk["clients"][0]
    assert client["api_key"] == "synthetic-test-key"
    assert client["base_url"] == "https://api.openai.com/v1"
    assert client["max_retries"] == 0
    assert client["timeout"] == REQUEST_SECONDS
    assert client["admin_api_key"] == client["organization"] == client["project"] == ""
    assert client["default_headers"] == {"Authorization": "Bearer synthetic-test-key"}
    assert sdk["http"] == [{"trust_env": False, "follow_redirects": False, "timeout": REQUEST_SECONDS}]
    assert sdk["closed"] == 1 and logger.disabled


def test_request_has_strict_schema_no_tools_store_or_reasoning_summary(sdk):
    OpenAIPlanner("synthetic-test-key").propose(context(), timeout=3.5)
    request = sdk["calls"][0]
    assert request["model"] == MODEL
    assert request["tools"] == [] and request["tool_choice"] == "none"
    assert request["store"] is request["background"] is False
    assert request["reasoning"] == {"effort": "none"}
    assert request["max_output_tokens"] == MAX_OUTPUT_TOKENS == 2500
    assert request["timeout"] == 3.5
    assert "previous_response_id" not in request
    output_format = request["text"]["format"]
    assert output_format["type"] == "json_schema" and output_format["strict"] is True
    schema = output_format["schema"]
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    assert set(schema["required"]) == {"status", "tasks"}
    assert schema["$defs"]["PlannedTask"]["additionalProperties"] is False
    sent = json.loads(request["input"][0]["content"])
    assert sent["state"] == context()
    assert len(sent["domain"]["tasks"]) == 6 and sent["domain"]["max_concurrency"] == 2


def test_revision_request_carries_fixed_records_observations_and_prior_plan(sdk):
    async def adapt(request):
        current = json.loads(request["input"][0]["content"])["state"]
        return response(ReplayPlanner().propose(current, timeout=1).model_dump())
    sdk["behavior"] = adapt
    report = run(load_example("reviewer-unavailable"), OpenAIPlanner("synthetic-test-key"), mode="live")
    assert report["status"] == "completed" and report["planning_calls"] == 2
    state = json.loads(sdk["calls"][1]["input"][0]["content"])["state"]
    assert state["current_tick"] == 4
    assert state["availability"]["reviewer-primary"] is False
    assert {task["id"] for task in state["fixed_tasks"]} == {"requirements", "examples", "draft"}
    assert {item["task"] for item in state["completed"]} == {"requirements", "examples", "draft"}
    assert state["prior_plan"]["status"] == "plan"
    assert "Synthetic objective" not in json.dumps(report)


@pytest.mark.parametrize("change,reason", [
    (lambda r: r.update(status="incomplete"), "provider_incomplete"),
    (lambda r: r.update(incomplete_details={"reason": "max_output_tokens"}), "provider_incomplete"),
    (lambda r: r.update(status="failed", error={"message": "sensitive payload"}), "provider_error"),
    (lambda r: r.update(output=[]), "provider_malformed"),
    (lambda r: r.update(output=[{"type": "function_call", "name": "shell"}]), "provider_malformed"),
    (lambda r: r["output"][0].update(role="user"), "provider_malformed"),
    (lambda r: r["output"][0].update(content=[{"type": "refusal", "refusal": "sensitive payload"}]), "provider_refusal"),
    (lambda r: r["output"][0]["content"][0].update(text="sensitive payload"), "provider_malformed"),
    (lambda r: r["output"][0]["content"][0].update(text="x" * 20_001), "provider_malformed"),
    (lambda r: r["output"][0]["content"][0].update(text='{"status":"plan","tasks":[],"extra":"sensitive payload"}'), "provider_malformed"),
    (lambda r: r["output"].append(r["output"][0]), "provider_malformed"),
])
def test_provider_failures_sanitized_terminal_and_no_replay_fallback(sdk, change, reason):
    raw = response()
    change(raw)
    async def invalid(request):
        return raw
    sdk["behavior"] = invalid
    report = run(load_example("normal"), OpenAIPlanner("synthetic-test-key"), mode="live")
    assert report["status"] == "failed" and report["reason"] == reason
    assert report["release_artifact"] is None
    assert len(sdk["calls"]) == report["planning_calls"] == 1
    assert not any(event["event"] == "task_started" for event in report["trace"])
    assert "sensitive payload" not in json.dumps(report)


def test_semantically_bad_structured_proposal_still_rejected_by_host(sdk):
    async def invalid(request):
        return response({"status": "plan", "tasks": []})
    sdk["behavior"] = invalid
    report = run(load_example("normal"), OpenAIPlanner("synthetic-test-key"), mode="live")
    assert report["status"] == "failed" and report["reason"] == "invalid_plan"
    assert report["release_artifact"] is None


@pytest.mark.parametrize("error,reason", [(RuntimeError("secret token"), "provider_error"),
                                         (TimeoutError("secret token"), "provider_timeout")])
def test_transport_errors_no_retry_or_raw_payload(sdk, error, reason):
    async def broken(request):
        raise error
    sdk["behavior"] = broken
    report = run(load_example("normal"), OpenAIPlanner("synthetic-test-key"), mode="live")
    assert report["reason"] == reason
    assert report["status"] == ("limit_reached" if reason == "provider_timeout" else "failed")
    assert len(sdk["calls"]) == 1
    assert "secret" not in json.dumps(report)


def test_async_total_request_timeout_cancels_slow_request(sdk):
    cancelled = []
    async def slow(request):
        try:
            await asyncio.sleep(2)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
    sdk["behavior"] = slow
    with pytest.raises(Failure, match="provider_timeout"):
        OpenAIPlanner("synthetic-test-key").propose(context(), timeout=0.02)
    assert cancelled == [True] and sdk["closed"] == 1


def test_missing_key_and_dependency_fail_preflight(sdk, monkeypatch):
    with pytest.raises(Failure, match="missing_credentials"):
        OpenAIPlanner(" ")
    def missing(name):
        raise ImportError("raw import details")
    monkeypatch.setattr(backends.importlib, "import_module", missing)
    with pytest.raises(Failure, match="missing_live_dependency"):
        OpenAIPlanner("synthetic-test-key")
    assert not sdk["clients"] and not sdk["calls"]


def test_ambient_custom_headers_fail_preflight_without_sending(sdk, monkeypatch):
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "Authorization: Bearer ambient-key")
    with pytest.raises(Failure, match="provider_error"):
        OpenAIPlanner("synthetic-test-key")
    assert not sdk["clients"] and not sdk["calls"]
