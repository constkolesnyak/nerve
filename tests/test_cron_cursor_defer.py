"""Deferred consumer-cursor commit for cron sessions (email-loss safety).

The inbox-processor cron polls sources and advances the consumer cursor to
mark messages "read". If the cursor advanced immediately at poll time, a
mid-run auth failure (503 auth_unavailable) would leave messages marked read
but never notified -> silent email loss.

Fix under test: cron poll handlers BUFFER the cursor advance on the engine;
the cron run methods commit the buffer only on a clean run and discard it on
failure (leaving messages unread so the next run reprocesses them). User
(non-cron) sessions still commit inline.
"""

from __future__ import annotations

import pytest

from nerve.agent.engine import AgentEngine
from nerve.agent.tools.handlers.sources import (
    poll_all_sources_handler,
    poll_source_handler,
)
from nerve.agent.tools.registry import ToolContext
from nerve.sources.models import SourceRecord


def _make_engine(db) -> AgentEngine:
    """A bare engine exposing just the cursor-buffer surface (no full init)."""
    engine = AgentEngine.__new__(AgentEngine)
    engine._cursor_buffers = {}
    engine.db = db
    return engine


def _rec(rid: str, content: str) -> SourceRecord:
    return SourceRecord(
        id=rid,
        source="github",
        record_type="github_notification",
        summary=f"thread {rid}",
        content=content,
        timestamp="2026-01-01T00:00:00Z",
        metadata={"reason": "mention", "repo_name": "owner/repo"},
    )


# --------------------------------------------------------------------------- #
#  Engine buffer primitives                                                    #
# --------------------------------------------------------------------------- #

def test_cursor_is_deferred_only_for_cron_sessions():
    assert AgentEngine.cursor_is_deferred("cron:inbox-processor")
    assert AgentEngine.cursor_is_deferred("cron:foo:20260101-000000")
    assert not AgentEngine.cursor_is_deferred("web-abc")
    assert not AgentEngine.cursor_is_deferred("hook:gh:1")


def test_run_failed_sentinels():
    assert AgentEngine._run_failed("Agent error: 503 auth_unavailable")
    assert AgentEngine._run_failed(
        "The conversation contained an unprocessable image or document ..."
    )
    assert AgentEngine._run_failed("")
    assert AgentEngine._run_failed("   \n ")
    # A normal successful summary is not a failure.
    assert not AgentEngine._run_failed("Processed 3 emails, notified about 1.")


@pytest.mark.asyncio
async def test_commit_buffer_writes_highest_seq_per_source(db):
    engine = _make_engine(db)
    sid = "cron:inbox-processor"

    engine.buffer_cursor(sid, "inbox", "github", 5, ttl_days=2)
    engine.buffer_cursor(sid, "inbox", "github", 12, ttl_days=2)  # higher wins
    engine.buffer_cursor(sid, "inbox", "gmail:x", 7, ttl_days=2)

    # Nothing persisted until commit.
    assert await db.get_consumer_cursor("inbox", "github") == 0
    assert await db.get_consumer_cursor("inbox", "gmail:x") == 0

    committed = await engine.commit_cursor_buffer(sid)
    assert committed == 2  # two distinct (consumer, source) cursors
    assert await db.get_consumer_cursor("inbox", "github") == 12
    assert await db.get_consumer_cursor("inbox", "gmail:x") == 7

    # Buffer is drained after commit.
    assert await engine.commit_cursor_buffer(sid) == 0


@pytest.mark.asyncio
async def test_discard_buffer_leaves_cursor_untouched(db):
    engine = _make_engine(db)
    sid = "cron:inbox-processor"

    engine.buffer_cursor(sid, "inbox", "github", 9, ttl_days=2)
    dropped = engine.discard_cursor_buffer(sid)
    assert dropped == 1
    assert await db.get_consumer_cursor("inbox", "github") == 0
    # Idempotent.
    assert engine.discard_cursor_buffer(sid) == 0


@pytest.mark.asyncio
async def test_settle_commits_on_success_discards_on_failure(db):
    engine = _make_engine(db)

    ok = "cron:inbox-processor"
    engine.buffer_cursor(ok, "inbox", "github", 4, ttl_days=2)
    await engine._settle_cursor_buffer(ok, "Notified about 1 email.")
    assert await db.get_consumer_cursor("inbox", "github") == 4

    bad = "cron:inbox-processor"
    engine.buffer_cursor(bad, "inbox", "gmail:y", 8, ttl_days=2)
    await engine._settle_cursor_buffer(bad, "Agent error: 503 auth_unavailable")
    assert await db.get_consumer_cursor("inbox", "gmail:y") == 0


# --------------------------------------------------------------------------- #
#  Poll handlers honour the defer/commit split                                 #
# --------------------------------------------------------------------------- #

async def _init_cursor(db, consumer: str, source: str) -> None:
    """Park the cursor at 0 on an empty inbox (get lazily inits to max rowid)."""
    assert await db.get_consumer_cursor(consumer, source) == 0


@pytest.mark.asyncio
async def test_poll_all_sources_defers_cursor_for_cron_session(db):
    engine = _make_engine(db)
    await _init_cursor(db, "inbox", "github")
    await db.insert_source_messages([_rec("t1", "a"), _rec("t2", "b")], source="github")

    ctx = ToolContext(session_id="cron:inbox-processor", db=db, engine=engine)
    res = await poll_all_sources_handler(ctx, {"consumer": "inbox"})
    assert not res.is_error

    # Cursor NOT advanced yet — it lives in the engine buffer.
    assert await db.get_consumer_cursor("inbox", "github") == 0
    assert engine._cursor_buffers["cron:inbox-processor"]

    # On a clean run the buffer commits and the messages are marked read.
    await engine._settle_cursor_buffer("cron:inbox-processor", "done, notified")
    parked = await db.get_consumer_cursor("inbox", "github")
    assert parked > 0
    again = await db.read_source_messages_by_rowid("github", after_seq=parked, limit=50)
    assert again == []


@pytest.mark.asyncio
async def test_poll_all_sources_reprocesses_after_failed_run(db):
    engine = _make_engine(db)
    await _init_cursor(db, "inbox", "github")
    await db.insert_source_messages([_rec("t1", "a")], source="github")

    ctx = ToolContext(session_id="cron:inbox-processor", db=db, engine=engine)
    await poll_all_sources_handler(ctx, {"consumer": "inbox"})

    # Run fails (tokens ran out mid-run) -> discard -> cursor stays at 0.
    await engine._settle_cursor_buffer(
        "cron:inbox-processor", "Agent error: 503 auth_unavailable",
    )
    assert await db.get_consumer_cursor("inbox", "github") == 0

    # Next run sees the SAME message again (no loss).
    rows = await db.read_source_messages_by_rowid("github", after_seq=0, limit=50)
    assert {r["id"] for r in rows} == {"t1"}


@pytest.mark.asyncio
async def test_poll_source_commits_inline_for_user_session(db):
    # User sessions have no run boundary to flush a buffer -> commit inline.
    engine = _make_engine(db)
    await _init_cursor(db, "inbox", "github")
    await db.insert_source_messages([_rec("t1", "a")], source="github")

    ctx = ToolContext(session_id="web-123", db=db, engine=engine)
    res = await poll_source_handler(
        ctx, {"source": "github", "consumer": "inbox"},
    )
    assert not res.is_error
    # Committed immediately; nothing buffered.
    assert await db.get_consumer_cursor("inbox", "github") > 0
    assert "web-123" not in engine._cursor_buffers


@pytest.mark.asyncio
async def test_poll_source_without_engine_commits_inline(db):
    # No engine on the context (e.g. external MCP) -> inline commit, no crash.
    await _init_cursor(db, "inbox", "github")
    await db.insert_source_messages([_rec("t1", "a")], source="github")
    ctx = ToolContext(session_id="cron:inbox-processor", db=db, engine=None)
    res = await poll_source_handler(
        ctx, {"source": "github", "consumer": "inbox"},
    )
    assert not res.is_error
    assert await db.get_consumer_cursor("inbox", "github") > 0
