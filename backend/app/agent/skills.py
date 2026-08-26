"""Skill prompts + helpers for the two specialized outputs: a Ship-30-style essay
and a renderable artifact. The Ship-30 principles are encoded here (and mirrored in
.claude/skills/ship-30-essay/SKILL.md for the Agent SDK path)."""
from __future__ import annotations

import json
import re

# --- Ship 30 for 30 essay ---------------------------------------------------
SHIP30_SYSTEM = """You are a world-class writer trained in the Ship 30 for 30 method.
Turn the grounded material into a ~1,250-word long-form essay in GitHub-flavored Markdown.

Apply these Ship 30 principles:
- HOOK (first line): use ONE of the 6 proven openers — a strong declarative stance, a
  thought-provoking question, a controversial opinion, a specific moment in time, a vulnerable
  admission, or a weird/surprising insight. Open a curiosity gap; line 1's only job is to earn
  line 2 (the "1 Chip Rule").
- HEADLINE (# H1): clear, not clever. Signal WHO it's for, WHAT it's about, how it makes them
  FEEL, the PROMISE/outcome, and HOW MUCH (e.g. a number). Make a strong, specific promise you keep.
- STRUCTURE: stack sections on the 1/3/1 rhythm (a one-line opener, development, a one-line
  closer). Each major point is a BOLD ## subhead that tells the story on its own — a skimmer
  should get the value from the subheads alone.
- GOLDEN INTERSECTION: don't just state the answer — pair each answer with a short
  narrative/example drawn from the transcripts (answer + story).
- SKIMMABILITY: short paragraphs, generous whitespace, bullet lists, selective **bold**. Every
  sentence must advance the point — no filler.
- SPECIFICITY: concrete over vague, clear over clever.
- TAKEAWAY: end with ONE specific, useful takeaway the reader can act on today.

Grounding:
- Base every claim on the provided CONTEXT excerpts from Lenny's transcripts. Do not invent facts.
- Add inline citations [n] mapping to the context excerpts where you use them.
- Target ~1,250 words. Output Markdown only (no preamble)."""


def build_essay_messages(history: list[dict], context_text: str, request: str) -> list[dict]:
    ctx = context_text.strip() or "(no relevant excerpts were found)"
    return [
        {"role": "system", "content": SHIP30_SYSTEM},
        *history,
        {
            "role": "user",
            "content": (
                f"CONTEXT (numbered excerpts from Lenny's transcripts):\n{ctx}\n\n"
                f"WRITE AN ESSAY ABOUT: {request}\n\n"
                "Follow the Ship 30 principles. Ground every claim in the CONTEXT and cite [n]."
            ),
        },
    ]


# --- Artifact ---------------------------------------------------------------
# Small local models are unreliable at emitting strictly-valid JSON containing a big
# HTML string, so we ask for the RAW artifact (no JSON wrapper) and decide the type up
# front from the request. We still accept clean JSON (strong cloud models) and salvage
# JSON-ish blobs, so the viewer never shows raw braces.

ARTIFACT_SYSTEM = (
    "You generate ONE self-contained artifact for an in-app viewer, based on the conversation "
    "and the grounded CONTEXT. Ground factual claims in the CONTEXT. Keep it focused."
)

_HTML_RULES = (
    "Output a SINGLE self-contained HTML snippet and NOTHING else — no explanation, no JSON, no "
    "code fences. Use inline <style>/CSS only. Do NOT include <script>, event handlers (onclick, "
    "…), external/remote resources (remote scripts, styles, fonts, images), network requests, or "
    "off-site forms. Use inline SVG/CSS for visuals. Begin directly with the HTML."
)
_MD_RULES = (
    "Output clean, self-contained GitHub-flavored Markdown and NOTHING else — no explanation, no "
    "JSON, no surrounding code fences. Begin directly with the Markdown (start with a # heading)."
)

_HTML_HINTS = (
    "html", "web page", "webpage", "landing page", "landing", "website", "css", "styled",
    "one-pager", "one pager", "render", "visual", "chart", "dashboard", "card", "banner", "page",
)


def wants_html(request: str) -> bool:
    m = request.lower()
    if m.strip().startswith("/artifact"):
        parts = m.split(None, 1)
        m = parts[1] if len(parts) > 1 else ""
    return any(h in m for h in _HTML_HINTS)


def build_artifact_messages(
    history: list[dict], context_text: str, request: str, prefer_html: bool
) -> list[dict]:
    ctx = context_text.strip() or "(no relevant excerpts were found)"
    rules = _HTML_RULES if prefer_html else _MD_RULES
    return [
        {"role": "system", "content": f"{ARTIFACT_SYSTEM}\n\n{rules}"},
        *history,
        {
            "role": "user",
            "content": (
                f"CONTEXT (numbered excerpts from Lenny's transcripts):\n{ctx}\n\n"
                f"CREATE AN ARTIFACT FOR: {request}\n\n{rules}"
            ),
        },
    ]


_HTML_TAG = re.compile(
    r"<(?:!doctype|html|head|body|div|section|article|main|header|footer|nav|table|ul|ol|li|"
    r"h[1-6]|p|span|style|svg|img|a|button)\b",
    re.IGNORECASE,
)


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t)
    return t.strip()


def _looks_html(text: str) -> bool:
    return bool(_HTML_TAG.search(text))


def _derive_title(content: str, request: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", content, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()[:120] or "Artifact"
    m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if m:
        return m.group(1).strip()[:120]
    r = request.strip()
    if r.lower().startswith("/artifact"):
        r = r[len("/artifact"):].strip()
    return (r[:60] or "Artifact")


def _try_json_artifact(raw: str) -> dict | None:
    """Strict-ish JSON parse; returns None unless it's valid JSON with a 'content' key."""
    text = _strip_fences(raw)
    i, j = text.find("{"), text.rfind("}")
    if i == -1 or j == -1 or j <= i:
        return None
    try:
        obj = json.loads(text[i : j + 1])
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(obj, dict) or "content" not in obj:
        return None
    atype = obj.get("type", "markdown")
    if atype not in ("markdown", "html"):
        atype = "markdown"
    return {"type": atype, "title": (obj.get("title") or "Artifact")[:120], "content": obj.get("content", "")}


def _salvage_json(text: str) -> dict | None:
    """Recover content from a JSON-ish blob a weak model emitted (invalid/truncated JSON)."""
    cmatch = re.search(r'"content"\s*:\s*"(.*)$', text, re.DOTALL)
    if not cmatch:
        return None
    body = cmatch.group(1)
    body = re.sub(r'"\s*\}?\s*$', "", body).rstrip()  # drop trailing closing quote/brace
    body = (body.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
                .replace("\\/", "/").replace("\\\\", "\\"))
    tmatch = re.search(r'"type"\s*:\s*"(html|markdown)"', text, re.IGNORECASE)
    ttl = re.search(r'"title"\s*:\s*"(.*?)"', text, re.DOTALL)
    atype = tmatch.group(1).lower() if tmatch else ("html" if _looks_html(body) else "markdown")
    title = (ttl.group(1) if ttl else "Artifact")[:120]
    return {"type": atype, "title": title, "content": body}


def parse_artifact(raw: str, fallback_title: str = "Artifact") -> dict:
    """JSON-first parse with a Markdown fallback (kept for tests)."""
    return _try_json_artifact(raw) or {"type": "markdown", "title": fallback_title, "content": raw.strip()}


def finalize_artifact(raw: str, request: str, prefer_html: bool) -> dict:
    """Turn a model response into {type,title,content}, robust to weak-model output."""
    parsed = _try_json_artifact(raw)
    if parsed and parsed["content"].strip():
        return parsed
    content = _strip_fences(raw)
    if content.lstrip().startswith("{") and '"content"' in content:
        salvaged = _salvage_json(content)
        if salvaged and salvaged["content"].strip():
            return salvaged
    atype = "html" if (prefer_html or _looks_html(content)) else "markdown"
    return {"type": atype, "title": _derive_title(content, request), "content": content}
