"""Non-destructive PostgreSQL migration for enhanced AgentVoxa models.

Run from the backend directory:
    python scripts/migrate_app_enhancements.py
"""
from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import models  # noqa: F401 - register every model before create_all.
from core.database import create_tables, engine


ALTERATIONS = [
    "CREATE TABLE IF NOT EXISTS app_settings (key VARCHAR(100) PRIMARY KEY, value TEXT NOT NULL, updated_at TIMESTAMP WITH TIME ZONE NOT NULL)",
    "ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS tool_executions TEXT",
    "ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS failure_details TEXT",
    "ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS latency_ms DOUBLE PRECISION",
    "ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS cost_metadata TEXT",
]


async def migrate() -> None:
    await create_tables()
    async with engine.begin() as connection:
        for statement in ALTERATIONS:
            await connection.execute(text(statement))


if __name__ == "__main__":
    asyncio.run(migrate())
