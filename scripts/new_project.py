"""One-command setup for context-layer MCP in any project.

Usage: python new_project.py <project-path> [task-slug]
Writes .vscode/mcp.json + .context-layer.json, prints the 2 daily prompts.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from setup_mcp import venv_python_path
from context_layer.project_identity import init_project_identity, resolve_task_slug

PYTHON = venv_python_path(ROOT)


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("usage: python new_project.py <project-path> [task-slug]")
        return 1
    target = Path(sys.argv[1]).resolve()
    slug_arg = sys.argv[2] if len(sys.argv) > 2 else None
    (target / ".vscode").mkdir(parents=True, exist_ok=True)
    (target / ".vscode" / "mcp.json").write_text(json.dumps({"servers": {"context-layer": {
        "type": "stdio", "command": str(PYTHON), "args": ["start_mcp.py"],
        "cwd": str(ROOT), "env": {}}}}, indent=2) + "\n")
    slug = resolve_task_slug(str(target)) if not slug_arg else init_project_identity(str(target), slug_arg)
    if not slug_arg:
        from context_layer.project_identity import IDENTITY_FILE
        if not (target / IDENTITY_FILE).is_file():
            slug = init_project_identity(str(target), target.name)
    print(f"slug: {slug}\nSTART: resume handoff for {slug}\nEND: create handoff for {slug} chained to the last one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
