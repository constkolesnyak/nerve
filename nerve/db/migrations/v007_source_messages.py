"""V7: Source messages inbox table and source_run_log.session_id column."""

from __future__ import annotations

import logging
import sqlite3

import aiosqlite

logger = logging.getLogger(__name__)

SQL = """
-- Source messages inbox (persistent storage with TTL)
CREATE TABLE IF NOT EXISTS source_messages (
    id TEXT NOT NULL,
    source TEXT NOT NULL,
    record_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    content TEXT NOT NULL,
    processed_content TEXT,
    timestamp TEXT NOT NULL,
    metadata JSON,
    run_session_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    PRIMARY KEY (source, id)
);
CREATE INDEX IF NOT EXISTS idx_source_messages_ts ON source_messages(source, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_source_messages_expires ON source_messages(expires_at);
CREATE INDEX IF NOT EXISTS idx_source_messages_created ON source_messages(created_at DESC);
"""


async def up(db: aiosqlite.Connection) -> None:
    await db.executescript(SQL)
    # Add session_id column to source_run_log
    try:
        await db.execute(
            "ALTER TABLE source_run_log ADD COLUMN session_id TEXT"
        )
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise
    logger.info("V7 migration: created source_messages table, added source_run_log.session_id")
