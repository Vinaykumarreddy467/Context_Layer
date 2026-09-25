"""
Claude Code PreCompact hook adapter.

This is ONE adapter among several -- it's specific to Claude Code, which
is the only platform (so far) with a native "about to lose context" event.
Other agents need a different adapter (see adapters/), but they all call
the same underlying engine: auto_handoff.summarize_and_store().

Wire this into ~/.claude/settings.json:

{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "python <this_file_path>" }
        ]
      }
    ]
  }
}

Claude Code sends JSON on stdin shaped like:
{
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../<uuid>.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "PreCompact",
  "trigger": "manual" | "auto",
  "custom_instructions": ""
}

This script never blocks compaction: if anything fails (DB down, bad
transcript, missing API key), it prints a warning to stderr and exits 0
so Claude Code's own compaction proceeds regardless.
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

# Make the project root importable regardless of cwd this hook runs from
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from context_layer import auto_handoff, export_capsule as capsule, project_identity  # noqa: E402
import context_layer as cl  # noqa: E402


def _read_transcript(transcript_path: str) -> str:
    """
    Claude Code transcripts are JSONL -- one JSON object per line, each
    representing a turn. Extract plain text content defensively, since
    the exact per-line shape can include tool calls/results as well as
    plain messages.
    """
    path = Path(transcript_path).expanduser()
    lines_out = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg = entry.get("message", entry)
            role = msg.get("role", entry.get("type", "unknown"))
            content = msg.get("content", "")

            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                # content blocks: keep text blocks, skip tool_use/tool_result noise
                text = "\n".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            else:
                text = ""

            if text.strip():
                lines_out.append(f"{role}: {text.strip()}")

    return "\n".join(lines_out)


def _git_branch(cwd: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        branch = result.stdout.strip()
        return branch if branch else "unknown"
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
    payload = json.load(sys.stdin)
    transcript_path = payload.get("transcript_path")
    cwd = payload.get("cwd", os.getcwd())
    trigger = payload.get("trigger", "auto")

    task_slug = project_identity.resolve_task_slug(cwd)
    git_branch = _git_branch(cwd)
    transcript = _read_transcript(transcript_path)

    if not transcript.strip():
        print("pre_compact hook: empty transcript, skipping handoff", file=sys.stderr)
        return

    prev_id = await _latest_handoff_id(task_slug)

    handoff = await auto_handoff.summarize_and_store(
        transcript=transcript,
        task_slug=task_slug,
        git_branch=git_branch,
        continues_from_id=prev_id,
        platform_session_id=payload.get("session_id"),
    )

    if "error" in handoff:
        print(f"pre_compact hook: {handoff['error']}", file=sys.stderr)
        return

    print(f"context-layer: saved handoff {handoff.get('id')} "
          f"before {trigger} compaction (task={task_slug})")
    await capsule.sync_capsule(task_slug, cwd)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        # Never block Claude Code's own compaction on our failure
        print(f"pre_compact hook failed (non-blocking): {e}", file=sys.stderr)
    sys.exit(0)
