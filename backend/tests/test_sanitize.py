"""HTML sanitizer strips dangerous constructs and reports them (pure)."""
from app.security.sanitize import POLICY, sanitize_html


def test_strips_script_tags():
    clean, report = sanitize_html("<div>ok</div><script>alert(1)</script>")
    assert "<script" not in clean.lower()
    assert "alert(1)" not in clean
    assert "<script> tags" in report["removed"]


def test_strips_event_handlers():
    clean, report = sanitize_html('<button onclick="steal()">go</button>')
    assert "onclick" not in clean.lower()
    assert any("event handlers" in r for r in report["removed"])


def test_neutralizes_javascript_uri():
    clean, report = sanitize_html('<a href="javascript:alert(1)">x</a>')
    assert "javascript:" not in clean.lower()
    assert "javascript: URIs" in report["removed"]


def test_flags_external_resources():
    clean, report = sanitize_html('<img src="https://evil.example.com/pixel.png">')
    assert report["flagged"]  # reported (CSP blocks at render)


def test_policy_shape():
    assert "permits" in POLICY and "blocks" in POLICY
    assert any("script" in b.lower() for b in POLICY["blocks"])
