"""Retrieval: embed the query, cosine top-k over pgvector, then format grounded
context + citations. `grounded` is False when nothing clears the score floor, so
the agent can honestly say the transcripts don't cover the question."""
from __future__ import annotations

import logging
from typing import Any

from ..config import get_settings
from ..repository import similarity_search
from .embed import embed_text

log = logging.getLogger(__name__)

_MAX_CHUNK_CHARS = 1400  # bound per-chunk text injected into the prompt


def _citation(row: dict) -> dict:
    pub = row.get("publish_date")
    return {
        "episode_title": row["episode_title"],
        "guest": row.get("guest"),
        "source_url": row.get("source_url"),
        "publish_date": pub.isoformat() if hasattr(pub, "isoformat") else pub,
        "chunk_id": str(row["id"]),
        "score": round(float(row["score"]), 4),
    }


async def retrieve_context(
    query: str, top_k: int | None = None, min_score: float | None = None
) -> dict[str, Any]:
    s = get_settings()
    top_k = top_k or s.retrieval_top_k
    min_score = s.retrieval_min_score if min_score is None else min_score

    try:
        embedding = await embed_text(query)
    except Exception as exc:  # noqa: BLE001 — embeddings unavailable (ollama down)
        log.warning("Embedding failed during retrieval: %s", exc)
        return {"context_text": "", "citations": [], "chunks": [], "grounded": False,
                "top_score": 0.0, "error": "embeddings_unavailable"}

    rows = await similarity_search(embedding, top_k)
    top_score = float(rows[0]["score"]) if rows else 0.0
    grounded = top_score >= min_score

    # Build enumerated context blocks for the model to cite as [1], [2], ...
    blocks = []
    for i, r in enumerate(rows, start=1):
        text = r["chunk_text"][:_MAX_CHUNK_CHARS]
        header = f"[{i}] {r.get('guest') or 'Unknown'} — {r['episode_title']}"
        blocks.append(f"{header}\n{text}")
    context_text = "\n\n".join(blocks)

    # De-duplicate citations by episode, keep the best-scoring chunk per episode.
    best: dict[str, dict] = {}
    for r in rows:
        c = _citation(r)
        key = r["episode_id"]
        if key not in best or (c["score"] or 0) > (best[key]["score"] or 0):
            best[key] = c
    citations = sorted(best.values(), key=lambda c: c["score"] or 0, reverse=True)

    return {
        "context_text": context_text,
        "citations": citations,
        "chunks": rows,
        "grounded": grounded,
        "top_score": top_score,
    }
