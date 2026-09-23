# Repository structure

This document describes the current source tree. Generated configuration, local databases, virtual environments, caches, and reports may be present in a developer checkout but are not application source.

```text
context_layer/
├── context_layer/                    # Installable Python package
│   ├── __init__.py                   # Public core API
│   ├── core.py                       # SurrealDB access, handoffs, search, context assembly
│   ├── server.py                     # FastMCP server, tools, resources, startup
│   ├── auto_handoff.py               # Transcript extraction and handoff persistence
│   ├── export_capsule.py             # Portable Markdown context export
│   ├── project_identity.py           # Stable task_slug resolution
│   └── trigger.py                    # Token-budget checkpoint trigger
├── adapters/                         # Agent and framework integrations
│   ├── codex/hook.py                 # Codex SessionStart/PreCompact/SessionEnd hooks
│   ├── copilot/                      # VS Code Copilot adapter
│   ├── opencode/                     # OpenCode hooks and plugins
│   ├── generic_loop.py               # Framework integration examples
│   └── PROACTIVE_INSTRUCTIONS.md     # Guidance for MCP-only clients
├── hooks/                            # Claude Code hook and shared JS client hooks
│   ├── pre_compact.py
│   ├── context-layer-checkpoint.js
│   └── context-layer-handoff.js
├── scripts/                          # Setup, launch, migration, and CLI utilities
│   ├── start_db.py
│   ├── run_migrations.py
│   ├── diagnostics.py                 # Database, schema, embedding, and MCP readiness checks
│   ├── run_mcp.py
│   ├── run_mcp.ps1
│   ├── handoff_cli.py
│   ├── new_project.py
│   └── backfill_refs.py
├── sql/
│   ├── migrations/                   # Versioned migrations applied by the server
│   └── 001_schema.surql              # Human-readable schema/query reference
├── tests/                            # Executable integration scripts
├── mcp_server.py                     # Compatibility launcher
├── setup_mcp.py                      # Generate supported client configurations
├── bootstrap.py                      # First-time local setup
├── pyproject.toml                    # Package metadata and dependencies
├── requirements.txt                  # Runtime dependency list
├── README.md                         # Product, setup, and operating guide
└── FOLDER_STRUCTURE.md               # This file
```

## Entry points

Run commands from the project root unless noted otherwise.

| Command | Purpose |
|---|---|
| `python bootstrap.py` | Check prerequisites, install the package, generate client configs and identity, and start the local database. |
| `python mcp_server.py` | Start the MCP server; normally ensures SurrealDB is running and applies pending migrations. |
| `python -m context_layer.server` | Start the package server directly. |
| `python setup_mcp.py --no-db` | Generate configured client files without starting SurrealDB. |
| `python scripts/run_migrations.py --status` | Show migration status; SurrealDB must already be running. |
| `python scripts/diagnostics.py` | Check database, migrations, local embedding model, and MCP stdio readiness. |
| `python scripts/handoff_cli.py summarize ...` | Summarize a transcript and store a handoff. |
| `python scripts/handoff_cli.py resume <task_slug>` | Fetch and mark the latest handoff as resumed. |

## Generated and local data

The following paths are local runtime or generated data, not source modules:

- `venv/` — local Python environment created by bootstrap.
- `data/handoffs.db/` — default SurrealDB RocksDB store.
- `.mcp/`, `.vscode/`, `.cursor/`, `.claude/`, `.codex/`, and `opencode.json` — client configuration; some files contain local absolute paths.
- `.context-layer.json` — project identity. Commit this file when clones should share one `task_slug`.
- `.opencode/`, `copilot-hooks.json`, and `graphify-out/` — generated plugin, hook, or analysis output where present.

Review generated configuration before sharing it. Keep credentials and machine-specific paths out of public source control.

## Schema files

`sql/migrations/` is the versioned migration source used by the MCP server at startup. `sql/001_schema.surql` is a reference file for manual inspection and query examples; the server does not apply it as a migration. See [sql/migrations/README.md](sql/migrations/README.md).
