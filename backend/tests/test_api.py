"""API integration tests. Persistence hits the real DB; the model + retrieval are
mocked so no live LLM is needed. Runs in Docker (`make test`); skipped if no DB."""
import os

import pytest

pytest.importorskip("litellm")
pytest.importorskip("psycopg")
import psycopg  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

_DSN = os.environ.get("DATABASE_URL", "postgresql://lenny:lenny@localhost:5432/lenny")


def _db_ok() -> bool:
    try:
        with psycopg.connect(_DSN, connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ok(), reason="Postgres not reachable")


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert "provider" in body and "checks" in body


def test_session_crud(client):
    r = client.post("/sessions", json={"title": "Test chat"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert any(s["id"] == sid for s in client.get("/sessions").json())
    assert client.get(f"/sessions/{sid}").status_code == 200
    assert client.get(f"/sessions/{sid}/messages").json() == []


def test_missing_session_returns_structured_404(client):
    r = client.get("/sessions/00000000-0000-0000-0000-000000000000/messages")
    assert r.status_code == 404
    assert r.json()["error"]["type"] == "http_error"


def test_chat_streams_and_persists(client, monkeypatch):
    import app.agent.orchestrator as orch

    async def fake_retrieve(_q, **_k):
        return {
            "context_text": "[1] Guest — Ep\nbody",
            "citations": [{"episode_title": "Ep", "guest": "Guest", "source_url": "u",
                           "publish_date": None, "chunk_id": "1", "score": 0.9}],
            "chunks": [],
            "grounded": True,
            "top_score": 0.9,
        }

    async def fake_stream(_messages, **_k):
        for tok in ["Hello", " world"]:
            yield tok

    monkeypatch.setattr(orch, "retrieve_context", fake_retrieve)
    monkeypatch.setattr(orch.gateway, "stream_chat", fake_stream)
    monkeypatch.setattr(orch.gateway, "active_labels", lambda: ("local", "test-model"))
    monkeypatch.setattr(orch.claude_sdk, "available", lambda: False)

    s = client.post("/sessions", json={"title": "New chat"}).json()
    r = client.post("/chat", json={"session_id": s["id"], "message": "hi"})
    assert r.status_code == 200
    body = r.text
    assert "event: token" in body and "Hello" in body
    assert "event: meta" in body and "event: done" in body

    msgs = client.get(f"/sessions/{s['id']}/messages").json()
    roles = [m["role"] for m in msgs]
    assert "user" in roles and "assistant" in roles
    assert any("Hello world" in m["content"] for m in msgs if m["role"] == "assistant")
