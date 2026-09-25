"""
Export a portable "context capsule" -- a plain markdown primer you can
paste into any AI chat UI that doesn't support MCP (ChatGPT, Gemini, a
plain API call, etc.), so the cross-platform case is covered even without
live sync. This is the honest, achievable version of "works with any
agent" -- manual paste instead of automatic sync, because no third party
can reach inside another vendor's chat UI.
"""

import context_layer as cl
from pathlib import Path
from typing import Optional


def _capsule_text(latest: dict) -> str:
    """Build the pasteable markdown primer from a handoff record."""
    # Prefer the structured summary. Older records without it use the shared
    # separator when available, with raw content as the final fallback.
    summary = latest.get("summary")
    if not summary:
        raw_content = latest.get("raw_content", "")
        summary = raw_content.split(cl.HANDOFF_CONTENT_SEPARATOR, 1)[0]

    lines = [
        f"# Context primer: {latest.get('task_slug')}",
        f"capsule_version: {latest.get('version', 1)}",
        "",
        "You are resuming work from a previous AI session on this task. "
        "Here is the context so far -- do not ask the user to re-explain it.",
        "",
        "## Summary",
        summary,
        "",
        "## Decisions already made (do not relitigate these)",
    ]
    for d in latest.get("decisions", []):
        lines.append(f"- **{d.get('text')}** — {d.get('rationale')}")

    lines.append("")
    lines.append("## Next steps")
    for step in latest.get("next_steps", []):
        lines.append(f"- {step}")

    return "\n".join(lines)


async def export_capsule(task_slug: str) -> str:
    """Build a pasteable markdown primer from the latest handoff for a task."""
    latest = await cl.get_latest_handoff(task_slug)
    if not latest:
        return f"No handoff found for task '{task_slug}'."
    return _capsule_text(latest)


async def sync_capsule(task_slug: str, project_dir) -> Optional[Path]:
    """Write the latest handoff capsule to CONTEXT.md in project_dir.

    Returns the written path, or None when no handoff exists yet. Any agent
    that reads project files (all coding agents) picks the context up with
    zero integration work.
    """
    latest = await cl.get_latest_handoff(task_slug)
    if not latest:
        return None
    target = Path(project_dir) / "CONTEXT.md"
    target.write_text(_capsule_text(latest) + "\n", encoding="utf-8")
    return target
