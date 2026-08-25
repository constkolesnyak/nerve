"""A dead session must not read as a wedged turn — and only the daemon recovers.

Two failures from 2026-08-25, one after the other:

1. A manual `nerve cron nerve-healthcheck` run finished, sent its report, and
   then never wrote its assistant row. Orphan recovery moved the session's
   *status* but the message log kept a user row with nothing after it, which
   is precisely the shape the external watchdog reads as "a turn has been
   wedged for two hours, holding an agent slot". It alerted twice and was one
   tick from restarting a daemon that was running everything on schedule.

2. That same recovery ran inside the CLI process of an unrelated
   `nerve cron inbox-processor`, and from there every session the daemon was
   running looked orphaned ("no live client *here*"), so it stopped — and
   memorized — a healthcheck that was still going in another process.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from nerve.agent.sessions import SessionManager
from nerve.db import Database


@pytest_asyncio.fixture
async def sm(db: Database):
    return SessionManager(db)


@pytest.mark.asyncio
class TestDanglingTurnClosure:
    async def test_closes_a_turn_left_open_by_a_dead_run(self, sm, db):
        await db.create_session("dead-run", status="active")
        await db.update_session_fields("dead-run", {"status": "active"})
        await db.add_message("dead-run", "user", "scheduled run — go")

        await sm.recover_orphaned_sessions()

        messages = await db.get_messages("dead-run")
        assert [m["role"] for m in messages] == ["user", "assistant"]
        assert messages[-1]["content"] == sm.INTERRUPTED_TURN_MARKER
        # The watchdog's probe — "user row with no assistant row after it" —
        # now finds nothing.
        assert messages[-1]["created_at"] >= messages[0]["created_at"]

    async def test_closes_the_turn_of_a_resumable_session_too(self, sm, db):
        await db.create_session("dead-resumable", status="active")
        await db.update_session_fields("dead-resumable", {
            "status": "active", "sdk_session_id": "sdk-abc",
        })
        await db.add_message("dead-resumable", "user", "go")

        await sm.recover_orphaned_sessions()

        messages = await db.get_messages("dead-resumable")
        assert messages[-1]["role"] == "assistant"
        assert (await db.get_session("dead-resumable"))["status"] == "idle"

    async def test_leaves_a_finished_turn_alone(self, sm, db):
        await db.create_session("finished", status="active")
        await db.update_session_fields("finished", {"status": "active"})
        await db.add_message("finished", "user", "go")
        await db.add_message("finished", "assistant", "done, 3 things checked")

        await sm.recover_orphaned_sessions()

        messages = await db.get_messages("finished")
        assert [m["role"] for m in messages] == ["user", "assistant"]
        assert messages[-1]["content"] == "done, 3 things checked"

    async def test_empty_session_gets_no_marker(self, sm, db):
        await db.create_session("never-ran", status="active")
        await db.update_session_fields("never-ran", {"status": "active"})

        await sm.recover_orphaned_sessions()

        assert await db.get_messages("never-ran") == []

    async def test_a_write_failure_does_not_break_recovery(self, sm, db):
        await db.create_session("write-fails", status="active")
        await db.update_session_fields("write-fails", {"status": "active"})
        await db.add_message("write-fails", "user", "go")
        sm.add_message = AsyncMock(side_effect=RuntimeError("db gone"))

        # Recovery still runs the session to its final status.
        await sm.recover_orphaned_sessions()

        assert (await db.get_session("write-fails"))["status"] == "stopped"


class TestOrphanRecoveryIsDaemonOnly:
    """`nerve cron` and friends must not touch the daemon's live sessions."""

    def test_recovery_is_opt_in(self):
        import inspect

        from nerve.agent.engine import AgentEngine

        param = inspect.signature(AgentEngine.initialize).parameters[
            "recover_orphans"
        ]
        assert param.default is False

    def test_only_the_gateway_opts_in(self):
        from pathlib import Path

        import nerve.agent.engine as engine_mod
        import nerve.cli as cli_mod
        import nerve.gateway.server as server_mod

        gateway = Path(server_mod.__file__).read_text()
        assert "initialize(recover_orphans=True)" in gateway

        cli = Path(cli_mod.__file__).read_text()
        assert "recover_orphans=True" not in cli

        # And the engine still only recovers behind the flag.
        engine = Path(engine_mod.__file__).read_text()
        assert "if recover_orphans:" in engine
