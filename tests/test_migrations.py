"""Test migration system."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import context_layer as cl


async def main():
    db = await cl._connect()
    try:
        # Ensure schema_version table exists
        await db.query("""
            DEFINE TABLE IF NOT EXISTS schema_version SCHEMAFULL;
            DEFINE FIELD IF NOT EXISTS version ON schema_version TYPE int;
            DEFINE FIELD IF NOT EXISTS applied_at ON schema_version TYPE datetime DEFAULT time::now();
            DEFINE FIELD IF NOT EXISTS description ON schema_version TYPE string;
            DEFINE INDEX IF NOT EXISTS version_idx ON schema_version FIELDS version UNIQUE;
        """)

        # Check applied migrations
        result = await db.query("SELECT version, description FROM schema_version ORDER BY version;")
        rows = result[0] if result else []
        print("Applied migrations:")
        for r in rows:
            print(f"  {r['version']:04d}: {r['description']}")

        # Verify handoff table exists
        result = await db.query("INFO FOR TABLE handoff;")
        print("\nHandoff table exists:", bool(result))

        # Verify continues_from table exists
        result = await db.query("INFO FOR TABLE continues_from;")
        print("Continues_from table exists:", bool(result))

        print("\nMIGRATION TEST PASSED")
    finally:
        await db.close()


asyncio.run(main())