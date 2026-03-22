"""V5: Full-text search index for tasks."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)

SQL = """
-- Full-text search index for tasks (title + content)
CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(task_id UNINDEXED, title, content);
"""


async def up(db: aiosqlite.Connection) -> None:
    await db.executescript(SQL)
    # Seed FTS from existing tasks (title only — next reindex fills content)
    await db.execute(
        "INSERT INTO tasks_fts (task_id, title, content) SELECT id, title, '' FROM tasks"
    )
    logger.info("V5 migration: created tasks_fts full-text search index")
