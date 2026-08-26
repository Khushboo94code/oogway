"""Deterministic intent router (chat vs essay vs artifact). Kept rule-based so it
is fast, free, provider-independent, and unit-testable."""
from __future__ import annotations

from typing import Literal

Intent = Literal["chat", "essay", "artifact"]

_ESSAY_KW = (
    "essay", "ship 30", "ship30", "ship-30", "write a post", "blog post",
    "long-form", "long form", "1250 word", "1,250 word", "write me a piece",
    "turn this into a post", "atomic essay",
)
_ARTIFACT_KW = (
    "artifact", "html", "landing page", "one-pager", "one pager", "checklist",
    "render", "css", "web page", "webpage", "mockup", "mock up", "table of",
    "make a table", "diagram",
)


def route(message: str) -> Intent:
    m = message.lower().strip()
    if m.startswith("/essay"):
        return "essay"
    if m.startswith("/artifact"):
        return "artifact"
    if any(k in m for k in _ESSAY_KW):
        return "essay"
    if any(k in m for k in _ARTIFACT_KW):
        return "artifact"
    return "chat"
