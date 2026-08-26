"""Artifact JSON parsing is robust to fences, prose, and malformed output (pure)."""
from app.agent.skills import parse_artifact


def test_plain_json():
    a = parse_artifact('{"type":"html","title":"T","content":"<p>hi</p>"}')
    assert a["type"] == "html"
    assert a["title"] == "T"
    assert "hi" in a["content"]


def test_fenced_json():
    raw = '```json\n{"type":"markdown","title":"M","content":"# Heading"}\n```'
    a = parse_artifact(raw)
    assert a["type"] == "markdown"
    assert a["content"] == "# Heading"


def test_json_with_prose_around_it():
    raw = 'Here is your artifact:\n{"type":"markdown","title":"X","content":"body"}\nDone.'
    a = parse_artifact(raw)
    assert a["title"] == "X"


def test_invalid_type_coerced_to_markdown():
    a = parse_artifact('{"type":"weird","title":"x","content":"y"}')
    assert a["type"] == "markdown"


def test_fallback_when_not_json():
    a = parse_artifact("just some plain text answer")
    assert a["type"] == "markdown"
    assert "just some plain text" in a["content"]
