"""V3: Add columns to sessions, create channel_sessions and session_events tables.

This is the most complex migration — adds columns, creates tables,
migrates data from metadata JSON blobs to dedicated columns, and
backfills message counts.
"""

from __future__ import annotations

import json
import logging
import sqlite3

import aiosqlite

logger = logging.getLogger(__name__)

_V3_SESSION_COLUMNS = [
    ("status", "TEXT NOT NULL DEFAULT 'idle'"),
    ("sdk_session_id", "TEXT"),
    ("parent_session_id", "TEXT"),
    ("forked_from_message", "TEXT"),
    ("connected_at", "TEXT"),
    ("last_activity_at", "TEXT"),
    ("archived_at", "TEXT"),
    ("message_count", "INTEGER DEFAULT 0"),
    ("total_cost_usd", "REAL DEFAULT 0.0"),
    ("last_memorized_at", "TEXT"),
]

TABLES_SQL = """
-- Persistent channel-to-session mapping (survives restarts)
CREATE TABLE IF NOT EXISTS channel_sessions (
    channel_key TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Session lifecycle event log (append-only audit trail)
CREATE TABLE IF NOT EXISTS session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    event_type TEXT NOT NULL,
    details JSON,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_session_events_session ON session_events(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_sdk_id ON sessions(sdk_session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_parent ON sessions(parent_session_id);
"""


async def up(db: aiosqlite.Connection) -> None:
    # Add new columns to sessions table (idempotent)
    for col_name, col_def in _V3_SESSION_COLUMNS:
        try:
            await db.execute(
                f"ALTER TABLE sessions ADD COLUMN {col_name} {col_def}"
            )
            logger.info("Added column sessions.%s", col_name)
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                logger.debug("Column sessions.%s already exists", col_name)
            else:
                raise

    # Verify all expected columns were added
    expected_cols = {name for name, _ in _V3_SESSION_COLUMNS}
    async with db.execute("PRAGMA table_info(sessions)") as cursor:
        actual_cols = {row[1] async for row in cursor}
    missing = expected_cols - actual_cols
    if missing:
        raise RuntimeError(
            f"V3 migration failed: sessions table missing columns: {missing}"
        )

    # Create new tables and indexes
    await db.executescript(TABLES_SQL)

    # Migrate data from metadata JSON blob to dedicated columns
    async with db.execute("SELECT id, metadata FROM sessions") as cursor:
        rows = [dict(row) async for row in cursor]
    for row in rows:
        meta = json.loads(row.get("metadata") or "{}")
        sdk_id = meta.get("sdk_session_id")
        conn_at = meta.get("connected_at")
        if sdk_id or conn_at:
            sets, params = [], []
            if sdk_id:
                sets.append("sdk_session_id = ?")
                params.append(sdk_id)
            if conn_at:
                sets.append("connected_at = ?")
                params.append(conn_at)
            params.append(row["id"])
            await db.execute(
                f"UPDATE sessions SET {', '.join(sets)} WHERE id = ?",
                tuple(params),
            )

    # Backfill message counts
    await db.execute("""
        UPDATE sessions SET message_count = (
            SELECT COUNT(*) FROM messages WHERE messages.session_id = sessions.id
        )
    """)
