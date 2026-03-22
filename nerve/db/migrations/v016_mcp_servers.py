"""V16: MCP server registry and tool usage tracking."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)

SQL = """
-- MCP server registry (config is source of truth, DB tracks metadata + usage)
CREATE TABLE IF NOT EXISTS mcp_servers (
    name TEXT PRIMARY KEY,
    type TEXT NOT NULL DEFAULT 'stdio',
    enabled BOOLEAN DEFAULT 1,
    tool_count INTEGER DEFAULT 0,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- MCP tool invocation tracking
CREATE TABLE IF NOT EXISTS mcp_tool_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_name TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    session_id TEXT,
    duration_ms INTEGER,
    success BOOLEAN DEFAULT 1,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_usage_server ON mcp_tool_usage(server_name, created_at);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_usage_session ON mcp_tool_usage(session_id, created_at);
"""


async def up(db: aiosqlite.Connection) -> None:
    await db.executescript(SQL)
    logger.info("V16 migration: created mcp_servers and mcp_tool_usage tables")
