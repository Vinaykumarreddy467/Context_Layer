"""
CLI for the context layer, so non-MCP callers (IDE hooks, opencode plugins,
shell scripts) can auto-summarize and resume handoffs.

Usage:
  python handoff_cli.py summarize <task_slug> <git_branch> [--transcript-file <path>] [--continues-from <id>]
  python handoff_cli.py resume <task_slug>

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
from context_layer import auto_handoff


async def _summarize(args) -> dict:
    if args.transcript_file:
        with open(args.transcript_file, encoding="utf-8") as f:
            transcript = f.read()
    else:
        transcript = sys.stdin.read()
    if not transcript.strip():
        return {"error": "empty transcript"}
    return await auto_handoff.summarize_and_store(
        transcript, args.task_slug, args.git_branch, args.continues_from
    )


async def _resume(args) -> dict:
    handoff = await cl.resume_handoff(args.task_slug)
    if not handoff:
        return {"error": f"no handoff for task '{args.task_slug}'"}
    return handoff


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

    args = parser.parse_args()
    result = asyncio.run(args.func(args))
    print(json.dumps(result, default=str))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())
