"""V10: Session file snapshots for diff view."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)

SQL = """
CREATE TABLE IF NOT EXISTS session_file_snapshots (
    session_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    original_content TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (session_id, file_path)
);
CREATE INDEX IF NOT EXISTS idx_file_snapshots_session
    ON session_file_snapshots(session_id);
"""


async def up(db: aiosqlite.Connection) -> None:
    await db.executescript(SQL)
    logger.info("V10 migration: created session_file_snapshots table")
