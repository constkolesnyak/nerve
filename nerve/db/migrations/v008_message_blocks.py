"""V8: Add blocks JSON column to messages."""

from __future__ import annotations

import logging
import sqlite3

import aiosqlite

logger = logging.getLogger(__name__)


async def up(db: aiosqlite.Connection) -> None:
    try:
        await db.execute("ALTER TABLE messages ADD COLUMN blocks JSON")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise
    logger.info("V8 migration: added messages.blocks column")
