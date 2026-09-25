"""
VS Code Copilot Chat PreCompact hook adapter.

IMPORTANT CAVEAT: Copilot's hook system (v0.32+, still a preview feature)
is documented far less precisely than Claude Code's -- I could not find
an official field-by-field schema for what Copilot sends its PreCompact
hook on stdin. This script assumes it's similar to Claude Code's
(session_id / transcript_path / cwd), since several projects building
Copilot hooks describe "full parity with the Claude Code edition", but
that is inference, not a confirmed spec.

BEFORE TRUSTING THIS: run it once with the debug block below uncommented
to print the raw payload Copilot actually sends, confirm the real field
names, then adjust _get() calls accordingly. Do this once and it's done.

Install: point Copilot's hooks.json (see adapters/copilot/hooks.json) at
this file. This never blocks Copilot's own compaction if it fails.
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from context_layer import auto_handoff, export_capsule as capsule, project_identity  # noqa: E402
import context_layer as cl  # noqa: E402


def _get(payload: dict, *keys, default=None):
    """Try several possible field names, since the exact schema is unconfirmed."""
    for k in keys:
        if k in payload:
            return payload[k]
    return default


def _read_transcript(transcript_path: str) -> str:
    if not transcript_path:
        return ""
    path = Path(transcript_path).expanduser()
    if not path.exists():
        return ""

    lines_out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                # Not JSONL -- maybe it's plain markdown/text. Just use it directly.
                lines_out.append(line)
                continue

            msg = entry.get("message", entry)
            role = msg.get("role", entry.get("type", "unknown"))
            content = msg.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = "\n".join(
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
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
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


async def _latest_handoff_id(task_slug: str) -> str | None:
    db = await cl._connect()
    try:
        result = await db.query(
            "SELECT id, timestamp FROM handoff WHERE task_slug = $slug ORDER BY timestamp DESC LIMIT 1;",
            {"slug": task_slug},
        )
        rows = result[0] if result else []
        return str(rows[0]["id"]) if rows else None
    finally:
        await db.close()


async def main():
    payload = json.load(sys.stdin)

    # --- Uncomment this once to see Copilot's actual payload shape ---
    # with open("/tmp/copilot_precompact_debug.json", "w") as f:
    #     json.dump(payload, f, indent=2)

    transcript_path = _get(payload, "transcript_path", "transcriptPath", "transcript")
    cwd = _get(payload, "cwd", "workspaceFolder", default=os.getcwd())

    task_slug = project_identity.resolve_task_slug(cwd)
    git_branch = _git_branch(cwd)
    transcript = _read_transcript(transcript_path) if transcript_path else ""

    if not transcript.strip():
        print("copilot pre_compact hook: no transcript found, skipping "
              "(schema may differ from assumed -- see debug block)", file=sys.stderr)
        return

    prev_id = await _latest_handoff_id(task_slug)

    handoff = await auto_handoff.summarize_and_store(
        transcript=transcript,
        task_slug=task_slug,
        git_branch=git_branch,
        continues_from_id=prev_id,
        platform_session_id=_get(payload, "session_id", "sessionId"),
    )
    if "error" in handoff:
        print(f"copilot pre_compact hook: {handoff['error']}", file=sys.stderr)
        return
    print(f"context-layer: saved handoff {handoff.get('id')} (task={task_slug})")
    await capsule.sync_capsule(task_slug, cwd)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"copilot pre_compact hook failed (non-blocking): {e}", file=sys.stderr)
    sys.exit(0)
