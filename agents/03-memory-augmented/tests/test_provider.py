import asyncio
from datetime import timedelta
import io
import json
import logging
import sqlite3
from types import SimpleNamespace as NS

import pytest

from memory_agent import provider
from memory_agent.contracts import Failure
from memory_agent.knowledge import candidates


def response(text='{"faq_ids":["faq-working-memory"]}', **changes):
    return NS(**{
        "status": "completed", "error": None, "incomplete_details": None,
        "output": [NS(type="message", role="assistant", status="completed",
                      content=[NS(type="output_text", text=text)])], **changes,
    })


@pytest.fixture
def environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-not-a-real-key")
    monkeypatch.setenv("MEMORY_AGENT_MODEL", "synthetic-model")
    monkeypatch.delenv("OPENAI_CUSTOM_HEADERS", raising=False)


def snapshot(tmp_path):
    with sqlite3.connect(tmp_path / "private-data/demo.sqlite3") as connection:
        return tuple(connection.iterdump())


@pytest.mark.parametrize("selection", [["invented"], ["faq-retention"],
    ["faq-working-memory", "faq-working-memory"], ["faq-working-memory"] * 4, "faq-working-memory", [1], None])
def test_invalid_model_ids_fail_without_writes(turn, tmp_path, selection):
    turn(remember_style="example-first")
    before = snapshot(tmp_path)
    result = turn(mode="live", remember_style="step-by-step", selector=lambda *_: selection)
    assert result["failure_code"] == "provider_selection"
    assert result["answer"] is None and result["memory_committed"] is False
    assert snapshot(tmp_path) == before


def test_model_abstention_is_processed_without_factual_answer(turn):
    result = turn(mode="live", remember_style="example-first", selector=lambda *_: [])
    assert result["status"] == "insufficient_knowledge" and result["evidence"] == []
    assert result["memory_committed"] is True
    assert turn()["preference"]["style"] == "example-first"


def test_model_selection_cannot_modify_preference(turn):
    turn(remember_style="example-first")
    result = turn(mode="live", selector=lambda *_: ["faq-semantic-memory"])
    assert result["preference"]["style"] == "example-first"
    assert result["evidence"][0]["id"] == "faq-semantic-memory"
    assert turn()["preference"]["style"] == "example-first"


def test_provider_context_is_bounded_scoped_and_identity_free(turn, now, monkeypatch, environment):
    turn(user="secret-other-user", session="secret-other-session", query="working private-other-episode")
    for index in range(6):
        turn(user="private-user", session=f"private-session-{index}", at=now + timedelta(seconds=index))
    payloads = []
    async def fake_request(payload, key):
        payloads.append(payload)
        return response()
    monkeypatch.setattr(provider, "_request", fake_request)
    result = turn(user="private-user", session="private-current-session", mode="live", at=now + timedelta(seconds=7))
    assert result["status"] == "answered" and len(payloads) == 1
    payload = payloads[0]
    context = json.loads(payload["input"][0]["content"])
    assert len(context["episodes"]) == len(context["candidates"]) == 3
    assert context["style"] == "concise"
    raw = json.dumps(payload)
    for sentinel in ("secret-other", "private-user", "private-session", "private-current", "synthetic-not-a-real-key"):
        assert sentinel not in raw
    assert payload["max_output_tokens"] == 512
    assert payload["store"] is False and payload["background"] is False
    assert payload["tools"] == [] and payload["tool_choice"] == "none"
    schema = payload["text"]["format"]
    assert schema["strict"] is True and schema["type"] == "json_schema"
    assert schema["schema"]["additionalProperties"] is False
    assert schema["schema"]["required"] == ["faq_ids"]


@pytest.mark.parametrize("text", ["not JSON", "{}", "[]", '{"faq_ids":[],"style":"concise"}',
    '{"faq_ids":[],"faq_ids":["faq-working-memory"]}', '{"faq_ids":"faq-working-memory"}',
    '{"faq_ids":[null]}', '{"faq_ids":["a","b","c","d"]}', "x" * 4097])
def test_invalid_provider_schema_fails_and_preserves_memory(turn, tmp_path, monkeypatch, environment, text):
    turn(remember_style="example-first")
    before = snapshot(tmp_path)
    async def fake_request(*_):
        return response(text)
    monkeypatch.setattr(provider, "_request", fake_request)
    result = turn(mode="live", remember_style="step-by-step")
    assert result["failure_code"] == "provider_output"
    assert result["answer"] is None and snapshot(tmp_path) == before


@pytest.mark.parametrize("changes,code", [
    ({"status": "incomplete"}, "provider_incomplete"),
    ({"status": "queued"}, "provider_incomplete"),
    ({"error": {"message": "private"}}, "provider_output"),
    ({"incomplete_details": {"reason": "max_output_tokens"}}, "provider_incomplete"),
    ({"output": [NS(type="message", role="assistant", status="completed", content=[NS(type="refusal", refusal="private")])]}, "provider_refusal"),
    ({"output": [NS(type="function_call", name="forget", arguments="private")]}, "provider_output"),
    ({"output": []}, "provider_output"),
    ({"output": [NS(type="message", role="assistant", status="incomplete", content=[])]}, "provider_output"),
])
def test_provider_terminal_failures_rollback(turn, tmp_path, monkeypatch, environment, changes, code):
    turn(remember_style="example-first")
    before = snapshot(tmp_path)
    async def fake_request(*_):
        return response(**changes)
    monkeypatch.setattr(provider, "_request", fake_request)
    result = turn(mode="live", remember_style="step-by-step")
    assert result["failure_code"] == code
    assert result["answer"] is None and snapshot(tmp_path) == before
    assert "private" not in json.dumps(result)


def test_provider_exception_sanitized_no_retry_no_fallback(turn, tmp_path, monkeypatch, environment):
    turn(remember_style="example-first")
    before = snapshot(tmp_path)
    calls = []
    async def fake_request(*_):
        calls.append(1)
        raise RuntimeError("secret API key and private data")
    monkeypatch.setattr(provider, "_request", fake_request)
    result = turn(mode="live", remember_style="step-by-step")
    assert result["failure_code"] == "provider_failure" and calls == [1]
    assert "secret" not in json.dumps(result)
    assert snapshot(tmp_path) == before


def test_total_deadline_cancels_request_and_rolls_back(turn, tmp_path, monkeypatch, environment):
    turn(remember_style="example-first")
    before = snapshot(tmp_path)
    cancelled = []
    async def fake_request(*_):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.append(True)
    monkeypatch.setattr(provider, "_request", fake_request)
    monkeypatch.setattr(provider, "DEADLINE_SECONDS", 0.01)
    result = turn(mode="live", remember_style="step-by-step")
    assert result["failure_code"] == "provider_timeout"
    assert cancelled == [True] and snapshot(tmp_path) == before


def test_provider_interrupt_rolls_back(turn, tmp_path):
    turn(remember_style="example-first")
    before = snapshot(tmp_path)
    def interrupted(*_):
        raise KeyboardInterrupt
    result = turn(mode="live", remember_style="step-by-step", selector=interrupted)
    assert result["status"] == "cancelled" and snapshot(tmp_path) == before


@pytest.mark.parametrize("variable,value", [("OPENAI_API_KEY", ""), ("OPENAI_API_KEY", "bad\nvalue"),
    ("MEMORY_AGENT_MODEL", ""), ("MEMORY_AGENT_MODEL", "https://other"),
    ("OPENAI_CUSTOM_HEADERS", "Authorization: private-other-key")])
def test_bad_provider_configuration_never_calls_backend(turn, tmp_path, monkeypatch, environment, variable, value):
    monkeypatch.setenv(variable, value)
    async def forbidden(*_):
        pytest.fail("Provider configuration must fail before calling the backend")
    monkeypatch.setattr(provider, "_request", forbidden)
    result = turn(mode="live", remember_style="example-first")
    assert result["failure_code"] == "provider_config"
    with sqlite3.connect(tmp_path / "private-data/demo.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM episodes").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM preferences").fetchone() == (0,)


def test_existing_child_logger_does_not_expose_context(turn, monkeypatch, environment):
    captured = io.StringIO()
    handler = logging.StreamHandler(captured)
    logger = logging.getLogger("openai._base_client")
    previous = logger.level
    previous_disable = logging.root.manager.disable
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    async def fake_request(*_):
        logger.debug("secret API key and private query")
        return response()
    monkeypatch.setattr(provider, "_request", fake_request)
    try:
        assert turn(mode="live")["status"] == "answered"
        assert captured.getvalue() == ""
        assert logging.root.manager.disable == previous_disable
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


def test_reasoning_metadata_is_not_used_as_answer():
    result = response()
    result.output.insert(0, NS(type="reasoning", summary="untrusted answer"))
    assert provider.parse_response(result) == ["faq-working-memory"]
