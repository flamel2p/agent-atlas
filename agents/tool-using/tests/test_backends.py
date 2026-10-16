from copy import deepcopy
import importlib
import json
import logging
from types import SimpleNamespace

import pytest

from tool_using.backends import OpenAIBackend, ReplayBackend
from tool_using.contracts import MODEL, Failure, RunConfig


SECRET = "sk-test-never-log-this-value"
TASK = "Compare total revenue by channel"


def call(name="inspect_dataset", arguments="{}", call_id="call_one", **extra):
    return {"type": "function_call", "id": "fc_one", "name": name, "arguments": arguments, "call_id": call_id, **extra}


def message(content=None, **extra):
    return {
        "type": "message", "id": "msg_one", "role": "assistant", "status": "completed",
        "content": content if content is not None else [{"type": "output_text", "text": "Finished.", "annotations": []}],
        **extra,
    }


def response(output=None, **extra):
    return SimpleNamespace(
        **{
            "status": "completed", "output": output if output is not None else [call()],
            "error": None, "incomplete_details": None, "model": MODEL,
            "_request_id": "req_safe", "usage": {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
            **extra,
        }
    )


class FakeClient:
    def __init__(self, *responses):
        self.script = iter(responses)
        self.calls = []
        self.responses = self
        self.closed = 0

    def create(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        item = next(self.script)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        self.closed += 1


def live(client, output_format="bar"):
    return OpenAIBackend(RunConfig(mode="live", task=TASK, output_format=output_format, example=None), SECRET, client)


def test_replay_imports_no_sdk_or_tools_and_uses_real_summary_handle(monkeypatch):
    def forbidden_import(*args, **kwargs):
        pytest.fail("Replay must not import an SDK or construct a network client")

    monkeypatch.setattr(importlib, "import_module", forbidden_import)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend = ReplayBackend(RunConfig())
    assert backend.next(None).calls[0].name == "inspect_dataset"
    assert json.loads(backend.next({"row_count": 6}).calls[0].arguments) == {"metric": "revenue_sen"}
    chart = backend.next({"summary_id": "summary-real-handle"}).calls[0]
    assert chart.name == "render_bar_chart"
    assert json.loads(chart.arguments) == {"summary_id": "summary-real-handle"}
    assert backend.next({"artifact_id": "chart-real-handle"}).calls == ()
    backend.close()


def test_replay_spend_and_deliberate_rejection():
    backend = ReplayBackend(RunConfig(example="spend-by-channel-table", output_format="table"))
    backend.next(None)
    assert json.loads(backend.next({}).calls[0].arguments) == {"metric": "spend_sen"}
    assert backend.next({"summary_id": "real"}).calls == ()
    invalid = ReplayBackend(RunConfig(example="invalid-tool-call"))
    assert invalid.next(None).calls[0].name == "average_by_channel"


def test_replay_rejects_missing_summary_handle():
    backend = ReplayBackend(RunConfig())
    backend.next(None)
    backend.next({})
    with pytest.raises(Failure) as error:
        backend.next({})
    assert error.value.code == "invalid_tool_result"


def test_exact_client_options_ignore_api_base_override(monkeypatch):
    import openai

    constructor = []
    client = FakeClient(response([message()]))

    def construct(**kwargs):
        constructor.append(kwargs)
        return client

    monkeypatch.setenv("OPENAI_BASE_URL", "https://untrusted.invalid")
    monkeypatch.setattr(openai, "OpenAI", construct)
    backend = OpenAIBackend(RunConfig(mode="live", example=None), SECRET)
    assert constructor == [{"api_key": SECRET, "base_url": "https://api.openai.com/v1", "max_retries": 0, "timeout": 30.0}]
    backend.close()
    backend.close()
    assert client.closed == 1


@pytest.mark.parametrize("output_format,names", [
    ("table", {"inspect_dataset", "sum_by_channel"}),
    ("bar", {"inspect_dataset", "sum_by_channel", "render_bar_chart"}),
])
def test_exact_request_options_and_tool_authority(output_format, names):
    client = FakeClient(response())
    decision = live(client, output_format).next(None)
    request = client.calls[0]
    assert {key: value for key, value in request.items() if key not in {"tools", "instructions", "input"}} == {
        "model": MODEL, "tool_choice": "auto", "parallel_tool_calls": False, "store": False,
        "background": False, "reasoning": {"effort": "none"}, "max_output_tokens": 1200, "timeout": 30.0,
    }
    assert request["input"] == [{"role": "user", "content": TASK}]
    assert f"output mode is {output_format}" in request["instructions"]
    assert {tool["name"] for tool in request["tools"]} == names
    for tool in request["tools"]:
        assert tool["type"] == "function"
        assert tool["strict"] is True
        assert tool["parameters"]["additionalProperties"] is False
        assert set(tool["parameters"].get("required", [])) == set(tool["parameters"]["properties"])
    assert decision.metadata == {
        "requested_model": MODEL, "reported_model": MODEL, "request_id": "req_safe",
        "usage": {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
    }


def test_history_preserves_sdk_output_reasoning_phase_and_correlated_result():
    from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseReasoningItem

    reasoning = ResponseReasoningItem(id="rs_one", summary=[], type="reasoning", encrypted_content="opaque-private-content")
    commentary = ResponseOutputMessage(**message(phase="commentary"))
    proposed = ResponseFunctionToolCall(**call())
    client = FakeClient(response([reasoning, commentary, proposed]), response([message()]))
    backend = live(client)
    assert backend.next(None).calls[0].call_id == "call_one"
    result = {"dataset_id": "campaign-demo-v1", "row_count": 6}
    final = backend.next(result)
    history = client.calls[1]["input"]
    assert history[1] == reasoning.model_dump(mode="json", exclude_none=True, by_alias=True)
    assert history[2]["phase"] == "commentary"
    assert history[3] == proposed.model_dump(mode="json", exclude_none=True, by_alias=True)
    assert history[4]["type"] == "function_call_output"
    assert history[4]["call_id"] == "call_one"
    assert json.loads(history[4]["output"]) == result
    assert final.calls == ()
    assert "opaque-private-content" not in json.dumps(final.metadata)
    assert len(client.calls[0]["input"]) == 1


@pytest.mark.parametrize("malformed,expected", [
    (response([call(), message([{"type": "refusal", "refusal": SECRET}])]), "provider_refusal"),
    (response([call()], status="failed", error={"message": SECRET}), "provider_error"),
    (response([call()], status="incomplete", incomplete_details={"reason": "max_output_tokens"}), "incomplete_result"),
    (response([call()], incomplete_details={"reason": SECRET}), "incomplete_result"),
    (response([call()], status="in_progress"), "provider_error"),
    (response([call(), call(call_id="call_two")]), "invalid_tool_call"),
    (response([call(), {"type": "web_search_call", "status": "completed"}]), "provider_error"),
    (response([call(), message([{ "type": "unknown", "text": SECRET}])]), "provider_error"),
    (response([call(), message(status="incomplete")]), "provider_error"),
    (response([call(), message(role="user")]), "provider_error"),
    (response([call(arguments={"metric": "spend_sen"})]), "invalid_tool_call"),
    (response([call(call_id="bad\n" + SECRET)]), "invalid_tool_call"),
    (response([call(status="incomplete")]), "invalid_tool_call"),
    (response([call(namespace="other")]), "invalid_tool_call"),
    (response([call(caller={"type": "program", "caller_id": "program_one"})]), "invalid_tool_call"),
    (response([call(**{"async": True})]), "invalid_tool_call"),
    (response([{"type": "reasoning", "summary": "malformed"}, call()]), "provider_error"),
    (response([{"type": "reasoning", "summary": [], "content": [{"type": "refusal", "text": SECRET}]}, call()]), "provider_error"),
    (response(output="not-a-list"), "provider_error"),
    (response([object()]), "provider_error"),
])
def test_entire_invalid_response_rejected_before_returning_a_call(malformed, expected):
    client = FakeClient(malformed)
    backend = live(client)
    with pytest.raises(Failure) as error:
        backend.next(None)
    assert error.value.code == expected
    assert SECRET not in str(error.value)
    assert SECRET not in json.dumps(error.value.as_dict())
    assert len(client.calls) == 1
    with pytest.raises(Failure) as terminal:
        backend.next(None)
    assert terminal.value.code == "invalid_state"
    assert len(client.calls) == 1


@pytest.mark.parametrize("usage", [
    {"input_tokens": True, "output_tokens": 10, "total_tokens": 11},
    {"input_tokens": -1, "output_tokens": 10, "total_tokens": 9},
    {"input_tokens": 100, "output_tokens": 10, "total_tokens": 111},
    {"input_tokens": "100", "output_tokens": 10, "total_tokens": 110},
    {"input_tokens": 100},
])
def test_rejects_malformed_token_usage(usage):
    with pytest.raises(Failure) as error:
        live(FakeClient(response(usage=usage))).next(None)
    assert error.value.code == "provider_error"


def test_optional_metadata_is_sanitized():
    decision = live(FakeClient(response([message()], model=SECRET, _request_id=SECRET, usage=None))).next(None)
    assert decision.metadata == {"requested_model": MODEL, "reported_model": None, "request_id": None, "usage": None}


@pytest.mark.parametrize("returned", [
    response([message([{"type": "refusal", "refusal": SECRET}])]),
    response(status="incomplete", incomplete_details={"reason": "max_output_tokens"}),
])
def test_response_usage_is_retained_on_refusal_and_incomplete_results(returned):
    backend = live(FakeClient(returned))
    with pytest.raises(Failure):
        backend.next(None)
    assert backend.last_metadata == {
        "requested_model": MODEL, "reported_model": MODEL, "request_id": "req_safe",
        "usage": {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
    }
    assert SECRET not in json.dumps(backend.last_metadata)


@pytest.mark.parametrize("later", [
    TimeoutError(SECRET),
    response(usage={"input_tokens": "unsafe", "output_tokens": 1, "total_tokens": 1}),
])
def test_metadata_resets_before_transport_failure_or_untrusted_usage(later):
    backend = live(FakeClient(response(), later))
    first = backend.next(None)
    assert first.metadata["usage"]["total_tokens"] == 110
    with pytest.raises(Failure):
        backend.next({"row_count": 6})
    assert backend.last_metadata is None


@pytest.mark.parametrize("exception,expected", [(RuntimeError(SECRET), "provider_error"), (TimeoutError(SECRET), "provider_timeout")])
def test_provider_exceptions_are_sanitized_and_not_retried(exception, expected):
    exception.request_id = "req_safe"
    exception.status_code = 429
    client = FakeClient(exception)
    with pytest.raises(Failure) as error:
        live(client).next(None)
    assert error.value.code == expected
    assert error.value.request_id == "req_safe"
    assert error.value.http_status == 429
    assert SECRET not in json.dumps(error.value.as_dict())
    assert len(client.calls) == 1


def test_sdk_timeout_is_classified_with_an_injected_client():
    import httpx2
    import openai

    timeout = openai.APITimeoutError(request=httpx2.Request("POST", "https://api.openai.com/v1/responses"))
    client = FakeClient(timeout)
    with pytest.raises(Failure) as error:
        live(client).next(None)
    assert error.value.code == "provider_timeout"
    assert len(client.calls) == 1


def test_missing_and_unsolicited_results_do_not_make_provider_calls():
    client = FakeClient(response())
    backend = live(client)
    backend.next(None)
    with pytest.raises(Failure) as missing:
        backend.next(None)
    assert missing.value.code == "invalid_tool_result"
    assert len(client.calls) == 1
    other = FakeClient(response())
    with pytest.raises(Failure) as unsolicited:
        live(other).next({"result": "unsolicited"})
    assert unsolicited.value.code == "invalid_state"
    assert not other.calls


def test_call_ids_cannot_be_reused():
    backend = live(FakeClient(response(), response()))
    backend.next(None)
    with pytest.raises(Failure) as error:
        backend.next({"row_count": 6})
    assert error.value.code == "invalid_tool_call"


def test_sdk_and_transport_debug_logging_cannot_emit_secrets(monkeypatch, caplog):
    monkeypatch.setenv("OPENAI_LOG", "debug")
    caplog.set_level(logging.DEBUG)
    names = ("openai", "openai._base_client", "httpx", "httpx2", "httpcore.connection", "httpcore2.connection")
    for name in names:
        logger = logging.getLogger(name)
        monkeypatch.setattr(logger, "disabled", False)
        monkeypatch.setattr(logger, "propagate", True)
        logger.setLevel(logging.DEBUG)
    live(FakeClient(response())).next(None)
    for name in names:
        logging.getLogger(name).error("Authorization: %s; body: %s", SECRET, SECRET)
    logging.getLogger("openai.created_after_backend").error(SECRET)
    assert SECRET not in caplog.text


def test_missing_credentials_are_rejected_without_client_call():
    client = FakeClient()
    with pytest.raises(Failure) as error:
        OpenAIBackend(RunConfig(mode="live"), "   ", client)
    assert error.value.code == "missing_credentials"
    assert client.calls == []
