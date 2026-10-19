import json

import pytest


@pytest.fixture(autouse=True)
def no_ambient_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)


@pytest.fixture
def document():
    return {"id": "policy", "title": "Subscription policy", "revision": "r1",
            "product": "atlasdesk", "version": "2.0", "audience": "public",
            "effective_from": "2026-10-01", "effective_until": None, "reviewed_at": "2026-10-10",
            "text": "Cancel your subscription in Billing."}


def encoded(documents):
    return json.dumps({"schema_version": 1, "documents": documents}).encode()
