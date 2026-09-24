# Context Layer

**Persistent, model-agnostic project context for AI coding agents.** Context Layer stores project handoffs in SurrealDB and exposes them through the Model Context Protocol (MCP), so compatible agents can save, find, and resume decisions and work across sessions.

> **Project status:** The default deployment is local-first and intended for development. It is not a hardened multi-user hosted service. See [security and operations](docs/operations.md) before exposing any service or storing sensitive data.

## What it provides

- Structured project handoffs with decisions, next steps, branch, content, and file references.
- Full-text, vector, and hybrid search over saved handoffs.
- Context assembly and portable Markdown capsules for bounded context windows.
- Handoff lineage and 17 MCP tools, plus a project context resource.
- Optional client lifecycle adapters for automatic checkpointing and context loading.

Context Layer stores and retrieves context explicitly provided to it. It does not synchronize complete private conversation histories across platforms. Automatic capture depends on a supported client adapter; otherwise, an agent must call the MCP tools.

## Get started

### Install Context Layer

Requirements: Python 3.12+, the SurrealDB `surreal` executable on `PATH`, and network access for initial package/model downloads.

From this repository root, create `.env` from `.env.example`, set a local database password, then run:

```powershell
python bootstrap.py
```

On Windows, bootstrap registers `context-layer` in the current user's PATH. Open a new terminal after installation. On macOS and Linux, use the virtual environment's `bin` directory or activate the environment when using the command.

### Enable it in a project

Open a terminal in the project where you want agent context and run:

```powershell
context-layer init
```

This creates a stable project identity and configures the supported project-scoped MCP clients and hooks. To configure only selected clients, pass `--client` one or more times; for example, `context-layer init --client codex --client opencode`. Add `--no-db` to write configuration without starting SurrealDB. Claude Desktop is opt-in because its configuration is user-wide: `context-layer init --client claude_desktop`.

See [Getting started](docs/getting-started.md) for platform-specific setup, verification, and troubleshooting.

## Documentation

- [Getting started](docs/getting-started.md) — install, initialize a project, connect clients, and verify readiness.
- [Configuration](docs/configuration.md) — environment variables, project identity, generated files, and client selection.
- [Architecture](docs/architecture.md) — components, data model, context flow, and current limitations.
- [MCP reference](docs/mcp-reference.md) — tools and resource with use cases.
- [Operations and security](docs/operations.md) — database, migrations, diagnostics, data handling, and troubleshooting.
- [Development](docs/development.md) — repository workflow and integration test precautions.
- [Repository map](FOLDER_STRUCTURE.md) — source tree and entry points.
- [Migration workflow](sql/migrations/README.md) — how to evolve the SurrealDB schema.
- [MCP-only agent guidance](adapters/PROACTIVE_INSTRUCTIONS.md) — instructions for clients without lifecycle hooks.

## Architecture at a glance

```text
AI agent / MCP client
        │ tools and resource (stdio)
        ▼
context_layer.server ── adapters and hooks
        │
        ▼
context_layer.core ── SurrealDB + local embeddings
```

The server exposes MCP; the core package stores and retrieves handoffs; adapters connect selected agent lifecycle events to checkpoint and resume behavior. See [Architecture](docs/architecture.md) for details and scope.

## Code graph

`graphify-out/` contains generated architecture graph data, a browser viewer, report, and supporting metadata. These checked-in artifacts can lag behind the source. Open `graphify-out/graph.html` or read `graphify-out/GRAPH_REPORT.md`; see [Repository map](FOLDER_STRUCTURE.md) for refresh and ignore details.
