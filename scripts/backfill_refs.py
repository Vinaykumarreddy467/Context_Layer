#!/usr/bin/env python3
"""Backfill files/refs metadata on existing handoffs (one-time migration).

Run after upgrading to the files/refs schema:
    python scripts/backfill_refs.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import context_layer as cl


async def main():
    db = await cl._connect()
    try:
        rows = (await db.query(
            "SELECT id, raw_content, summary, decisions, next_steps FROM handoff;"
        ))[0]
        updated = 0
        for h in rows:
            files, refs = cl.extract_files_refs(
                h.get("raw_content", ""), h.get("summary", ""),
                " ".join(d.get("text", "") for d in (h.get("decisions") or [])),
                " ".join(h.get("next_steps") or []),
            )
            if files or refs:
                await db.update(h["id"]).merge({"files": files, "refs": refs})
                updated += 1
        print(f"backfilled {updated}/{len(rows)} handoffs")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
