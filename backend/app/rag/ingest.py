"""Ingestion: clone Lenny transcripts → parse frontmatter → chunk → embed → pgvector.

Run once (idempotent; re-running refreshes the index):
    python -m app.rag.ingest            # uses INGEST_MAX_EPISODES from env
    python -m app.rag.ingest --max 0    # ingest ALL episodes
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import subprocess
from pathlib import Path

import frontmatter

from ..config import get_settings
from ..db import get_pool, init_db
from ..logging_config import configure_logging
from ..repository import insert_chunks
from .chunk import chunk_text
from .embed import embed_texts

log = logging.getLogger(__name__)

DATA_DIR = Path("data")


def clone_or_update(repo_url: str) -> Path:
    dest = DATA_DIR / "lennys-podcast-transcripts"
    DATA_DIR.mkdir(exist_ok=True)
    if dest.exists():
        log.info("Transcripts already present at %s (pulling latest, best-effort)", dest)
        subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"], check=False)
    else:
        log.info("Cloning %s -> %s", repo_url, dest)
        subprocess.run(["git", "clone", "--depth", "1", repo_url, str(dest)], check=True)
    return dest


def find_transcripts(root: Path) -> list[Path]:
    files = sorted(root.glob("episodes/*/transcript.md"))
    if not files:  # fallback: any markdown that isn't a readme/index
        files = sorted(
            p for p in root.rglob("*.md")
            if p.name.lower() not in {"readme.md", "index.md"}
        )
    return files


def _meta(md: dict, path: Path) -> dict:
    slug = path.parent.name
    return {
        "episode_id": md.get("video_id") or slug,
        "episode_title": (md.get("title") or slug).strip(),
        "guest": md.get("guest"),
        "source_url": md.get("youtube_url") or md.get("url"),
        "publish_date": md.get("publish_date") or md.get("date"),
    }


async def _reset_chunks() -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("TRUNCATE transcript_chunks")
        await conn.commit()


async def ingest(repo_url: str, max_episodes: int, reset: bool) -> None:
    await init_db()
    if reset:
        log.info("Resetting transcript_chunks (refresh)")
        await _reset_chunks()

    root = clone_or_update(repo_url)
    files = find_transcripts(root)
    if max_episodes and max_episodes > 0:
        files = files[:max_episodes]
    log.info("Ingesting %d episode(s)", len(files))

    total_chunks = 0
    for i, path in enumerate(files, start=1):
        try:
            post = frontmatter.load(path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Skipping %s (frontmatter error: %s)", path, exc)
            continue

        meta = _meta(post.metadata, path)
        chunks = chunk_text(post.content or "")
        if not chunks:
            continue

        embeddings = await embed_texts(chunks)
        rows = [
            {**meta, "chunk_index": idx, "chunk_text": c, "embedding": emb}
            for idx, (c, emb) in enumerate(zip(chunks, embeddings))
        ]
        total_chunks += await insert_chunks(rows)
        log.info("[%d/%d] %s — %d chunks", i, len(files), meta["episode_title"], len(rows))

    log.info("Done. Ingested %d chunks across %d episodes.", total_chunks, len(files))


def main() -> None:
    s = get_settings()
    configure_logging(s.log_level)
    ap = argparse.ArgumentParser(description="Ingest Lenny transcripts into pgvector")
    ap.add_argument("--repo", default=s.transcripts_repo)
    ap.add_argument("--max", type=int, default=s.ingest_max_episodes, help="0 = all")
    ap.add_argument("--no-reset", action="store_true", help="append instead of refreshing")
    args = ap.parse_args()
    asyncio.run(ingest(args.repo, args.max, reset=not args.no_reset))


if __name__ == "__main__":
    main()
