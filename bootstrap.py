#!/usr/bin/env python3
"""One-command setup for context_layer: checks surreal, creates venv,
installs deps, writes platform MCP configs + project identity.

Usage:  python bootstrap.py
After:  python mcp_server.py   (auto-starts SurrealDB + applies schema)
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
from setup_mcp import venv_python_path


def main() -> int:
    # 1. surreal binary must exist
    if not shutil.which("surreal"):
        print("MISSING: 'surreal' binary not found on PATH.")
        print("  Windows: scoop install surreal")
        print("  macOS:   brew install surrealdb/tap/surreal")
        print("  Linux:   curl -sSf https://install.surrealdb.com | sh")
        print("  Or download from https://surrealdb.com/install")
        return 1

    # 2. venv
    venv_py = venv_python_path(ROOT)
    if not venv_py.exists():
        print("[1/4] Creating venv...")
        subprocess.run([sys.executable, "-m", "venv", str(ROOT / "venv")], check=True)
    else:
        print("[1/4] venv exists, skipping")

    # 3. deps
    print("[2/4] Installing dependencies...")
    subprocess.run(
        [str(venv_py), "-m", "pip", "install", "-e", str(ROOT)],
        check=True,
    )

    # 4. platform configs + identity (run from ROOT so cwd is correct)
    print("[3/4] Writing platform MCP configs + identity...")
    subprocess.run([str(venv_py), str(ROOT / "setup_mcp.py")], cwd=str(ROOT), check=True)

    # 5. Report setup readiness without making diagnostics failure abort setup.
    print("[4/4] Checking database, migrations, embedding model, and MCP readiness...")
    diagnostics = subprocess.run(
        [str(venv_py), str(ROOT / "scripts" / "diagnostics.py")],
        cwd=str(ROOT),
        check=False,
    )
    if diagnostics.returncode != 0:
        print("Readiness checks found items needing attention; rerun scripts/diagnostics.py for details.")

    print("\nStart the MCP server (it also checks SurrealDB and applies pending schema migrations):")
    print("  python mcp_server.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
