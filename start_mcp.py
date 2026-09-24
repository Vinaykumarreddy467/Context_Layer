#!/usr/bin/env python3
"""Start Context Layer, check SurrealDB, and serve MCP over stdio."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _project_python() -> Path:
    if os.name == "nt":
        return ROOT / "venv" / "Scripts" / "python.exe"
    return ROOT / "venv" / "bin" / "python"


def main() -> int:
    project_python = _project_python()
    if project_python.is_file():
        current_python = Path(sys.executable).resolve()
        if os.path.normcase(str(current_python)) != os.path.normcase(str(project_python.resolve())):
            return subprocess.call([str(project_python), str(Path(__file__).resolve()), *sys.argv[1:]])

    try:
        from context_layer.server import main as serve
    except ModuleNotFoundError as exc:
        missing = exc.name or "a required package"
        print(f"\n🚧 Context Layer is missing the Python dependency `{missing}`.", file=sys.stderr)
        print("   Run `python bootstrap.py` from the project folder, then retry `python start_mcp.py`.",
              file=sys.stderr)
        return 1

    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
