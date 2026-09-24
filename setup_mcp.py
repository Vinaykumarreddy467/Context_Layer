#!/usr/bin/env python3
"""
One command: write ALL platform configs (MCP + hooks + plugin) for context-layer,
then ensure the SurrealDB backend is installed and running.

Run from any project root:
    python setup_mcp.py          # configs + DB up
    python setup_mcp.py --no-db  # configs only

Writes (merging with existing files, never clobbering):
  .mcp/config.json          single source of truth (created if missing)
  .vscode/mcp.json          VS Code
  .cursor/mcp.json          Cursor
  opencode.json(c)          OpenCode / OpenWork (merged)
  .claude/settings.json     Claude Code
  ~/.config/claude-desktop/claude_desktop_config.json   Claude Desktop (global)
  copilot-hooks.json        Copilot (merged; wires checkpoint + resume hooks)
  .codex/hooks.json         Codex (loads context at startup; saves on compact/end)
  hooks/context-layer-*.js  deployed from this repo
  .opencode/plugins/context-layer.ts   deployed from this repo

Restart editors afterwards: MCP servers are spawned at client start.
"""
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def venv_python_path(root: Path, system: str | None = None) -> Path:
    """Return the virtualenv interpreter path for the current platform."""
    system = system or platform.system()
    if system == "Windows":
        return root / "venv" / "Scripts" / "python.exe"
    return root / "venv" / "bin" / "python"


def claude_desktop_config_path(system: str | None = None) -> Path:
    """Return Claude Desktop's per-user config path for the current OS."""
    system = system or platform.system()
    if system == "Windows":
        roaming = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return roaming / "Claude" / "claude_desktop_config.json"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


VENV_PYTHON = str(venv_python_path(ROOT))

SERVER_CFG = {
    "name": "context-layer",
    "type": "stdio",
    "command": VENV_PYTHON,
    "args": [str(ROOT / "start_mcp.py")],
    "cwd": str(ROOT),
    # Secrets and DB settings are loaded from the project .env by the server.
    # Keep them out of generated client configuration files.
    "env": {},
}
PLATFORM_DEFAULTS = {
    "vscode": True, "cursor": True, "opencode": True,
    "claude_code": True, "claude_desktop": False, "copilot": True,
    "codex": True,
}


def _read_json_object(path: Path, default: dict) -> dict:
    """Read a config object without silently replacing malformed user config."""
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot safely merge {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Cannot safely merge {path}: expected a JSON object")
    return data


def load_or_create_config(project_root: Path):
    cfg_file = project_root / ".mcp" / "config.json"
    if cfg_file.exists():
        cfg = json.loads(cfg_file.read_text())
        server = {**SERVER_CFG, **cfg.get("server", {})}
        needs_write = False
        configured_args = server.get("args", [])
        if configured_args and Path(configured_args[0]).name == "mcp_server.py":
            server["args"] = [str(project_root / "start_mcp.py")]
            cfg.setdefault("server", {})["args"] = server["args"]
            needs_write = True
        if server.get("env"):
            server["env"] = {}
            cfg.setdefault("server", {})["env"] = {}
            needs_write = True
        if needs_write:
            cfg.setdefault("server", {})["args"] = server["args"]
            cfg["server"]["env"] = {}
            cfg_file.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        server["env"] = {}
        slug = cfg.get("identity", {}).get("task_slug", "")
        platforms = {**PLATFORM_DEFAULTS, **cfg.get("platforms", {})}
        return cfg_file, server, slug, platforms
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(json.dumps({
        "server": SERVER_CFG,
        "identity": {"task_slug": ""},
        "platforms": PLATFORM_DEFAULTS,
    }, indent=2) + "\n")
    print(f"  [CREATED] {cfg_file.relative_to(project_root)} (edit for custom paths)")
    server = {**SERVER_CFG, "env": {}}
    return cfg_file, server, "", PLATFORM_DEFAULTS


def write_vscode(project_root: Path, server: dict):
    d = project_root / ".vscode"
    d.mkdir(parents=True, exist_ok=True)
    target = d / "mcp.json"
    data = _read_json_object(target, {})
    servers = data.setdefault("servers", {})
    if not isinstance(servers, dict):
        raise RuntimeError(f"Cannot safely merge {target}: 'servers' must be an object")
    servers[server["name"]] = {
        "type": server["type"], "command": server["command"], "args": server["args"],
        "cwd": server["cwd"], "env": server["env"],
    }
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"  [OK] .vscode/mcp.json")


def write_cursor(project_root: Path, server: dict):
    d = project_root / ".cursor"
    d.mkdir(parents=True, exist_ok=True)
    target = d / "mcp.json"
    data = _read_json_object(target, {})
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise RuntimeError(f"Cannot safely merge {target}: 'mcpServers' must be an object")
    servers[server["name"]] = {
        "type": server["type"], "command": server["command"], "args": server["args"],
        "cwd": server["cwd"], "env": server["env"],
    }
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"  [OK] .cursor/mcp.json")


def write_opencode(project_root: Path, server: dict):
    target = next((project_root / n for n in ("opencode.jsonc", "opencode.json")
                   if (project_root / n).exists()), project_root / "opencode.json")
    data = _read_json_object(target, {})
    mcp = data.setdefault("mcp", {})
    if not isinstance(mcp, dict):
        raise RuntimeError(f"Cannot safely merge {target}: 'mcp' must be an object")
    mcp[server["name"]] = {
        "type": "local",
        "command": [server["command"], *server["args"]],
        "environment": server["env"],
        "enabled": True,
    }
    target.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  [OK] {target.relative_to(project_root)} (merged)")


def write_claude_code(project_root: Path, server: dict):
    d = project_root / ".claude"
    d.mkdir(parents=True, exist_ok=True)
    target = d / "settings.json"
    data = _read_json_object(target, {})
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise RuntimeError(f"Cannot safely merge {target}: 'mcpServers' must be an object")
    servers[server["name"]] = {
        "command": server["command"], "args": server["args"], "env": server["env"],
    }
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"  [OK] .claude/settings.json")


def write_claude_desktop(server: dict):
    cfg = claude_desktop_config_path()
    cfg.parent.mkdir(parents=True, exist_ok=True)
    data = _read_json_object(cfg, {"mcpServers": {}})
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise RuntimeError(f"Cannot safely merge {cfg}: 'mcpServers' must be an object")
    servers[server["name"]] = {
        "command": server["command"], "args": server["args"], "env": server["env"],
    }
    cfg.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  [OK] {cfg}")


def write_copilot_hooks(project_root: Path):
    target = project_root / "copilot-hooks.json"
    data = {"version": 1, "hooks": {"sessionStart": [], "userPromptSubmitted": []}}
    if target.exists():
        try:
            data = json.loads(target.read_text())
        except Exception:
            pass
    data.setdefault("hooks", {})
    data["hooks"].setdefault("sessionStart", [])
    data["hooks"].setdefault("userPromptSubmitted", [])
    resume = {"type": "command",
              "bash": 'node "${PLUGIN_ROOT}/hooks/context-layer-handoff.js" --resume-auto',
              "powershell": 'node "${PLUGIN_ROOT}\\hooks\\context-layer-handoff.js" --resume-auto',
              "timeoutSec": 10}
    checkpoint = {"type": "command",
                  "bash": 'node "${PLUGIN_ROOT}/hooks/context-layer-checkpoint.js"',
                  "powershell": 'node "${PLUGIN_ROOT}\\hooks\\context-layer-checkpoint.js"',
                  "timeoutSec": 10}
    if not any("context-layer-handoff" in str(e.get("bash", ""))
               for e in data["hooks"]["sessionStart"]):
        data["hooks"]["sessionStart"].append(resume)
    if not any("context-layer-checkpoint" in str(e.get("bash", ""))
               for e in data["hooks"]["userPromptSubmitted"]):
        data["hooks"]["userPromptSubmitted"].append(checkpoint)
    target.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  [OK] copilot-hooks.json (merged)")


def write_codex_hooks(project_root: Path):
    """Install project-scoped Codex lifecycle hooks for context handoffs."""
    target = project_root / ".codex" / "hooks.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    data = {"hooks": {}}
    if target.exists():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    hooks = data.setdefault("hooks", {})
    command = f'"{VENV_PYTHON}" "{ROOT / "adapters" / "codex" / "hook.py"}"'
    for event, matcher in (("SessionStart", "startup|resume|compact"),
                           ("PreCompact", ".*"), ("SessionEnd", None)):
        groups = hooks.setdefault(event, [])
        if any("adapters\\codex\\hook.py" in str(group)
               or "adapters/codex/hook.py" in str(group) for group in groups):
            continue
        group = {"hooks": [{"type": "command", "command": command,
                            "statusMessage": "Loading Context Layer context"
                            if event == "SessionStart" else "Saving Context Layer handoff"}]}
        if matcher is not None:
            group["matcher"] = matcher
        groups.append(group)
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("  [OK] .codex/hooks.json")


def deploy_hooks_and_plugin(project_root: Path):
    hooks_dir = project_root / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for name in ("context-layer-checkpoint.js", "context-layer-handoff.js"):
        src = ROOT / "hooks" / name
        if not src.exists():
            continue
        dst = hooks_dir / name
        if not dst.exists() or dst.read_text() != src.read_text():
            dst.write_text(src.read_text())
            print(f"  [OK] hooks/{name}")
    plugin_dir = project_root / ".opencode" / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    src = ROOT / "adapters" / "opencode" / "context-layer-plugin.ts"
    dst = plugin_dir / "context-layer.ts"
    text = (src.read_text()
            .replace("__CONTEXT_LAYER_DIR__", ROOT.as_posix())
            .replace("__CHECKPOINT_JS__", str(hooks_dir / "context-layer-checkpoint.js")))
    if not dst.exists() or dst.read_text() != text:
        dst.write_text(text)
        print(f"  [OK] .opencode/plugins/context-layer.ts")


def ensure_identity(project_root: Path, slug: str):
    idf = project_root / ".context-layer.json"
    if idf.exists():
        try:
            current = json.loads(idf.read_text()).get("task_slug")
            if current:
                print(f"  [OK] existing slug: {current}")
                return
        except Exception:
            pass
    from context_layer.project_identity import init_project_identity
    final = init_project_identity(str(project_root), slug or project_root.name)
    print(f"  [OK] .context-layer.json -> slug: {final}")


def main():
    project_root = Path.cwd()
    cfg_file, server, slug, platforms = load_or_create_config(project_root)

    if not os.path.isabs(server["cwd"]):
        server["cwd"] = str(project_root / server["cwd"])
    if not os.path.isabs(server["command"]):
        server["command"] = str(project_root / server["command"])

    if platforms.get("vscode"):
        write_vscode(project_root, server)
    if platforms.get("cursor"):
        write_cursor(project_root, server)
    if platforms.get("opencode"):
        write_opencode(project_root, server)
    if platforms.get("claude_code"):
        write_claude_code(project_root, server)
    if platforms.get("claude_desktop"):
        write_claude_desktop(server)
    if platforms.get("copilot"):
        write_copilot_hooks(project_root)
    if platforms.get("codex"):
        write_codex_hooks(project_root)

    deploy_hooks_and_plugin(project_root)
    ensure_identity(project_root, slug)

    if "--no-db" not in sys.argv:
        print("\n[DB] ensuring SurrealDB backend...")
        start_db_script = ROOT / "scripts" / "start_db.py"
        if not start_db_script.is_file():
            raise FileNotFoundError(f"SurrealDB startup script not found: {start_db_script}")
        if not Path(VENV_PYTHON).is_file():
            raise FileNotFoundError(
                f"Project virtualenv Python not found: {VENV_PYTHON}. Run bootstrap.py first."
            )
        subprocess.run([VENV_PYTHON, str(start_db_script)], check=True)

    print("\nDone. Restart all editors / run 'MCP: List Servers' in VS Code.")
    print("Run `python scripts/diagnostics.py` to check database, migrations, embeddings, and MCP readiness.")


if __name__ == "__main__":
    main()
