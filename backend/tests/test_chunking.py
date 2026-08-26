"""Chunking is deterministic and paragraph-aware (pure; no external deps)."""
from app.rag.chunk import chunk_text


def test_empty_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_single_chunk():
    assert chunk_text("Product-market fit is the only thing that matters.") == [
        "Product-market fit is the only thing that matters."
    ]


def test_large_text_splits_into_multiple():
    paras = "\n\n".join(f"Paragraph {i}. " + "word " * 120 for i in range(20))
    chunks = chunk_text(paras, target_chars=1000, overlap_chars=100)
    assert len(chunks) > 1
    assert all(c.strip() for c in chunks)


def test_deterministic():
    paras = "\n\n".join("growth loop " * 40 for _ in range(8))
    assert chunk_text(paras) == chunk_text(paras)


def test_oversized_paragraph_is_hard_split():
    giant = "x" * 5000
    chunks = chunk_text(giant, target_chars=1000, overlap_chars=100)
    assert len(chunks) >= 5
