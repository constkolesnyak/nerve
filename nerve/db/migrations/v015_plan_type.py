"""V15: Add plan_type column to plans table."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)


async def up(db: aiosqlite.Connection) -> None:
    await db.executescript("ALTER TABLE plans ADD COLUMN plan_type TEXT DEFAULT 'generic';")
    logger.info("V15 migration: added plan_type column to plans table")
