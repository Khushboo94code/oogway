"""Server-side HTML sanitization — DEFENSE IN DEPTH only.

The real isolation boundary is the frontend: generated HTML renders inside a
`<iframe sandbox>` (no same-origin, no top navigation) with a strict Content-
Security-Policy that blocks scripts and all network/external resources. This
function is a second layer that strips the obvious dangerous constructs and
REPORTS what it removed, so the viewer can show users exactly what was blocked."""
from __future__ import annotations

import re

_SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_SCRIPT_OPEN = re.compile(r"</?script\b[^>]*>", re.IGNORECASE)
_ON_ATTR = re.compile(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_JS_URI = re.compile(r"(href|src)\s*=\s*(\"|')\s*javascript:[^\"']*(\"|')", re.IGNORECASE)
_IFRAME = re.compile(r"</?iframe\b[^>]*>", re.IGNORECASE)
_EXTERNAL = re.compile(r"(src|href)\s*=\s*(\"|')\s*(https?:)?//", re.IGNORECASE)

# What the viewer permits/blocks — surfaced in the UI explainer.
POLICY = {
    "permits": [
        "Inline HTML structure and inline CSS / <style>",
        "Inline SVG and CSS-only visuals",
    ],
    "blocks": [
        "<script> and all JavaScript execution (iframe sandbox has no allow-scripts)",
        "Inline event handlers (onclick, onload, …)",
        "javascript: URIs",
        "External/remote resources — scripts, styles, fonts, images (blocked by CSP)",
        "Network requests, same-origin access, top-level navigation, form posts",
    ],
}


def sanitize_html(html: str) -> tuple[str, dict]:
    """Return (clean_html, report). report.removed lists categories that were stripped."""
    removed: list[str] = []

    if _SCRIPT_BLOCK.search(html) or _SCRIPT_OPEN.search(html):
        removed.append("<script> tags")
    html = _SCRIPT_BLOCK.sub("", html)
    html = _SCRIPT_OPEN.sub("", html)

    if _ON_ATTR.search(html):
        removed.append("inline event handlers (on*)")
    html = _ON_ATTR.sub("", html)

    if _JS_URI.search(html):
        removed.append("javascript: URIs")
    html = _JS_URI.sub(r'\1="#"', html)

    if _IFRAME.search(html):
        removed.append("nested <iframe>")
    html = _IFRAME.sub("", html)

    flagged: list[str] = []
    if _EXTERNAL.search(html):
        # Not stripped (CSP blocks them at render time) but flagged for transparency.
        flagged.append("external resource references (blocked by CSP at render)")

    return html, {"removed": removed, "flagged": flagged, "policy": POLICY}
