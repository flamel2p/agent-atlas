import builtins
from copy import deepcopy
import json
import logging
import os
import warnings

import httpx2
import pytest

from knowledge_agent.contracts import AgentError
from knowledge_agent.corpus import load_bundled, validate_corpus
from knowledge_agent.engine import run
from knowledge_agent.provider import MAX_OUTPUT_TOKENS, TIMEOUT_SECONDS, preflight_openai


DAY = "2026-10-19"
ENVIRONMENT = {"OPENAI_API_KEY": "sk-synthetic-test-key", "OPENAI_MODEL": "explicit-test-model"}


def envelope(selection=None):
    return {
        "id": "resp_synthetic", "object": "response", "created_at": 1792368000,
        "model": "explicit-test-model", "status": "completed", "error": None,
        "incomplete_details": None, "parallel_tool_calls": False,
        "tools": [], "tool_choice": "none",
        "output": [{"id": "msg_synthetic", "type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": json.dumps(selection or {
                        "status": "selected", "passage_ids": ["subscription-policy-v2:p1"]}),
                                 "annotations": []}]}],
    }


def execute(handler, **kwargs):
    transport = httpx2.MockTransport(handler)
    return run("How can I cancel my subscription?", backend="openai", as_of=DAY,
               provider_factory=lambda: preflight_openai(environ=ENVIRONMENT, transport=transport), **kwargs)


def test_actual_sdk_request_bounds_authority_and_eligible_payload(monkeypatch, capsys):
    requests = []
    captured = {}
    monkeypatch.setenv("OPENAI_BASE_URL", "https://malicious.invalid")
    monkeypatch.setenv("OPENAI_ORG_ID", "ambient-org-secret")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "ambient-project-secret")
    monkeypatch.setenv("OPENAI_ADMIN_KEY", "ambient-admin-secret")
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "Authorization: Bearer ambient-key\nX-Secret: ambient-custom-secret")
    monkeypatch.setenv("OPENAI_LOG", "debug")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")

    def handler(request):
        requests.append(request)
        captured.update(json.loads(request.content))
        logging.getLogger("openai._base_client").error("provider-payload-must-not-be-logged")
        return httpx2.Response(200, json=envelope())

    result, code = execute(handler)
    assert code == 0 and result["status"] == "answered"
    assert result["counts"] == {"search_calls": 1, "model_calls": 1}
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://api.openai.com/v1/responses"
    assert request.method == "POST"
    assert request.headers["authorization"] == "Bearer sk-synthetic-test-key"
    assert "x-secret" not in request.headers
    assert "ambient" not in str(dict(request.headers))
    assert all(value == TIMEOUT_SECONDS for value in request.extensions["timeout"].values())
    assert captured["model"] == ENVIRONMENT["OPENAI_MODEL"]
    assert captured["store"] is False and captured["stream"] is False and captured["background"] is False
    assert captured["tools"] == [] and captured["tool_choice"] == "none"
    assert captured["truncation"] == "disabled" and captured["max_output_tokens"] == MAX_OUTPUT_TOKENS
    assert captured["text"]["format"]["strict"] is True
    schema = captured["text"]["format"]["schema"]
    assert schema["additionalProperties"] is False and set(schema["required"]) == {"status", "passage_ids"}
    payload = json.loads(captured["input"][0]["content"])
    assert set(schema["properties"]["passage_ids"]["items"]["enum"]) == {part["passage_id"] for part in payload["passages"]}
    assert len(payload["passages"]) == 3
    serialized = json.dumps(captured)
    for document in validate_corpus(load_bundled()).documents:
        if document.id not in {"subscription-policy-v2", "billing-guide-v2", "support-guide-v2"}:
            assert document.id not in serialized and document.title not in serialized and document.text not in serialized
    assert os.environ["OPENAI_LOG"] == "debug"
    assert "ambient-custom-secret" in os.environ["OPENAI_CUSTOM_HEADERS"]
    output = capsys.readouterr()
    assert output.out == "" and output.err == ""


@pytest.mark.parametrize("environment", [
    {}, {"OPENAI_API_KEY": "key"}, {"OPENAI_MODEL": "model"},
    {"OPENAI_API_KEY": "key\nsecret", "OPENAI_MODEL": "model"},
    {"OPENAI_API_KEY": "key", "OPENAI_MODEL": "bad model"},
    {"OPENAI_API_KEY": "x" * 513, "OPENAI_MODEL": "model"},
    {"OPENAI_API_KEY": "key", "OPENAI_MODEL": "x" * 129},
])
def test_preflight_configuration_before_corpus(environment):
    accesses = []
    result, code = run("cancel", backend="openai", as_of=DAY,
                       corpus_loader=lambda: accesses.append(True),
                       provider_factory=lambda: preflight_openai(environ=environment))
    assert code == 1 and result["reason"] in {"missing_or_invalid_api_key", "missing_or_invalid_model"}
    assert accesses == [] and result["counts"] == {"search_calls": 0, "model_calls": 0}


def test_missing_sdk_preflight_before_corpus(monkeypatch):
    original_import = builtins.__import__
    def missing(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("private installation path")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", missing)
    accesses = []
    result, code = run("cancel", backend="openai", as_of=DAY,
                       corpus_loader=lambda: accesses.append(True),
                       provider_factory=lambda: preflight_openai(environ=ENVIRONMENT))
    assert code == 1 and result["reason"] == "sdk_unavailable"
    assert accesses == [] and "private" not in json.dumps(result)


@pytest.mark.parametrize("options", [{"version": "9.9"}, {"question": "blockchain"}])
def test_no_evidence_makes_zero_sdk_calls(options):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx2.Response(200, json=envelope())
    result, code = run(backend="openai", as_of=DAY,
                       provider_factory=lambda: preflight_openai(environ=ENVIRONMENT, transport=httpx2.MockTransport(handler)),
                       **{"question": "cancel", **options})
    assert code == 0 and result["status"] == "abstained"
    assert result["counts"]["model_calls"] == 0 and calls == []


def test_reasoning_is_not_used_as_evidence():
    response = envelope()
    response["output"].insert(0, {"id": "rs_synthetic", "type": "reasoning", "summary": [
        {"type": "summary_text", "text": "secret reasoning never becomes an answer"}]})
    result, code = execute(lambda _: httpx2.Response(200, json=response))
    assert code == 0 and result["status"] == "answered"
    assert "secret reasoning" not in json.dumps(result)


def bad_envelopes():
    base = envelope()
    cases = []
    for state in ("incomplete", "failed", "in_progress", "cancelled", None):
        response = deepcopy(base)
        response["status"] = state
        cases.append(response)
    response = deepcopy(base)
    response["incomplete_details"] = {"reason": "max_output_tokens"}
    cases.append(response)
    response = deepcopy(base)
    response["error"] = {"code": "server_error", "message": "raw-secret-payload"}
    cases.append(response)
    for output in ([], None, [base["output"][0]] * 2, [{"type": "function_call", "name": "steal", "arguments": "{}", "call_id": "x"}],
                   [{"type": "unknown"}], [{"type": "reasoning", "id": "r", "summary": []}]):
        response = deepcopy(base)
        response["output"] = output
        cases.append(response)
    for content in ([], [{"type": "refusal", "refusal": "raw-secret-payload"}],
                    [{"type": "output_text", "text": "", "annotations": []}],
                    [{"type": "output_text", "text": "raw-secret-payload", "annotations": []}],
                    [{"type": "output_text", "text": "x" * 4097, "annotations": []}],
                    [{"type": "output_text", "text": '{"status":"abstained","status":"selected","passage_ids":[]}', "annotations": []}],
                    base["output"][0]["content"] * 2):
        response = deepcopy(base)
        response["output"][0]["content"] = content
        cases.append(response)
    for field, value in (("status", "incomplete"), ("status", None), ("role", "user")):
        response = deepcopy(base)
        response["output"][0][field] = value
        cases.append(response)
    return cases


@pytest.mark.parametrize("response", bad_envelopes())
def test_invalid_envelopes_fail_closed_without_raw_payload(response):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx2.Response(200, json=response)
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        result, code = execute(handler)
    assert code == 1 and result["status"] == "failed"
    assert result["reason"] in {"provider_incomplete", "provider_error", "provider_malformed", "provider_refusal"}
    assert result["answer"] == "" and result["citations"] == []
    assert len(calls) == 1 and result["counts"]["model_calls"] == 1
    assert "raw-secret-payload" not in json.dumps(result)
    assert emitted == []


@pytest.mark.parametrize("selection", [
    {"status": "selected", "passage_ids": ["unknown-source"]},
    {"status": "selected", "passage_ids": ["staff-retention-v2:p1"]},
    {"status": "selected", "passage_ids": ["subscription-policy-v2:p1"], "answer": "raw-secret-payload"},
    {"status": "selected", "passage_ids": ["subscription-policy-v2:p1"] * 2},
    {"status": "selected", "passage_ids": []},
    {"status": "abstained", "passage_ids": ["subscription-policy-v2:p1"]},
])
def test_actual_sdk_selection_is_still_host_validated(selection):
    result, code = execute(lambda _: httpx2.Response(200, json=envelope(selection)))
    assert code == 1 and result["reason"] == "invalid_selection"
    assert result["answer"] == "" and result["citations"] == []
    assert "raw-secret-payload" not in json.dumps(result)


def test_provider_abstention_is_terminal():
    result, code = execute(lambda _: httpx2.Response(200, json=envelope({"status": "abstained", "passage_ids": []})))
    assert code == 0 and result["status"] == "abstained" and result["reason"] == "evidence_gap"
    assert result["answer"] == "" and result["citations"] == []


@pytest.mark.parametrize("status", [401, 429, 500, 503, 302])
def test_errors_do_not_retry_redirect_or_fallback(status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx2.Response(status, headers={"location": "https://malicious.invalid/redirect"},
                               json={"error": {"message": "raw-secret-payload", "type": "error"}})
    result, code = execute(handler)
    assert code == 1 and result["reason"] == "provider_error"
    assert len(calls) == 1 and result["answer"] == "" and result["citations"] == []
    assert "raw-secret-payload" not in json.dumps(result)


@pytest.mark.parametrize("error_type", [httpx2.ReadTimeout, httpx2.ConnectError, KeyboardInterrupt])
def test_transport_timeout_failure_and_interruption(error_type):
    calls = []
    def handler(request):
        calls.append(request)
        if error_type is KeyboardInterrupt:
            raise KeyboardInterrupt
        raise error_type("raw-secret-payload", request=request)
    result, code = execute(handler)
    assert code == (130 if error_type is KeyboardInterrupt else 1)
    assert result["status"] == ("cancelled" if error_type is KeyboardInterrupt else "failed")
    assert len(calls) == 1 and result["answer"] == "" and result["citations"] == []
    assert "raw-secret-payload" not in json.dumps(result)


def test_sdk_disables_retries_and_proxy_environment():
    provider = preflight_openai(environ=ENVIRONMENT, transport=httpx2.MockTransport(lambda _: httpx2.Response(200, json=envelope())))
    try:
        assert provider.client.max_retries == 0
        assert provider.client._client.trust_env is False
        assert provider.client._client.follow_redirects is False
    finally:
        provider.close()


def test_cleanup_interruption_cancels_an_otherwise_successful_answer():
    class InterruptOnClose:
        def select(self, request, candidates):
            return {"status": "selected", "passage_ids": [candidates[0].id]}

        def close(self):
            raise KeyboardInterrupt

    result, code = run("cancel subscription", backend="openai", as_of=DAY,
                       provider_factory=InterruptOnClose)
    assert code == 130 and result["status"] == "cancelled" and result["reason"] == "interrupted"
    assert result["answer"] == "" and result["citations"] == []
