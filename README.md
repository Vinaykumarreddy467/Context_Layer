# Context Layer

Context Layer is a local-first memory service for AI-assisted software work. It stores project handoffs in SurrealDB and exposes them through MCP so compatible agents can save, search, and resume context across sessions.

> **Deployment scope:** The default setup is intended for local development. Before using it as a shared or production service, configure database credentials, access controls, backups, retention, and a deployment model appropriate to your environment. See [Security and operations](#security-and-operations).

## What it does

- Stores handoffs with a project identity, branch, decisions, next steps, transcript text, and extracted file references.
- Searches handoffs with full-text, vector, or hybrid retrieval.
- Connects handoffs with `continues_from` lineage edges.
- Assembles context to a requested token budget and exports portable Markdown capsules.
- Exposes 17 MCP tools and the `context://current/{task_slug}` resource.
- Includes adapters for selected coding agents and a generic integration pattern.

The system captures and retrieves project context; it does not automatically synchronize private model conversation histories across every AI platform. Automatic capture depends on each client’s adapter or on the agent calling MCP tools.

## Architecture

```text
Coding agent / MCP client
       │ MCP tools and resource
       ▼
context_layer.server ─── adapter hooks ─── auto_handoff
       │                                    │
       └──────────── core storage API ──────┘
                            │
                            ▼
                 SurrealDB + local embeddings
```

- `context_layer/core.py` contains storage, search, lineage, context assembly, and token budgeting.
- `context_layer/server.py` exposes the MCP tools and starts SurrealDB/migrations when launched normally.
- `context_layer/auto_handoff.py` extracts a structured summary and persists the handoff. It uses the local rule-based extractor by default and can use Claude when `ANTHROPIC_API_KEY` is configured.
- `adapters/` contains client-specific lifecycle integrations.

## Requirements

- Python 3.12 or newer.
- SurrealDB 3.x, with the `surreal` executable available on `PATH`.
- Network access to install Python packages. The local embedding model may also need to be downloaded on first use; after it is cached, embeddings run locally.

## Quick start

### Windows PowerShell

From the project root:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
# Edit .env and replace the local database password placeholder.
python bootstrap.py
.\venv\Scripts\Activate.ps1
python start_mcp.py
```

### macOS or Linux

From the project root:

```bash
test -f .env || cp .env.example .env
# Edit .env and replace the local database password placeholder.
python3 bootstrap.py
source venv/bin/activate
python start_mcp.py
```

`bootstrap.py` checks for SurrealDB, creates the virtual environment if needed, installs the package, registers the `context-layer` command in the Windows user PATH, generates client files and project identity, starts the database, and runs readiness diagnostics. Reopen terminals after bootstrap so they load the updated PATH. On macOS/Linux, activate the virtual environment or add its `bin` directory to PATH manually. The default diagnostic pass checks for a locally cached embedding model without downloading one. The MCP server starts SurrealDB if it is not already reachable and applies pending migrations.

Configured `stdio` clients normally launch the MCP server as a child process; in that case, do not start a second copy manually. To run it directly for development or diagnosis, use `python start_mcp.py` from the project root and keep that terminal open. The starter checks SurrealDB first, starts the local database when possible, and prints a clear recovery message to stderr if the database or configuration is not ready. When it reports that it is waiting for an MCP client, that is normal: do not type into that terminal; connect a configured MCP client or press Ctrl+C to stop. MCP protocol output stays on stdout.

### Manual setup

If you prefer to configure each step yourself:

```bash
test -f .env || cp .env.example .env
# Edit .env and replace the local database password placeholder.
python -m venv venv
# Activate the environment for your shell, then:
python -m pip install -e .
python setup_mcp.py --no-db
python start_mcp.py
```

Install SurrealDB before running the server. `setup_mcp.py --no-db` writes the client configurations without starting the database. Running `setup_mcp.py` without `--no-db` also ensures the local database is running.

## Connecting an MCP client

For another project, open a terminal in that project's root and run the Context Layer command. By default it configures every project-scoped client integration. Install Context Layer in editable mode once in its virtual environment to register the `context-layer` command. Activate that environment in the terminal where you run the command (or add its `Scripts`/`bin` directory to your user `PATH` once):

```powershell
# One time, from the Context Layer checkout (with its venv active):
python -m pip install -e .

# For each project, from that project's root:
context-layer init
```

It creates or updates project settings for VS Code, Cursor, OpenCode, Claude Code, Copilot, and Codex, and saves the selection in the project's ignored `.mcp/config.json`. Use `--client codex` to configure just one client; repeat `--client` for multiple clients. Claude Desktop is opt-in with `--client claude_desktop` because its configuration is global and written outside the project. Add `--no-db` to skip starting SurrealDB. Keep the Context Layer checkout in place; generated client settings point to its installation path.

`setup_mcp.py` generates configuration for the clients enabled in `.mcp/config.json`. Generated settings use the project's virtual environment and the `start_mcp.py` launcher, which reports database startup problems on stderr without mixing messages into MCP protocol output.

For Codex, the setup script configures this project’s lifecycle hooks in `.codex/hooks.json`. Register the MCP server with Codex separately, for example:

```powershell
codex mcp add context-layer -- "C:\path\to\context_layer\venv\Scripts\python.exe" "C:\path\to\context_layer\start_mcp.py"
codex mcp list
```

Replace the example paths with the absolute paths to this checkout. Codex project hooks run only when the project configuration is trusted. Restart or open a new session after configuration changes.

For other generated client files, run `python setup_mcp.py` and follow that client’s procedure for refreshing MCP servers. Review generated files before using them in a different project or machine; they can contain machine-specific absolute paths.

## Project identity

Handoffs are grouped by `task_slug`. Every agent that should share a project’s memory must resolve to the same slug.

Resolution order:

1. `CONTEXT_LAYER_TASK_SLUG`, if set.
2. The nearest `.context-layer.json`, searched from the working directory upward.
3. If neither exists, resolution fails with an actionable error; there is no silent directory-name fallback.

The setup script creates `.context-layer.json` if it is missing. Commit that file when clones and agents should share the same project identity. Do not reuse a slug for unrelated projects.

Example:

```json
{
  "task_slug": "my-project"
}
```

## MCP interface

### Save and update handoffs

| Tool | Purpose |
|---|---|
| `create_handoff` | Store structured decisions, next steps, and content. |
| `auto_summarize_handoff` | Extract a summary, decisions, and next steps from a transcript and store it. |
| `append_next_step` | Add a next step to an existing handoff. |
| `close_handoff` | Mark a handoff as complete. |

### Find and resume context

| Tool | Purpose |
|---|---|
| `resume_handoff` | Return the latest handoff and mark it resumed. |
| `search_handoffs` | Full-text search, optionally scoped to a project. |
| `semantic_search_handoffs` | Vector search for related meaning. |
| `hybrid_search_handoffs` | Combine full-text and vector search. |
| `find_handoffs_by_file` | Find handoffs referencing a path or filename. |
| `get_handoff_lineage` | Trace predecessor and successor handoffs. |

### Assemble and export context

| Tool | Purpose |
|---|---|
| `context_for_window` | Assemble prioritized project context under a token budget. |
| `get_context_capsule` | Export a portable Markdown context primer. |
| `summarize_for_window` | Compress context when it exceeds a target budget. |
| `token_budget_report` | Report context token usage and recommendations. |

### Project and skill helpers

| Tool | Purpose |
|---|---|
| `ensure_project_ready` | Create missing project identity and VS Code MCP configuration. |
| `list_skills` | List skill packs found in configured skill directories. |
| `get_skill` | Read one skill pack’s `SKILL.md`. |

The server also exposes `context://current/{task_slug}`, which returns assembled context for the specified project.

## Adapters

| Client or pattern | Adapter | Capture or resume behavior |
|---|---|---|
| Codex | `adapters/codex/hook.py` | Loads context at session start; captures before compaction and at session end. Project hooks are registered by `setup_mcp.py`. |
| Claude Code | `hooks/pre_compact.py` | Captures at `PreCompact` when configured as a Claude Code hook. |
| VS Code Copilot | `adapters/copilot/pre_compact.py` | Pre-compaction adapter; the project notes that this client hook format is less fully specified. |
| OpenCode | `adapters/opencode/compaction-plugin.ts` and `context-layer-plugin.ts` | Integrates with OpenCode session/compaction lifecycle. |
| Custom Python agent | `adapters/generic_loop.py` and `context_layer/trigger.py` | Example integration that checkpoints when a token threshold is reached. |
| MCP-only clients | `adapters/PROACTIVE_INSTRUCTIONS.md` | Instructions for agent-initiated checkpointing; this is not an automatic lifecycle hook. |

Hook transcript formats are client-defined and may change. Adapters should fail without interrupting the host client’s work. Review and trust local hook configuration in the client before enabling it.

## Configuration

Copy `.env.example` to `.env` and set local values before starting the database or MCP server. `.env` is ignored by Git; database connection settings and API credentials are read from it and are not copied into generated MCP client configuration files. Existing process environment variables take precedence over `.env`.

The local configuration variables are:

| Variable | Default | Description |
|---|---|---|
| `SURREAL_URL` | `ws://127.0.0.1:8010` | SurrealDB WebSocket endpoint. |
| `SURREAL_NS` | `dev` | SurrealDB namespace. |
| `SURREAL_DB` | `context_layer` | SurrealDB database. |
| `SURREAL_USER` | `root` | Database username. |
| `SURREAL_PASS` | Set in `.env` | Database password. |
| `CONTEXT_LAYER_TENANT_PREFIX` | empty | Prefix added to the namespace for tenant separation. |
| `CONTEXT_LAYER_TASK_SLUG` | unset | Optional project identity override. |
| `SKILLS_DIRS` | empty | OS path-separated directories containing `SKILL.md` files. |
| `ANTHROPIC_API_KEY` | unset | Enables Claude-based extraction for automatic transcript summarization. Without it, local rules are used. |
| `CONTEXT_LAYER_CLAUDE_MODEL` | `claude-3-5-sonnet-20241022` | Model override for the optional Claude extraction path. |

The MCP server loads these values from `.env` or its process environment. Keep credentials in `.env`; generated MCP client configurations intentionally contain no database passwords or API keys.

## Data and migrations

SurrealDB data is stored in `data/handoffs.db` by the default startup path. The versioned schema migrations live in `sql/migrations/` and are applied when the MCP server starts. See [sql/migrations/README.md](sql/migrations/README.md) before adding or manually applying a migration.

Handoffs include structured fields and retained `raw_content`. Treat the database as project data: protect it, include it in backup planning, and avoid sending secrets or unrelated sensitive conversation text into handoffs.

## Security and operations

The database launcher binds SurrealDB to `127.0.0.1`. Set a local password in `.env` before the first startup; do not expose the local listener to a network. For shared deployment, define an authentication and authorization boundary, use non-default credentials, restrict network access, and establish backup, restore, retention, and upgrade procedures.

`CONTEXT_LAYER_TENANT_PREFIX` helps separate namespaces, but it is not a substitute for authorization or a complete multi-tenant security design. The default setup is local-first and should not be treated as a hardened hosted service.

## Development and verification

The files in `tests/` are executable integration scripts, not a conventional pytest suite. Several start the MCP server, write handoffs, and use the configured database. Use a disposable database when running them.

Examples:

```bash
python tests/test_mcp_e2e.py
python tests/test_mcp_semantic.py
python tests/test_migrations.py
```

The MCP end-to-end scripts need the project dependencies and a reachable SurrealDB instance. Some exercises also load the local embedding model. These scripts can write persistent test records.

### Readiness diagnostics

Run this after setup or when a client cannot connect:

```bash
python scripts/diagnostics.py
```

The command reports database authentication/connectivity, applied and pending migrations, whether the configured FastEmbed model can produce a local vector, and whether the configured MCP server completes `initialize` and `tools/list` over stdio. It exits with code `0` only when all four checks are ready. If the model is not cached, download it explicitly while online with:

```bash
python scripts/diagnostics.py --download-model
```

Use `--timeout 180` to allow more time for a cold model load or slow MCP startup, and `--json` for machine-readable output. Model download is opt-in. If database, migration, or embedding checks are not ready, the MCP handshake is marked `BLOCKED` and skipped. The MCP check launches the server configured in `.mcp/config.json`; normal server startup behavior applies.

## Repository layout

See [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md) for the source tree and entry points.

## Code graph

`graphify-out/` contains the generated project graph, interactive HTML viewer, report, manifest, token-cost summary, and reviewed community labels. These portable outputs are checked in so contributors can inspect the architecture without installing Graphify. To refresh them, run `/graphify --update` in a Graphify-enabled assistant; the command updates the graph and project documentation. Review the resulting diff before committing. Local Graphify caches, backups, signatures, and machine-specific interpreter/root metadata are ignored.

Open `graphify-out/graph.html` in a browser to explore the graph, or read `graphify-out/GRAPH_REPORT.md` for a text summary. The graph is generated analysis and can lag behind source changes until refreshed.
