"""
Small helper invoked by the OpenCode TypeScript plugin
(compaction-plugin.ts) via shell-out. Resolves the task_slug from the
project directory (via project_identity), reads the transcript from the
CONTEXT_LAYER_TRANSCRIPT env var, then reuses the same auto_handoff
engine every other adapter uses.

Usage (called by the plugin, not normally run by hand):
    python save_before_compact.py [--cwd <project-dir>]
"""

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from context_layer import auto_handoff, export_capsule as capsule, project_identity  # noqa: E402
import context_layer as cl  # noqa: E402


def _git_branch(cwd: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


async def _latest_handoff_id(task_slug: str) -> str | None:
    db = await cl._connect()
    try:
        result = await db.query(
            "SELECT id, timestamp FROM handoff WHERE task_slug = $slug "
            "ORDER BY timestamp DESC LIMIT 1;",
            {"slug": task_slug},
        )
        rows = result[0] if result else []
        return str(rows[0]["id"]) if rows else None
    finally:
        await db.close()


async def main():
    parser = argparse.ArgumentParser(prog="save_before_compact.py")
    parser.add_argument("--cwd", default=os.getcwd(),
                        help="project directory to resolve the task_slug from")
    args = parser.parse_args()

    task_slug = project_identity.resolve_task_slug(args.cwd)
    transcript = os.environ.get("CONTEXT_LAYER_TRANSCRIPT", "").strip()
    session_id = os.environ.get("CONTEXT_LAYER_SESSION_ID", "").strip() or None
    git_branch = _git_branch(args.cwd)

    if not transcript:
        print("no transcript provided, skipping handoff", file=sys.stderr)
        return

    prev_id = await _latest_handoff_id(task_slug)

    handoff = await auto_handoff.summarize_and_store(
        transcript=transcript,
        task_slug=task_slug,
        git_branch=git_branch,
        continues_from_id=prev_id,
        platform_session_id=session_id,
    )

    if "error" in handoff:
        print(f"save_before_compact: {handoff['error']}", file=sys.stderr)
        return

    print(f"saved handoff {handoff.get('id')} for task={task_slug}")
    await capsule.sync_capsule(task_slug, args.cwd)


if __name__ == "__main__":
    asyncio.run(main())
