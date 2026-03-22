"""V2: memU audit log table."""

from __future__ import annotations

import aiosqlite

SQL = """
-- memU audit log
CREATE TABLE IF NOT EXISTS memu_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    source TEXT,
    details TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON memu_audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON memu_audit_log(action);
"""


async def up(db: aiosqlite.Connection) -> None:
    await db.executescript(SQL)
