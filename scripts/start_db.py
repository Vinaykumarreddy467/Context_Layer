#!/usr/bin/env python3
"""Start SurrealDB with HTTP endpoint enabled for hooks."""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "data" / "handoffs.db"

sys.path.insert(0, str(ROOT))
from context_layer.env import load_local_env  # noqa: E402

load_local_env(ROOT / ".env")
SURREAL_URL = os.environ.get("SURREAL_URL", "ws://127.0.0.1:8010")
SURREAL_USER = os.environ.get("SURREAL_USER", "root")
SURREAL_PASS = os.environ.get("SURREAL_PASS", "")
SURREAL_NS = os.environ.get("SURREAL_NS", "dev")
SURREAL_DB = os.environ.get("SURREAL_DB", "context_layer")


def _db_reachable() -> bool:
    try:
        import asyncio
        from surrealdb import AsyncSurreal

        async def probe():
            db = AsyncSurreal(SURREAL_URL)
            await db.connect()
            await db.signin({"username": SURREAL_USER, "password": SURREAL_PASS})
            await db.use(SURREAL_NS, SURREAL_DB)
            await db.query("INFO FOR DB;")
            await db.close()

        asyncio.run(probe())
        return True
    except Exception:
        return False


def main() -> int:
    if not SURREAL_PASS:
        print("SURREAL_PASS is not set. Copy .env.example to .env and set a local password.",
              file=sys.stderr)
        return 1

    if _db_reachable():
        print("SurrealDB already running")
        return 0

    DB_DIR.parent.mkdir(parents=True, exist_ok=True)
    log_path = DB_DIR.parent / "surrealdb.log"
    try:
        log_file = log_path.open("ab")
        try:
            proc = subprocess.Popen(
                ["surreal", "start", "--username", SURREAL_USER, "--password", SURREAL_PASS,
                 "--bind", "127.0.0.1:8010", f"rocksdb://{DB_DIR}"],
                stdout=log_file, stderr=subprocess.STDOUT,
            )
        finally:
            log_file.close()
    except FileNotFoundError:
        print("surreal binary not found on PATH. Install from https://surrealdb.com/install",
              file=sys.stderr)
        return 1

    # Wait for readiness with a bounded timeout; logs are drained to disk.
    for _ in range(30):
        time.sleep(1)
        if _db_reachable():
            print("SurrealDB started successfully")
            return 0
    else:
        detail = ""
        if proc.poll() is not None and log_path.is_file():
            detail = log_path.read_text(encoding="utf-8", errors="replace")[-1000:].strip()
        message = "SurrealDB did not become ready within 30 seconds"
        if detail:
            message += f". Startup detail: {detail}"
        else:
            message += f". Check logs at {log_path}"
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
