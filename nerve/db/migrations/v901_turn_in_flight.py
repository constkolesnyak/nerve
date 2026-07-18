"""V901: Persisted in-flight-turn marker on sessions.

Records that a session has a turn actively executing, so an interrupted
turn can be detected and resumed after a restart.

Background: the "mid-turn" signal (``SessionManager._running_sessions``)
is in-memory only and is lost when the process dies. Graceful
``AgentEngine.shutdown()`` additionally rewrites every session to
``idle``, so after a clean restart there is no surviving signal of who
was working. These two columns survive the restart:

* ``turn_in_flight`` — 1 while a turn runs, cleared to 0 when it ends
  (success, error, or stop).
* ``turn_started_at`` — UTC ISO timestamp the turn began, used as a
  staleness guard by the startup resumer.

On boot, ``AgentEngine.resume_interrupted_turns()`` finds sessions still
marked in-flight and re-injects a restart-aware continuation.
"""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)


async def up(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        ALTER TABLE sessions ADD COLUMN turn_in_flight INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE sessions ADD COLUMN turn_started_at TEXT;
        """
    )
    # Startup resumer scans WHERE turn_in_flight = 1.
    await db.execute(
        """CREATE INDEX IF NOT EXISTS idx_sessions_turn_in_flight
               ON sessions (turn_in_flight)"""
    )
    logger.info("v901: added sessions.turn_in_flight / turn_started_at")
