"""System prompts + message assembly for grounded answers."""
from __future__ import annotations

GROUNDED_SYSTEM = """You are the Lenny Growth Assistant — an expert product and growth advisor.
Your ONLY knowledge source is the numbered CONTEXT excerpts from Lenny's Podcast transcripts
provided in each turn.

Rules:
- Answer using ONLY the provided CONTEXT. Do not use outside knowledge or invent facts.
- Cite sources inline using the bracketed numbers from the context, e.g. [1], [2].
- If the CONTEXT does not contain enough to answer, say so plainly: state that Lenny's
  transcripts don't cover it and suggest a related question. Never fabricate.
- Be concrete and practical: name the frameworks, tactics, and examples the guests describe.
- Respect earlier conversation turns for follow-up questions.
"""


def build_messages(history: list[dict], context_text: str, question: str) -> list[dict]:
    ctx = context_text.strip() or "(no relevant excerpts were found)"
    messages: list[dict] = [{"role": "system", "content": GROUNDED_SYSTEM}]
    # prior turns for follow-up continuity (already role/content dicts)
    messages.extend(history)
    messages.append(
        {
            "role": "user",
            "content": (
                f"CONTEXT (numbered excerpts from Lenny's transcripts):\n{ctx}\n\n"
                f"QUESTION: {question}\n\n"
                "Answer using only the CONTEXT above and cite the excerpt numbers like [1]. "
                "If the context is insufficient, say the transcripts don't cover it."
            ),
        }
    )
    return messages
