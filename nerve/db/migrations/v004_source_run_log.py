"""V4: Source run log table and reset sync cursors."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)

SQL = """
-- Per-source run log for diagnostics
CREATE TABLE IF NOT EXISTS source_run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    ran_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    records_fetched INTEGER DEFAULT 0,
    records_processed INTEGER DEFAULT 0,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_source_run_log_source ON source_run_log(source, ran_at DESC);
"""


async def up(db: aiosqlite.Connection) -> None:
    # Reset sync cursors — old JSONL line-number cursors are meaningless
    # in the new sources layer. Sources will re-establish proper cursors.
    await db.execute("DELETE FROM sync_cursors")
    await db.executescript(SQL)
    logger.info("V4 migration: reset sync cursors, created source_run_log")
