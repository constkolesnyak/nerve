"""V9: Add raw_content column to source_messages."""

from __future__ import annotations

import logging
import sqlite3

import aiosqlite

logger = logging.getLogger(__name__)


async def up(db: aiosqlite.Connection) -> None:
    try:
        await db.execute(
            "ALTER TABLE source_messages ADD COLUMN raw_content TEXT"
        )
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise
    logger.info("V9 migration: added source_messages.raw_content column")
