"""V6: Index on tasks.source_url for dedup lookups."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)

SQL = """
-- Index for fast source_url dedup lookups
CREATE INDEX IF NOT EXISTS idx_tasks_source_url ON tasks(source_url);
"""


async def up(db: aiosqlite.Connection) -> None:
    await db.executescript(SQL)
    logger.info("V6 migration: added source_url index")
