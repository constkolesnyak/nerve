"""Tests for whitespace normalization in notification text.

Failure mode this pins down: a cron session ends its ``body`` with a
trailing ``"\\n\\n"`` (models do this constantly), the Telegram renderer
appends the session label with a fixed ``"\\n\\n"``, and the reader sees
three blank lines hanging under the message before "Session: ...".

The fix is structural rather than a prompt rule — the write path strips
title/body, and the renderer strips again so rows persisted before the
fix don't render ragged either.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from nerve.config import NerveConfig, NotificationsConfig
from nerve.db import Database
from nerve.notifications.service import NotificationService


@pytest.fixture
def fake_config(tmp_path) -> NerveConfig:
    cfg = NerveConfig()
    cfg.workspace = tmp_path
    cfg.notifications = NotificationsConfig(
        channels=["web"],
        telegram_chat_id=None,
        default_expiry_hours=48,
        priority_prefixes={"high": "", "urgent": ""},
    )
    return cfg


@pytest.fixture
def fake_engine() -> MagicMock:
    engine = MagicMock()
    engine.sessions = MagicMock()
    engine.sessions.is_running.return_value = False
    engine.router = MagicMock()
    engine.router.get_channel.return_value = None
    engine.run = AsyncMock()
    return engine


@pytest.fixture
def patch_broadcaster(monkeypatch) -> list:
    captured: list = []

    class _FakeBroadcaster:
        async def broadcast(self, channel: str, message: dict) -> None:
            captured.append((channel, message))

    from nerve.agent import streaming
    monkeypatch.setattr(streaming, "broadcaster", _FakeBroadcaster())
    return captured


@pytest_asyncio.fixture
async def svc(db: Database, fake_config, fake_engine, patch_broadcaster):
    await db.create_session("s1")
    service = NotificationService(fake_config, db, fake_engine)
    service._fanout = AsyncMock()
    return service


# The shape a cron job actually emitted (skill-extractor, 2026-08-15):
# two bullet lines and a trailing blank line the model tacked on.
_RAGGED_BODY = (
    "🍁 Two new skills\n"
    "🌿 first one\n"
    "🌿 second one\n\n"
)


@pytest.mark.asyncio
class TestWritePathStrips:
    async def test_notify_body_persisted_without_trailing_newlines(self, svc, db):
        nid = await svc.send_notification(
            session_id="s1", title="", body=_RAGGED_BODY,
        )
        row = await db.get_notification(nid)
        assert row["body"] == _RAGGED_BODY.strip()
        assert not row["body"].endswith("\n")
        # Interior structure must survive — only the edges are trimmed.
        assert row["body"].count("\n") == 2

    async def test_notify_title_stripped(self, svc, db):
        nid = await svc.send_notification(
            session_id="s1", title="  Heads up \n", body="x",
        )
        row = await db.get_notification(nid)
        assert row["title"] == "Heads up"

    async def test_leading_newlines_also_trimmed(self, svc, db):
        nid = await svc.send_notification(
            session_id="s1", title="", body="\n\n🍁 late start",
        )
        row = await db.get_notification(nid)
        assert row["body"] == "🍁 late start"

    async def test_question_body_stripped(self, svc, db):
        res = await svc.ask_question(
            session_id="s1", title="Pick one", body=_RAGGED_BODY,
            options=["a", "b"],
        )
        row = await db.get_notification(res["notification_id"])
        assert row["body"] == _RAGGED_BODY.strip()

    async def test_approval_body_stripped(self, svc, db):
        res = await svc.propose_action(
            session_id="s1", target_kind="mechanical-action",
            target_id="t-1", title="Approve?", body=_RAGGED_BODY,
        )
        row = await db.get_notification(res["notification_id"])
        assert row["body"] == _RAGGED_BODY.strip()

    async def test_body_of_only_whitespace_becomes_empty(self, svc, db):
        nid = await svc.send_notification(
            session_id="s1", title="Title only", body="\n\n  \n",
        )
        row = await db.get_notification(nid)
        assert row["body"] == ""


class TestTelegramRenderGap:
    """The renderer is the last line of defense for pre-fix rows."""

    def test_exactly_one_blank_line_before_session_label(
        self, fake_config, db, fake_engine,
    ):
        svc = NotificationService(fake_config, db, fake_engine)
        text = svc._build_telegram_text(
            "cron:skill-extractor:20260815-220000", "", _RAGGED_BODY, "normal",
        )
        assert text == f"{_RAGGED_BODY.strip()}\n\nSession: " \
                       "cron:skill-extractor:20260815-220000"
        assert "\n\n\n" not in text

    def test_no_session_label_leaves_no_trailing_newlines(
        self, fake_config, db, fake_engine,
    ):
        svc = NotificationService(fake_config, db, fake_engine)
        svc._hide_session_label = ["cron"]
        text = svc._build_telegram_text(
            "cron:x:1", "", _RAGGED_BODY, "normal",
        )
        assert text == _RAGGED_BODY.strip()

    def test_title_and_body_keep_single_blank_line_between(
        self, fake_config, db, fake_engine,
    ):
        svc = NotificationService(fake_config, db, fake_engine)
        svc._hide_session_label = ["s1"]
        text = svc._build_telegram_text("s1", "Heads up", "\nbody\n\n", "normal")
        assert text == "Heads up\n\nbody"

    def test_empty_body_renders_title_only(
        self, fake_config, db, fake_engine,
    ):
        svc = NotificationService(fake_config, db, fake_engine)
        svc._hide_session_label = ["s1"]
        text = svc._build_telegram_text("s1", "Heads up", "\n  \n", "normal")
        assert text == "Heads up"
