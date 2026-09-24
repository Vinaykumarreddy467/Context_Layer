# Getting started

This guide separates installing the Context Layer service from enabling it in an agent project. Install once from the Context Layer checkout; initialize each project that should share context.

## Requirements

- Python 3.12 or newer.
- SurrealDB 3.x, with the `surreal` executable available on `PATH`.
- Network access to install Python dependencies. FastEmbed may download its embedding model on first use.

## Install the service

From the Context Layer repository root, create a local environment file and set a local database password:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
# Edit .env before the first database startup.
python bootstrap.py
```

On Windows, bootstrap installs the package in `venv`, creates a user-level command shim, adds its directory to the current user's PATH, configures the checkout, starts SurrealDB, and runs readiness diagnostics. Reopen terminals for the updated PATH to take effect. The command is registered for the current Windows user, not for every account on the machine.

On macOS/Linux:

```bash
test -f .env || cp .env.example .env
# Edit .env before the first database startup.
python3 bootstrap.py
source venv/bin/activate
```

The command is available while the virtual environment is active. To use it from other shells, add that environment's `bin` directory to your user PATH.

## Initialize a project

Change to the root of the project that should use Context Layer, then run:

```text
context-layer init
```

By default this enables project-scoped integrations for VS Code, Cursor, OpenCode, Claude Code, Copilot, and Codex, creates `.context-layer.json` if needed, records the platform selection in `.mcp/config.json`, and ensures the local database is running. The Context Layer checkout must remain at its installed location because generated MCP commands refer to it by absolute path.

Select clients explicitly when useful:

```text
context-layer init --client codex --client opencode
context-layer init --no-db
context-layer init --client claude_desktop
```

`--client` can be repeated. Claude Desktop is opt-in because it modifies a user-wide configuration. `--no-db` writes project/client configuration without starting SurrealDB.

## Connect and verify

Restart or reload the target editor/client after configuration. Some clients require explicit MCP server approval or project trust. Codex MCP registration and Codex project hook trust are distinct; see [Configuration](configuration.md#client-configuration) for the Codex procedure.

From the Context Layer checkout, run the readiness check:

```text
python scripts/diagnostics.py
```

It reports database connectivity/authentication, migration state, local embedding model readiness, and an MCP stdio handshake. Use `--download-model` to allow an uncached embedding model to download, `--timeout 180` for slower initial loading, or `--json` for machine-readable output. A successful diagnostic does not replace restarting the client after configuration changes.

## Run the MCP server directly

Normally, an MCP client starts the configured server as a child process; do not run a second copy for that same client. For development or diagnosis, start it manually from the Context Layer checkout:

```text
python start_mcp.py
```

Keep that terminal open, connect a client configured for a separate server process as appropriate, or press Ctrl+C to stop. A message that the process is waiting for an MCP client is expected. Do not type into the terminal: MCP uses stdin/stdout, and startup messages go to stderr.

## Manual installation

If you do not want bootstrap to run the complete setup, create `.env`, create and activate a virtual environment, and install the package:

```text
python -m venv venv
python -m pip install -e .
python setup_mcp.py --no-db
```

Install and start SurrealDB separately. The standalone `setup_mcp.py` command writes configuration for the current working project; `--no-db` skips database startup.

## Common setup issues

- **`context-layer` is not recognized:** On Windows, reopen the terminal after bootstrap and check that `%LOCALAPPDATA%\ContextLayer\bin` is in the user PATH. On macOS/Linux, activate the installed virtual environment or add its `bin` directory to PATH.
- **Database is not ready:** Check that SurrealDB is installed and on PATH, `.env` has a password, and `SURREAL_URL`, namespace, and database match the running server. Run `python scripts/diagnostics.py` from the checkout.
- **Client cannot find the MCP server:** Re-run `context-layer init` from the target project's root, review the generated client settings, and restart/reload the client.
- **Project identity missing:** Run `context-layer init` in the project or set `CONTEXT_LAYER_TASK_SLUG` explicitly.

