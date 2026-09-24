# Configuration

Context Layer uses a local `.env` for service settings and a per-project identity file for grouping handoffs. Client configuration points to the installed Context Layer checkout; secrets belong in `.env`, not generated client files.

## Environment variables

Copy `.env.example` to `.env` in the Context Layer checkout. Existing process environment variables take precedence over values loaded from `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `SURREAL_URL` | `ws://127.0.0.1:8010` | SurrealDB WebSocket endpoint. |
| `SURREAL_NS` | `dev` | SurrealDB namespace. |
| `SURREAL_DB` | `context_layer` | SurrealDB database. |
| `SURREAL_USER` | `root` | Database username. |
| `SURREAL_PASS` | Must be set locally | Database password. Set before the first local database startup. |
| `CONTEXT_LAYER_API_KEY` | Empty | A key value is read by the core package, but the current MCP tool handlers do not enforce it. It does not secure the MCP server. |
| `CONTEXT_LAYER_TENANT_PREFIX` | Empty | Prefix for namespace separation. This is not an authorization boundary. |
| `CONTEXT_LAYER_TASK_SLUG` | Unset | Explicit project identity override. |
| `ANTHROPIC_API_KEY` | Unset | Enables Claude-based extraction in the automatic handoff path; without it, local rule-based extraction is used. |
| `CONTEXT_LAYER_CLAUDE_MODEL` | `claude-3-5-sonnet-20241022` | Model name for the optional Claude extraction path. |
| `SKILLS_DIRS` | Empty | OS path-separated directories searched for skill files. |

The embedding model is currently `BAAI/bge-small-en-v1.5` via FastEmbed. It is not configured by an environment variable. The model may need to download once; diagnostics do not download it unless explicitly requested.

## Project identity

All sessions that should share handoffs must use the same `task_slug`. Context Layer resolves it in this order:

1. `CONTEXT_LAYER_TASK_SLUG` in the process environment.
2. The nearest `.context-layer.json`, searching from the working directory upward.
3. Otherwise, identity resolution fails with an actionable error; it does not silently derive a slug from the folder name.

`context-layer init` creates `.context-layer.json` when needed. Example:

```json
{
  "task_slug": "my-project"
}
```

Commit this file when project clones and agents should share the same identity. Do not reuse a slug for unrelated work.

## Client configuration

Run `context-layer init` from the target project's root. With no `--client` options, it enables the project's supported integrations. Repeat `--client` to select specific clients; `--no-db` skips starting the local database. Claude Desktop is opt-in because it writes to a global user configuration location.

The initializer records client selection in `.mcp/config.json` and writes or merges client settings, hooks, and plugin files for enabled clients. Some generated configuration files contain absolute paths to the Context Layer installation and the target project. Review those files before sharing the project or using it on another machine; rerun initialization after moving the checkout.

Codex MCP server discovery may require separate CLI registration. From a terminal where Codex CLI is available, register the absolute Python and starter paths from the Context Layer checkout, then confirm registration with `codex mcp list`. Codex project hooks also require the project configuration to be trusted. Restart the client after setup.

The initializer merges supported JSON configuration where possible and reports malformed files that it cannot safely merge. Keep a backup of client settings if you have custom configuration you cannot recreate.

## Local and generated files

- `.env`: local secrets/settings; ignored by Git. Never commit credentials.
- `.context-layer.json`: project identity; usually share/commit this when collaborators need a common project memory.
- `.mcp/config.json`: enabled integrations and server command configuration; generated for the project.
- Client settings and hooks: generated or merged for enabled platforms; may include absolute paths.
- `data/handoffs.db/`: local SurrealDB data for the default startup configuration.

See [Repository map](../FOLDER_STRUCTURE.md#generated-and-local-data) for generated paths.
