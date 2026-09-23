#!/usr/bin/env python3
"""
Migration runner for Context Layer SurrealDB schema.

Usage:
    python scripts/run_migrations.py           # Apply all pending migrations
    python scripts/run_migrations.py --status  # Show migration status
    python scripts/run_migrations.py --fake 0003  # Mark migration as applied without running
"""
import asyncio
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import context_layer as cl

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "sql" / "migrations"


async def _connect():
    return await cl._connect()


async def ensure_version_table(db):
    """Create schema_version table if it doesn't exist."""
    await db.query("""
        DEFINE TABLE IF NOT EXISTS schema_version SCHEMAFULL;
        DEFINE FIELD IF NOT EXISTS version ON schema_version TYPE int;
        DEFINE FIELD IF NOT EXISTS applied_at ON schema_version TYPE datetime DEFAULT time::now();
        DEFINE FIELD IF NOT EXISTS description ON schema_version TYPE string;
        DEFINE INDEX IF NOT EXISTS version_idx ON schema_version FIELDS version UNIQUE;
    """)


async def get_applied_versions(db):
    """Get list of applied migration versions."""
    result = await db.query("SELECT version FROM schema_version ORDER BY version;")
    rows = result[0] if result else []
    return {r["version"] for r in rows}


async def apply_migration(db, version: int, description: str, sql: str):
    """Apply a single migration and record it."""
    # Run the migration SQL
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if not stmt:
            continue
        await db.query(stmt)

    # Record the migration
    await db.create("schema_version", {
        "version": version,
        "description": description,
    })
    print(f"  Applied migration {version:04d}: {description}")


async def run_migrations(fake_version: int | None = None):
    """Run all pending migrations."""
    db = await _connect()
    try:
        await ensure_version_table(db)
        applied = await get_applied_versions(db)

        # Find all migration files
        migration_files = sorted(MIGRATIONS_DIR.glob("*.surql"))
        if not migration_files:
            print("No migration files found.")
            return

        for mf in migration_files:
            # Parse version from filename (e.g., 0001_initial_schema.surql)
            match = re.match(r"(\d{4})_(.+)\.surql", mf.name)
            if not match:
                print(f"  Skipping {mf.name}: invalid name format (expected 0001_name.surql)")
                continue

            version = int(match.group(1))
            description = match.group(2).replace("_", " ")

            if version in applied:
                print(f"  Already applied: {version:04d} - {description}")
                continue

            if fake_version and version == fake_version:
                await db.create("schema_version", {"version": version, "description": description})
                print(f"  Faked migration {version:04d}: {description}")
                continue

            print(f"  Applying migration {version:04d}: {description}...")
            sql = mf.read_text(encoding="utf-8")
            await apply_migration(db, version, description, sql)

        print("\nAll migrations complete.")
    finally:
        await db.close()


async def show_status():
    """Show migration status."""
    db = await _connect()
    try:
        await ensure_version_table(db)
        applied = await get_applied_versions(db)

        migration_files = sorted(MIGRATIONS_DIR.glob("*.surql"))
        if not migration_files:
            print("No migration files found.")
            return

        print("Migration Status:")
        print("-----------------")
        for mf in migration_files:
            match = re.match(r"(\d{4})_(.+)\.surql", mf.name)
            if not match:
                print(f"  {mf.name}: INVALID NAME FORMAT")
                continue
            version = int(match.group(1))
            description = match.group(2).replace("_", " ")
            status = "APPLIED" if version in applied else "PENDING"
            print(f"  {version:04d} - {description}: {status}")
    finally:
        await db.close()


def main():
    if "--status" in sys.argv:
        asyncio.run(show_status())
    elif "--fake" in sys.argv:
        try:
            idx = sys.argv.index("--fake")
            version = int(sys.argv[idx + 1])
            asyncio.run(run_migrations(fake_version=version))
        except (IndexError, ValueError):
            print("Usage: python run_migrations.py --fake <version>")
            sys.exit(1)
    else:
        asyncio.run(run_migrations())


if __name__ == "__main__":
    main()
