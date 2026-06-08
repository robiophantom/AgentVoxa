import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import inspect, text

import models  # noqa: F401  # Ensure all SQLAlchemy models are registered on Base.metadata.

from core.database import create_tables, engine

def _get_call_log_columns(sync_conn):
    inspector = inspect(sync_conn)
    if "call_logs" not in inspector.get_table_names():
        return None

    return {column["name"] for column in inspector.get_columns("call_logs")}


async def run_migration():
    print("Ensuring all database tables exist...")
    await create_tables()

    async with engine.begin() as conn:
        columns = await conn.run_sync(_get_call_log_columns)

        if columns is None:
            print("call_logs table does not exist yet; it will be created by the app startup path.")
            return

        if "vapi_call_id" in columns:
            print("call_logs already uses vapi_call_id. No migration needed.")
            return

        if "exotel_call_uuid" not in columns:
            print("call_logs exists, but no legacy exotel_call_uuid column was found. Nothing to rename.")
            return

        print("Renaming call_logs.exotel_call_uuid to vapi_call_id...")
        try:
            await conn.execute(
                text("ALTER TABLE call_logs RENAME COLUMN exotel_call_uuid TO vapi_call_id")
            )
            print("Successfully renamed column to vapi_call_id.")
        except Exception as error:
            print(f"Migration failed while renaming column: {error}")
            raise

if __name__ == "__main__":
    asyncio.run(run_migration())
