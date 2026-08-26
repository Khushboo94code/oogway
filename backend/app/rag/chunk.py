"""Paragraph-aware chunking. We pack paragraphs up to a character budget
(~char/4 ≈ tokens) with a small overlap so retrieval keeps local context."""
from __future__ import annotations

import re

_WS = re.compile(r"[ \t]+")


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # collapse runs of spaces/tabs but keep paragraph breaks
    lines = [_WS.sub(" ", ln).strip() for ln in text.split("\n")]
    return "\n".join(lines)


def chunk_text(text: str, target_chars: int = 3500, overlap_chars: int = 500) -> list[str]:
    """Return a list of chunk strings. ~3500 chars ≈ ~875 tokens; ~500 overlap."""
    text = _normalize(text).strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""

    for para in paragraphs:
        # A single huge paragraph: hard-split it.
        if len(para) > target_chars:
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(para), target_chars - overlap_chars):
                chunks.append(para[i : i + target_chars])
            continue

        if buf and len(buf) + len(para) + 2 > target_chars:
            chunks.append(buf)
            tail = buf[-overlap_chars:] if overlap_chars else ""
            buf = (tail + "\n\n" + para).strip()
        else:
            buf = (buf + "\n\n" + para).strip() if buf else para

    if buf:
        chunks.append(buf)

    return [c.strip() for c in chunks if c.strip()]
