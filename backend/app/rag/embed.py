"""Embeddings. Fixed to one model (nomic-embed-text via Ollama) so the vector
index stays provider-independent — Ollama runs in both cloud and local modes."""
from __future__ import annotations

import asyncio
import logging

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)


async def embed_text(text: str) -> list[float]:
    s = get_settings()
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{s.ollama_url}/api/embeddings",
            json={"model": s.embed_model, "prompt": text},
        )
        r.raise_for_status()
        data = r.json()
    emb = data.get("embedding")
    if not emb:
        raise RuntimeError(f"Empty embedding from Ollama for model {s.embed_model}")
    return emb


async def embed_texts(texts: list[str], concurrency: int = 4) -> list[list[float]]:
    """Embed many texts with bounded concurrency (order preserved)."""
    sem = asyncio.Semaphore(concurrency)

    async def _one(t: str) -> list[float]:
        async with sem:
            return await embed_text(t)

    return await asyncio.gather(*[_one(t) for t in texts])
