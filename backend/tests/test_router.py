"""Intent routing (chat vs essay vs artifact) — deterministic and testable."""
import pytest

from app.agent.router import route


@pytest.mark.parametrize(
    "message,expected",
    [
        ("What did guests say about product-market fit?", "chat"),
        ("How do I improve activation?", "chat"),
        ("Write a Ship 30 essay on onboarding", "essay"),
        ("/essay retention loops", "essay"),
        ("Turn this into a blog post", "essay"),
        ("Make an HTML landing page for a growth tool", "artifact"),
        ("/artifact a checklist of launch steps", "artifact"),
        ("Give me a one-pager on B2B growth", "artifact"),
    ],
)
def test_route(message, expected):
    assert route(message) == expected


def test_slash_commands_take_priority():
    assert route("/essay make an html page") == "essay"
    assert route("/artifact write a blog post") == "artifact"
