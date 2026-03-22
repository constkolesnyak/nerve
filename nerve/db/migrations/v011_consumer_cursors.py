"""V11: Consumer cursors for Kafka-like source consumption."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)

SQL = """
-- Consumer cursors for Kafka-like source consumption
CREATE TABLE IF NOT EXISTS consumer_cursors (
    consumer TEXT NOT NULL,
    source TEXT NOT NULL,
    cursor_seq INTEGER NOT NULL DEFAULT 0,
    session_id TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT,
    PRIMARY KEY (consumer, source)
);
"""


async def up(db: aiosqlite.Connection) -> None:
    await db.executescript(SQL)
    logger.info("V11 migration: created consumer_cursors table")
