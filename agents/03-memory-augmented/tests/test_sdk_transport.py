import json

import pytest

from memory_agent import provider


openai = pytest.importorskip("openai", reason="Install --extra live to verify the real SDK against a mock transport")
httpx2 = pytest.importorskip("httpx2")


@pytest.mark.parametrize("status", [200, 302, 429, 500])
def test_real_sdk_uses_official_endpoint_isolated_transport_and_one_call(turn, monkeypatch, status):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-key")
    monkeypatch.setenv("MEMORY_AGENT_MODEL", "synthetic-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://untrusted.invalid/v1")
    monkeypatch.setenv("OPENAI_ORG_ID", "private-org")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "private-project")
    monkeypatch.setenv("OPENAI_ADMIN_KEY", "private-admin")
    monkeypatch.setenv("HTTPS_PROXY", "https://untrusted.invalid")
    monkeypatch.setenv("ALL_PROXY", "https://untrusted.invalid")
    monkeypatch.delenv("OPENAI_CUSTOM_HEADERS", raising=False)
    requests, settings, clients = [], [], []
    def handle(request):
        requests.append(request)
        if status != 200:
            return httpx2.Response(status, headers={"location": "https://untrusted.invalid/steal"},
                                   json={"error": {"message": "private error", "type": "test"}})
        return httpx2.Response(200, json={
            "id": "resp_synthetic", "object": "response", "created_at": 1,
            "model": "synthetic-model", "status": "completed", "error": None, "incomplete_details": None,
            "output": [{"id": "msg_synthetic", "type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": '{"faq_ids":["faq-working-memory"]}', "annotations": []}]}],
        })
    original_transport = openai.DefaultAsyncHttpx2Client
    original_client = openai.AsyncOpenAI
    def transport(**kwargs):
        settings.append(kwargs)
        return original_transport(**kwargs, transport=httpx2.MockTransport(handle))
    def client(**kwargs):
        clients.append(kwargs)
        return original_client(**kwargs)
    monkeypatch.setattr(openai, "DefaultAsyncHttpx2Client", transport)
    monkeypatch.setattr(openai, "AsyncOpenAI", client)
    result = turn(mode="live")
    assert result["status"] == ("answered" if status == 200 else "failed")
    assert len(requests) == 1
    assert str(requests[0].url) == "https://api.openai.com/v1/responses"
    assert settings == [{"trust_env": False, "follow_redirects": False, "timeout": 20}]
    assert clients[0]["max_retries"] == 0 and clients[0]["timeout"] == 20
    assert clients[0]["admin_api_key"] == clients[0]["organization"] == clients[0]["project"] == ""
    headers = dict(requests[0].headers)
    assert headers["authorization"] == "Bearer synthetic-key"
    assert "private-org" not in str(headers) and "private-project" not in str(headers)
    body = json.loads(requests[0].content)
    assert body["tool_choice"] == "none" and body["tools"] == []
    assert body["store"] is False and body["background"] is False
    assert body["max_output_tokens"] == 512
    assert body["text"]["format"]["strict"] is True
    assert "private error" not in json.dumps(result)
