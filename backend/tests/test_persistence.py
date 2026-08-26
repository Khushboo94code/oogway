"""Persistence + session-context isolation against the real DB.
Runs in Docker (`make test`); skipped if Postgres is not reachable."""
import os

import pytest

pytest.importorskip("psycopg")
import psycopg  # noqa: E402

_DSN = os.environ.get("DATABASE_URL", "postgresql://lenny:lenny@localhost:5432/lenny")


def _db_ok() -> bool:
    try:
        with psycopg.connect(_DSN, connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ok(), reason="Postgres not reachable")

from app import repository as repo  # noqa: E402
from app.db import init_db  # noqa: E402


async def test_sessions_keep_independent_context():
    await init_db()
    s1 = await repo.create_session("A")
    s2 = await repo.create_session("B")
    await repo.add_message(s1["id"], "user", "one")
    await repo.add_message(s2["id"], "user", "two")
    m1 = await repo.list_messages(s1["id"])
    m2 = await repo.list_messages(s2["id"])
    assert [m["content"] for m in m1] == ["one"]
    assert [m["content"] for m in m2] == ["two"]


async def test_citations_and_artifact_persist():
    await init_db()
    s = await repo.create_session("C")
    cits = [{"episode_title": "T", "guest": "G", "source_url": "u", "score": 0.9}]
    await repo.add_message(
        s["id"], "assistant", "answer",
        citations=cits, artifact={"type": "markdown", "title": "x", "content": "y"},
    )
    msgs = await repo.list_messages(s["id"])
    assert msgs[0]["citations"][0]["episode_title"] == "T"
    assert msgs[0]["artifact"]["type"] == "markdown"
