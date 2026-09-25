# Architecture

Context Layer provides durable handoffs to MCP-compatible agents. An agent or lifecycle adapter sends useful project state to the MCP server; the server stores and searches it; a later session requests a bounded context bundle.

## Component map

```text
Coding agent / MCP client
       │ MCP over stdio
       ▼
context_layer.server ───── client adapters and hooks
       │                              │
       ▼                              └── checkpoint/resume calls
context_layer.core
       │
       ├── SurrealDB: records, full-text index, vector index, lineage
       └── FastEmbed: local text embeddings
```

- **MCP server** (`context_layer/server.py`): declares tools and a project context resource; ensures the configured local SurrealDB is reachable and applies pending migrations during startup.
- **Core API** (`context_layer/core.py`): manages handoffs, full-text/vector/hybrid retrieval, lineage, context assembly, token budgeting, and references.
- **Project identity** (`context_layer/project_identity.py`): maps sessions to a stable `task_slug` from an environment override or `.context-layer.json`.
- **Handoff extraction** (`context_layer/auto_handoff.py`): extracts structured decisions and next steps using local rules by default, with an optional Claude API path.
- **Adapters** (`adapters/`, `hooks/`): connect supported host events to context loading or checkpointing. Each adapter depends on that host's event and payload format.

## Handoff data

A handoff is a durable checkpoint associated with a project slug. The current schema includes timestamps, branch, status, decisions, next steps, raw content, summary, platform session metadata, token count, compaction flag, schema version, extracted files/references, and embedding. A `continues_from` relation can connect successive handoffs. Versioned SurrealQL migrations are under `sql/migrations/`; the `version` field is set by migration `0002` and defaults to 1.

`create_handoff` guards against duplicate checkpoints: a record with identical raw content (or the same platform session id) created within 60 seconds is skipped and the existing record is returned, so double-firing lifecycle events (for example PreCompact plus SessionEnd) do not create duplicate history. Capsule export includes the handoff's `version` as `capsule_version`.

The database stores user/agent-provided handoff text. Do not include credentials or unrelated sensitive conversation content. The embedding model runs locally after it has been obtained, but optional Claude extraction sends its transcript input to Anthropic when configured and used.

## Retrieval and context assembly

Agents can search by text, semantic similarity, or a hybrid method. Context assembly ranks available project context and fits it to a requested token budget; capsule export produces portable Markdown. The model receives only the context returned or read by the integration. Context Layer does not intercept or synchronize all platform conversations by itself.

## Automatic capture scope

Automatic behavior requires a client integration that invokes Context Layer at lifecycle points such as session start, before compaction, or session end. Hook formats and event guarantees differ across clients and can change. MCP-only clients rely on the agent following instructions to checkpoint manually. See the adapter summary in the [MCP reference](mcp-reference.md#client-adapters).

## Current deployment boundary

The supported default is one local development setup with local SurrealDB. Tenant prefixes organize namespaces but do not provide authorization isolation. Before shared or hosted deployment, the application needs a reviewed authentication/authorization model, network controls, backup and restore procedures, retention policy, and operational monitoring. See [Operations and security](operations.md).

