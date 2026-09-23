"""
Project identity: deterministic task_slug resolution shared by every
adapter (Claude Code, OpenCode, Copilot, generic loops, JS hooks).

Resolution order (first match wins):
  1. CONTEXT_LAYER_TASK_SLUG env var -- explicit override always wins.
  2. .context-layer.json found by walking upward from cwd -- a stable,
     deliberately-chosen slug (or UUID) meant to be committed to git so
     every clone/agent/machine agrees on the same identity.
  3. basename(cwd) -- exactly the old behavior, but logged as a warning
     so accidental reliance on the fallback is visible.

CLI:
  python -m context_layer.project_identity init [optional-task-slug]
  python -m context_layer.project_identity resolve [cwd]
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("context-layer.identity")

IDENTITY_FILE = ".context-layer.json"
ENV_OVERRIDE = "CONTEXT_LAYER_TASK_SLUG"


def resolve_task_slug(cwd: str) -> str:
    """
    Resolve the task_slug for a working directory.

    Env override wins, then the nearest .context-layer.json walking up
    from cwd. If neither exists, raises an error -- basename fallback
    is NOT provided because it causes silent identity fragmentation.
    Run `python -m context_layer.project_identity init` once per project to create the identity file.
    """
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        return override

    start = Path(cwd or os.getcwd()).resolve()
    for directory in [start, *start.parents]:
        candidate = directory / IDENTITY_FILE
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                slug = data.get("task_slug")
                if slug:
                    return slug
                logger.warning("%s exists but has no task_slug field", candidate)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("could not read %s: %s", candidate, e)

    # No identity file found - fail hard to prevent silent fragmentation
    raise RuntimeError(
        f"No {ENV_OVERRIDE} env var and no {IDENTITY_FILE} found from {start}. "
        f"Run `python -m context_layer.project_identity init [optional-slug]` in your project root "
        f"to create a stable identity, then commit {IDENTITY_FILE} to version control."
    )


def init_project_identity(cwd: str, task_slug: str | None = None) -> str:
    """
    Create .context-layer.json at cwd with a task_slug (a provided one,
    or a freshly generated UUID if none given). Meant to be run once per
    project, then committed to version control.
    """
    slug = task_slug or uuid.uuid4().hex[:12]
    target = Path(cwd or os.getcwd()).resolve() / IDENTITY_FILE
    payload = {
        "task_slug": slug,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("wrote %s with task_slug=%r", target, slug)
    return slug


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = sys.argv[1:]
    cmd = args[0] if args else "resolve"
    cwd = os.getcwd()

    if cmd == "init":
        slug = args[1] if len(args) > 1 else None
        print(init_project_identity(cwd, slug))
        return 0
    if cmd == "resolve":
        if len(args) > 1:
            cwd = args[1]
        print(resolve_task_slug(cwd))
        return 0
    print(
        f"usage: python -m context_layer.project_identity init [task-slug] | resolve [cwd]",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
