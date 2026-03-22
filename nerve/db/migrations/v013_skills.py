"""V13: Skills registry and usage tracking."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)

SQL = """
-- Skills registry (filesystem is source of truth, DB indexes metadata + tracks usage)
CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    version TEXT DEFAULT '1.0.0',
    enabled BOOLEAN DEFAULT 1,
    user_invocable BOOLEAN DEFAULT 1,
    model_invocable BOOLEAN DEFAULT 1,
    allowed_tools TEXT,
    metadata JSON DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Skill usage tracking for statistics
CREATE TABLE IF NOT EXISTS skill_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL,
    session_id TEXT,
    invoked_by TEXT NOT NULL,
    duration_ms INTEGER,
    success BOOLEAN DEFAULT 1,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_skill_usage_skill ON skill_usage(skill_id, created_at);
"""


async def up(db: aiosqlite.Connection) -> None:
    await db.executescript(SQL)
    logger.info("V13 migration: created skills and skill_usage tables")
