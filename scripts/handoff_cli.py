"""
CLI for the context layer, so non-MCP callers (IDE hooks, opencode plugins,
shell scripts) can auto-summarize and resume handoffs.

Usage:
  python handoff_cli.py summarize <task_slug> <git_branch> [--transcript-file <path>] [--continues-from <id>]
  python handoff_cli.py resume <task_slug>
  python handoff_cli.py sync [--cwd <dir>]
  python handoff_cli.py export <task_slug> [--output <file>]
  python handoff_cli.py import <file> [--task-slug <slug>]
  python handoff_cli.py consolidate <task_slug> [--git-branch <branch>]
  python handoff_cli.py check [--cwd <dir>]
  python handoff_cli.py forget <task_slug> [--yes]
  python handoff_cli.py backup [--dir <dir>]

Exit code 0 on success, 1 on failure. Prints JSON to stdout.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import context_layer as cl
from context_layer import auto_handoff, export_capsule as capsule
from context_layer import project_identity


async def _summarize(args) -> dict:
    if args.transcript_file:
        with open(args.transcript_file, encoding="utf-8") as f:
            transcript = f.read()
    else:
        transcript = sys.stdin.read()
    if not transcript.strip():
        return {"error": "empty transcript"}
    result = await auto_handoff.summarize_and_store(
        transcript, args.task_slug, args.git_branch, args.continues_from
    )
    # Refresh CONTEXT.md in the current project, if this is one.
    if "error" not in result:
        cwd = Path(os.getcwd())
        if (cwd / project_identity.IDENTITY_FILE).is_file():
            target = await capsule.sync_capsule(result["task_slug"], cwd)
            if target:
                result["synced"] = str(target)
    return result


async def _resume(args) -> dict:
    handoff = await cl.resume_handoff(args.task_slug)
    if not handoff:
        return {"error": f"no handoff for task '{args.task_slug}'"}
    return handoff


async def _sync(args) -> dict:
    slug = project_identity.resolve_task_slug(args.cwd)
    target = await capsule.sync_capsule(slug, args.cwd)
    if not target:
        return {"error": f"no handoff for task '{slug}'"}
    return {"task_slug": slug, "synced": str(target)}


async def _export(args) -> dict:
    db = await cl._connect()
    try:
        result = await db.query(
            "SELECT * FROM handoff WHERE task_slug = $slug ORDER BY timestamp ASC;",
            {"slug": args.task_slug},
        )
        rows = result[0] if result else []
        data = [dict(r) for r in rows]
    finally:
        await db.close()

    if args.output:
        Path(args.output).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return {"task_slug": args.task_slug, "count": len(data), "written": args.output}
    else:
        # Print to stdout for piping
        print(json.dumps(data, default=str))
        return {"task_slug": args.task_slug, "count": len(data)}


async def _import(args) -> dict:
    path = Path(args.file)
    if not path.is_file():
        return {"error": f"file not found: {path}"}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return {"error": "expected JSON array of handoff records"}

    created = 0
    for record in data:
        # Use create_handoff to preserve the engine's embedding + validation
        # Note: this generates new IDs/timestamps; original IDs are not preserved.
        # For true ID preservation, a direct DB insert would be needed.
        result = await cl.create_handoff(
            task_slug=args.task_slug or record.get("task_slug"),
            git_branch=record.get("git_branch", "main"),
            decisions=record.get("decisions", []),
            next_steps=record.get("next_steps", []),
            raw_content=record.get("raw_content", ""),
            summary=record.get("summary"),
            continues_from_id=record.get("continues_from_id"),
            platform_session_id=record.get("platform_session_id"),
        )
        if "error" in result:
            return {"error": f"failed to import record: {result['error']}"}
        created += 1
    return {"imported": created, "task_slug": args.task_slug or data[0].get("task_slug") if data else None}


CONSOLIDATION_PROMPT = """You are consolidating multiple handoff records from a long-running project into a single canonical current-state document.

Input: a chronological list of handoffs, each with decisions, next_steps, summary, and raw content.

Output: ONLY a JSON object (no markdown, no preamble) with this exact shape:
{
  "decisions": [{"text": "...", "rationale": "..."}],
  "next_steps": ["...", "..."],
  "summary": "Concise 3-5 sentence current state: what's working, what's open, what's next.",
  "superseded": ["decision text that is no longer valid", "..."]
}

Rules:
- MERGE duplicate/similar decisions into ONE entry with the strongest rationale.
- If a later handoff explicitly reverses or replaces an earlier decision, put the OLD decision text in "superseded" and the NEW one in "decisions".
- DEDUPLICATE next_steps: same action = one entry. Keep only steps that are still OPEN (not done).
- The summary must reflect CURRENT state, not history. "X is done, Y is in progress, Z is blocked" style.
- Do not invent decisions/steps not present in the input.
- If the input is empty, return empty arrays and "No handoffs to consolidate."

Handoffs (oldest first):
"""


async def _consolidate(args) -> dict:
    db = await cl._connect()
    try:
        result = await db.query(
            "SELECT * FROM handoff WHERE task_slug = $slug ORDER BY timestamp ASC;",
            {"slug": args.task_slug},
        )
        rows = result[0] if result else []
        handoffs = [dict(r) for r in rows]
    finally:
        await db.close()

    if not handoffs:
        return {"error": f"no handoffs for task '{args.task_slug}'"}

    # Build the consolidation input
    parts = []
    for i, h in enumerate(handoffs):
        parts.append(f"--- Handoff {i+1} ({h.get('timestamp', 'unknown')}) ---")
        if h.get("summary"):
            parts.append(f"Summary: {h['summary']}")
        if h.get("decisions"):
            parts.append("Decisions:")
            for d in h["decisions"]:
                parts.append(f"  - {d.get('text')}: {d.get('rationale')}")
        if h.get("next_steps"):
            parts.append("Next steps:")
            for s in h["next_steps"]:
                parts.append(f"  - {s}")
        if h.get("raw_content"):
            # Truncate raw content to keep prompt manageable
            raw = h["raw_content"][:2000]
            parts.append(f"Raw (truncated): {raw}")
        parts.append("")

    transcript = "\n".join(parts)

    # Use the same extraction path as auto_handoff (Claude if key, else local)
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from anthropic import Anthropic
            client = Anthropic()
            model = os.environ.get("CONTEXT_LAYER_CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
            response = client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[{"role": "user", "content": CONSOLIDATION_PROMPT + transcript}],
            )
            raw_text = response.content[0].text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()
            consolidated = json.loads(raw_text)
            extraction_status = "claude"
        except Exception as e:
            consolidated = _consolidate_local(handoffs)
            extraction_status = "local_fallback"
            consolidated["summary"] = f"[Warning: Claude consolidation failed ({type(e).__name__}); local fallback used.]\n\n" + consolidated["summary"]
    else:
        consolidated = _consolidate_local(handoffs)
        extraction_status = "local"

    # Store as a new handoff with status "consolidated"
    git_branch = args.git_branch or (handoffs[-1].get("git_branch") if handoffs else "main")
    combined_content = consolidated.get("summary", "") + cl.HANDOFF_CONTENT_SEPARATOR + transcript

    handoff = await cl.create_handoff(
        task_slug=args.task_slug,
        git_branch=git_branch,
        decisions=consolidated.get("decisions", []),
        next_steps=consolidated.get("next_steps", []),
        raw_content=combined_content,
        summary=consolidated.get("summary", ""),
        continues_from_id=str(handoffs[-1].get("id")) if handoffs else None,
        platform_session_id="consolidation",
    )
    handoff["extraction_status"] = extraction_status
    handoff["consolidated_from"] = len(handoffs)
    handoff["superseded"] = consolidated.get("superseded", [])

    # Refresh CONTEXT.md if in a project
    cwd = Path(os.getcwd())
    if (cwd / project_identity.IDENTITY_FILE).is_file():
        target = await capsule.sync_capsule(args.task_slug, cwd)
        if target:
            handoff["synced"] = str(target)

    return handoff


def _consolidate_local(handoffs: list) -> dict:
    """Heuristic consolidation without LLM: merge by exact text match, keep latest."""
    seen_decisions = {}
    seen_steps = set()
    superseded = []

    for h in handoffs:
        for d in h.get("decisions", []):
            text = d.get("text", "").strip()
            if text:
                # Simple: later handoff wins for same text
                seen_decisions[text] = d.get("rationale", "stated in handoff")
        for s in h.get("next_steps", []):
            s = s.strip()
            if s:
                seen_steps.add(s)

    # No supersession detection in local mode
    return {
        "decisions": [{"text": k, "rationale": v} for k, v in seen_decisions.items()],
        "next_steps": list(seen_steps)[:10],
        "summary": f"Consolidated {len(handoffs)} handoffs (local heuristic). {len(seen_decisions)} unique decisions, {len(seen_steps)} open steps.",
        "superseded": [],
    }


async def _check(args) -> dict:
    """Per-client lifecycle check: DB reachable, embedder loads, adapters present."""
    report = {"db": "unknown", "embedder": "unknown", "adapters": {}}

    # 1. Database reachable + migrations applied
    try:
        db = await cl._connect()
        try:
            result = await db.query("INFO FOR TABLE handoff;")
            report["db"] = "ok"
        finally:
            await db.close()
    except Exception as e:
        report["db"] = f"FAIL: {type(e).__name__}: {e}"

    # 2. Embedder loads (sync fallback path, same model)
    try:
        from context_layer.core import _embed, _get_embedder
        emb = _get_embedder()
        vec = _embed("lifecycle check")
        report["embedder"] = f"ok (dim={len(vec)})"
    except Exception as e:
        report["embedder"] = f"FAIL: {type(e).__name__}: {e}"

    # 3. Adapter files present (the per-client integrations)
    root = Path(__file__).resolve().parent.parent
    adapters = {
        "codex": root / "adapters" / "codex" / "hook.py",
        "copilot": root / "adapters" / "copilot" / "pre_compact.py",
        "claude": root / "hooks" / "pre_compact.py",
        "opencode": root / "adapters" / "opencode" / "save_before_compact.py",
    }
    for name, path in adapters.items():
        report["adapters"][name] = "ok" if path.is_file() else "MISSING"

    return report


async def _forget(args) -> dict:
    """Delete all handoffs for a task (correction/forget). Requires --yes."""
    if not args.yes:
        return {"error": "refusing without --yes (destructive)"}
    db = await cl._connect()
    try:
        result = await db.query(
            "DELETE handoff WHERE task_slug = $slug RETURN BEFORE;",
            {"slug": args.task_slug},
        )
        rows = result[0] if result else []
        return {"task_slug": args.task_slug, "deleted": len(rows)}
    finally:
        await db.close()


async def _backup(args) -> dict:
    """Export every task's handoffs to <dir>/<task_slug>.json (dated subdir)."""
    from datetime import date
    db = await cl._connect()
    try:
        result = await db.query("SELECT task_slug, count() AS n FROM handoff GROUP BY task_slug;")
        tasks = result[0] if result else []
    finally:
        await db.close()

    out_dir = Path(args.dir) / date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for row in tasks:
        slug = row["task_slug"]
        db = await cl._connect()
        try:
            result = await db.query(
                "SELECT * FROM handoff WHERE task_slug = $slug ORDER BY timestamp ASC;",
                {"slug": slug},
            )
            rows = result[0] if result else []
        finally:
            await db.close()
        target = out_dir / f"{slug}.json"
        target.write_text(json.dumps([dict(r) for r in rows], indent=2, default=str), encoding="utf-8")
        written.append({"task_slug": slug, "count": len(rows), "file": str(target)})
    return {"dir": str(out_dir), "tasks": written}


def main() -> int:
    parser = argparse.ArgumentParser(prog="handoff_cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sum = sub.add_parser("summarize")
    p_sum.add_argument("task_slug")
    p_sum.add_argument("git_branch")
    p_sum.add_argument("--transcript-file")
    p_sum.add_argument("--continues-from")
    p_sum.set_defaults(func=_summarize)

    p_res = sub.add_parser("resume")
    p_res.add_argument("task_slug")
    p_res.set_defaults(func=_resume)

    p_sync = sub.add_parser("sync")
    p_sync.add_argument("--cwd", default=os.getcwd(),
                        help="project directory to resolve the task_slug from")
    p_sync.set_defaults(func=_sync)

    p_exp = sub.add_parser("export")
    p_exp.add_argument("task_slug")
    p_exp.add_argument("--output", help="write to file instead of stdout")
    p_exp.set_defaults(func=_export)

    p_imp = sub.add_parser("import")
    p_imp.add_argument("file", help="JSON file exported by 'export'")
    p_imp.add_argument("--task-slug", help="override task_slug for all records")
    p_imp.set_defaults(func=_import)

    p_con = sub.add_parser("consolidate")
    p_con.add_argument("task_slug")
    p_con.add_argument("--git-branch", help="git branch for the consolidated handoff (default: latest handoff's branch)")
    p_con.set_defaults(func=_consolidate)

    p_chk = sub.add_parser("check")
    p_chk.add_argument("--cwd", default=os.getcwd(), help="project directory (unused, kept for symmetry)")
    p_chk.set_defaults(func=_check)

    p_for = sub.add_parser("forget")
    p_for.add_argument("task_slug")
    p_for.add_argument("--yes", action="store_true", help="confirm deletion (required)")
    p_for.set_defaults(func=_forget)

    p_bak = sub.add_parser("backup")
    p_bak.add_argument("--dir", default="backups", help="backup root dir (default: backups)")
    p_bak.set_defaults(func=_backup)

    args = parser.parse_args()
    result = asyncio.run(args.func(args))
    print(json.dumps(result, default=str))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())
