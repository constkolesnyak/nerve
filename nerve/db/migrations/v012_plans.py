"""V12: Plans table for async human review."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)

SQL = """
-- Plans proposed by the planner agent for async human review
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    session_id TEXT,
    impl_session_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    content TEXT NOT NULL,
    feedback TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    parent_plan_id TEXT,
    model TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_plans_task ON plans(task_id);
CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);
"""


async def up(db: aiosqlite.Connection) -> None:
    await db.executescript(SQL)
    logger.info("V12 migration: created plans table")
