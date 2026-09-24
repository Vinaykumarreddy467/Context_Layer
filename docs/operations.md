# Operations and security

The default configuration is a local development service. This guide covers startup, readiness, migrations, data handling, and common recovery steps.

## Startup and database

`python start_mcp.py` starts the MCP server and checks SurrealDB first. If the configured endpoint is a local endpoint and SurrealDB is not running, the server can launch it using the configured credentials and local database path. It applies pending migrations before serving requests. MCP clients normally launch their configured server process themselves; do not start an extra instance unless you are diagnosing or developing.

The default local RocksDB path is `data/handoffs.db/`. Database location and endpoint behavior are defined by the startup implementation and `SURREAL_*` configuration. Back up the database while following SurrealDB's supported backup procedure; do not treat copying a live database directory as a consistent backup unless the database is stopped or the vendor procedure confirms it is safe.

## Readiness diagnostics

From the repository root:

```text
python scripts/diagnostics.py
```

The diagnostic checks database connectivity/authentication, migration state, local embedding model availability, and MCP `initialize`/`tools/list` over stdio. A database or migration failure blocks later checks that depend on it. An uncached model is not downloaded by default.

Options:

- `--download-model` permits downloading the embedding model.
- `--timeout 180` increases the timeout for slow startup/model loading.
- `--json` emits machine-readable output.

The command exits successfully only when all readiness checks pass. It launches the server configured in `.mcp/config.json` when available.

## Migrations

Numbered files in `sql/migrations/` are applied during normal MCP server startup and recorded in `schema_version`. Check status with `python scripts/run_migrations.py --status`; that standalone runner requires a reachable database. Follow [the migration workflow](../sql/migrations/README.md) when changing schema. Test migration changes using a disposable database before applying them to important data.

## Security and privacy

- Keep real credentials in the ignored `.env`; never commit it or copy secrets into client configuration.
- Set a strong local `SURREAL_PASS` before first startup and keep the database bound to a local interface for local use.
- Handoffs retain raw content as well as structured summaries. Save only work-relevant content and exclude secrets.
- Optional Claude extraction sends transcript text to Anthropic when that extraction path is invoked with `ANTHROPIC_API_KEY` configured.
- Namespace tenant prefixes are not access control. Do not expose this setup as a shared service without an explicit authentication/authorization and network security design.
- Define backup, restore, retention, and upgrade procedures before relying on the database for important project history.

The configured `CONTEXT_LAYER_API_KEY` should not be treated as a complete authorization guarantee without validating where and how server operations enforce it. The current project's deployment posture is local-first, not hardened multi-tenant hosting.

## Troubleshooting

| Symptom | Check |
|---|---|
| SurrealDB executable not found | Install SurrealDB and ensure `surreal` is available on PATH; rerun diagnostics. |
| Database endpoint responds but authentication fails | Verify `SURREAL_URL`, `SURREAL_USER`, `SURREAL_PASS`, `SURREAL_NS`, and `SURREAL_DB` in `.env` and the process environment. |
| Migration check is not ready | Run normal server startup to apply pending migrations, then inspect with `python scripts/run_migrations.py --status`. |
| Embedding model unavailable | Connect to the network and run diagnostics with `--download-model`, then rerun diagnostics without it. |
| MCP handshake does not complete | Inspect `.mcp/config.json`, command path, working directory, and stderr; run `python start_mcp.py` manually for startup detail. |
| Client does not load updated tools/config | Restart/reload the client and check whether project trust or server approval is required. |

