"""Retrieval grounding logic (embeddings + similarity search are mocked, no DB)."""
import pytest

pytest.importorskip("psycopg")
pytest.importorskip("pydantic_settings")

import app.rag.retrieve as R  # noqa: E402

_ROW = {
    "id": "11111111-1111-1111-1111-111111111111",
    "episode_id": "e1",
    "episode_title": "Finding PMF",
    "guest": "A Guest",
    "source_url": "https://youtu.be/x",
    "publish_date": None,
    "chunk_index": 0,
    "chunk_text": "product-market fit is the only thing that matters",
}


async def test_grounded_true(monkeypatch):
    async def fake_embed(_):
        return [0.1] * 768

    async def fake_search(_emb, _k):
        return [{**_ROW, "score": 0.88}]

    monkeypatch.setattr(R, "embed_text", fake_embed)
    monkeypatch.setattr(R, "similarity_search", fake_search)

    res = await R.retrieve_context("pmf", min_score=0.25)
    assert res["grounded"] is True
    assert res["citations"][0]["episode_title"] == "Finding PMF"
    assert "[1]" in res["context_text"]


async def test_not_grounded_below_threshold(monkeypatch):
    async def fake_embed(_):
        return [0.1] * 768

    async def fake_search(_emb, _k):
        return [{**_ROW, "score": 0.05}]

    monkeypatch.setattr(R, "embed_text", fake_embed)
    monkeypatch.setattr(R, "similarity_search", fake_search)

    res = await R.retrieve_context("obscure", min_score=0.25)
    assert res["grounded"] is False


async def test_embeddings_unavailable(monkeypatch):
    async def boom(_):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(R, "embed_text", boom)
    res = await R.retrieve_context("q")
    assert res["grounded"] is False
    assert res["error"] == "embeddings_unavailable"
