"""Codex lifecycle adapter for loading and saving Context Layer handoffs.

Codex passes one JSON event on stdin. SessionStart injects the latest saved
context; PreCompact and SessionEnd capture the session transcript. Hook errors
are reported to stderr and never prevent Codex from continuing.
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import context_layer as cl  # noqa: E402
from context_layer import auto_handoff, export_capsule as capsule, project_identity  # noqa: E402


def _git_branch(cwd: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _read_transcript(transcript_path: str | None) -> str:
    """Extract message text from Codex's JSONL transcript defensively.

    Codex documents transcript_path as a convenience field whose wire format
    may change, so unknown records and content blocks are ignored safely.
    """
    if not transcript_path:
        return ""
    path = Path(transcript_path).expanduser()
    if not path.is_file():
        return ""

    messages: list[str] = []
    with path.open("r", encoding="utf-8") as transcript_file:
        for raw_line in transcript_file:
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                messages.append(line)
                continue
            if not isinstance(entry, dict):
                continue

            payload = entry.get("payload", entry)
            if not isinstance(payload, dict):
                continue
            role = payload.get("role") or entry.get("role")
            if role not in {"user", "assistant"}:
                continue
            content = payload.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = "\n".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict)
                    and block.get("type") in {"text", "input_text", "output_text"}
                    and isinstance(block.get("text"), str)
                )
            else:
                text = ""
            if text.strip():
                messages.append(f"{role}: {text.strip()}")
    return "\n".join(messages)


async def _latest_handoff_id(task_slug: str) -> str | None:
    db = await cl._connect()
    try:
        result = await db.query(
            "SELECT id FROM handoff WHERE task_slug = $slug "
            "ORDER BY timestamp DESC LIMIT 1;",
            {"slug": task_slug},
        )
        rows = result[0] if result else []
        return str(rows[0]["id"]) if rows else None
    finally:
        await db.close()


async def _session_start(task_slug: str) -> None:
    context = await cl.get_current_context(task_slug)
    sections = context.get("sections", []) if context else []
    if not sections:
        return
    additional_context = "\n\n".join(
        section.get("content", "") for section in sections if section.get("content")
    ).strip()
    if additional_context:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": (
                    "Relevant Context Layer handoff for this project:\n\n"
                    + additional_context
                ),
            }
        }))


async def _save_handoff(payload: dict, cwd: str, task_slug: str) -> None:
    transcript = _read_transcript(payload.get("transcript_path"))
    if not transcript.strip():
        return
    previous_id = await _latest_handoff_id(task_slug)
    handoff = await auto_handoff.summarize_and_store(
        transcript=transcript,
        task_slug=task_slug,
        git_branch=_git_branch(cwd),
        continues_from_id=previous_id,
        platform_session_id=payload.get("session_id"),
    )
    if handoff.get("error"):
        raise RuntimeError(handoff["error"])
    await capsule.sync_capsule(task_slug, cwd)


async def main() -> None:
    payload = json.load(sys.stdin)
    cwd = payload.get("cwd") or os.getcwd()
    task_slug = project_identity.resolve_task_slug(cwd)
    event = payload.get("hook_event_name")

    if event == "SessionStart":
        await _session_start(task_slug)
    elif event in {"PreCompact", "SessionEnd"}:
        await _save_handoff(payload, cwd, task_slug)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"context-layer Codex hook failed (non-blocking): {exc}", file=sys.stderr)
        sys.exit(0)
