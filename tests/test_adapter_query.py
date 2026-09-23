"""Verify the fixed _latest_handoff_id query used by all three adapters."""
import asyncio
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["SURREAL_URL"] = "ws://127.0.0.1:8010"
os.environ["SURREAL_NS"] = "dev"
os.environ["SURREAL_DB"] = "context_layer"
os.environ["SURREAL_USER"] = "root"
os.environ["SURREAL_PASS"] = "root"

import context_layer as cl


async def main():
    db = await cl._connect()
    try:
        result = await db.query(
            "SELECT id, timestamp FROM handoff WHERE task_slug = $slug "
            "ORDER BY timestamp DESC LIMIT 1;",
            {"slug": "semantic-demo"},
        )
        rows = result[0] if result else []
        print("OK, latest:", str(rows[0]["id"]) if rows else "none")
    finally:
        await db.close()


asyncio.run(main())