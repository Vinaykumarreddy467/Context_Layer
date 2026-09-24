#!/usr/bin/env python3
"""One-command setup for context_layer: checks surreal, creates venv,
installs deps, registers the CLI, and writes platform configs + project identity.

Usage:  python bootstrap.py
After:  python start_mcp.py    (checks SurrealDB, then starts MCP)
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
from setup_mcp import venv_python_path


def install_windows_cli(venv_python: Path) -> None:
    """Expose the installed CLI globally for this Windows user."""
    if sys.platform != "win32":
        print("[CLI] Automatic global command registration currently supports Windows only.")
        return

    import winreg

    launcher = venv_python.parent / "context-layer.exe"
    if not launcher.is_file():
        print(f"[CLI] Command launcher missing: {launcher}")
        return

    bin_dir = Path(os.environ.get(
        "LOCALAPPDATA", Path.home() / "AppData" / "Local"
    )) / "ContextLayer" / "bin"
    try:
        bin_dir.mkdir(parents=True, exist_ok=True)
        shim = bin_dir / "context-layer.cmd"
        shim.write_text(f'@echo off\r\n"{launcher}" %*\r\n', encoding="ascii")

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
            try:
                user_path, value_type = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                user_path, value_type = "", winreg.REG_EXPAND_SZ
            if not any(part.rstrip("\\/").casefold() == str(bin_dir).rstrip("\\/").casefold()
                       for part in user_path.split(";")):
                updated_path = f"{user_path};{bin_dir}" if user_path else str(bin_dir)
                winreg.SetValueEx(key, "Path", 0, value_type, updated_path)
    except OSError as exc:
        print(f"[CLI] Could not register the global command: {exc}")
        print(f"      Add this folder to your user PATH manually: {bin_dir}")
        return

    print(f"[CLI] Global command available as `context-layer` via {bin_dir}")
    print("      Reopen terminals for the PATH change to take effect.")


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

    # 4. Global command shim
    print("[3/5] Registering the context-layer command...")
    install_windows_cli(venv_py)

    # 5. platform configs + identity (run from ROOT so cwd is correct)
    print("[4/5] Writing platform MCP configs + identity...")
    subprocess.run([str(venv_py), str(ROOT / "setup_mcp.py")], cwd=str(ROOT), check=True)

    # 6. Report setup readiness without making diagnostics failure abort setup.
    print("[5/5] Checking database, migrations, embedding model, and MCP readiness...")
    diagnostics = subprocess.run(
        [str(venv_py), str(ROOT / "scripts" / "diagnostics.py")],
        cwd=str(ROOT),
        check=False,
    )
    if diagnostics.returncode != 0:
        print("Readiness checks found items needing attention; rerun scripts/diagnostics.py for details.")

    print("\nStart the MCP server (it also checks SurrealDB and applies pending schema migrations):")
    print("  python start_mcp.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
