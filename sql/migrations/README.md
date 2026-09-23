# SurrealDB migrations

The application schema is managed by the numbered SurrealQL files in this directory. The MCP server applies pending migrations during normal startup and records applied versions in the `schema_version` table.

## Migration workflow

1. Check the current database state:

   ```bash
   python scripts/run_migrations.py --status
   ```

   The database must already be reachable with the configured `SURREAL_*` variables.

2. Add a new file with the next four-digit version, for example `0002_add_handoff_field.surql`.
3. Make the migration safe to apply to the expected prior schema. Avoid editing migrations that have already shipped or been applied; add a new migration instead.
4. Validate the migration against a disposable database before using it with important data.
5. Start the MCP server or run `python scripts/run_migrations.py` to apply pending versions.
6. Confirm the result with `python scripts/run_migrations.py --status`.

The migration runner records a version only after its SQL statements complete. Keep each statement semicolon-delimited, as the current runner splits the file on semicolons. Avoid semicolons inside string literals or other constructs that would be broken by that split.

## Manual database and connections

The standalone migration runner does not start SurrealDB. Start the database first, then configure `SURREAL_URL`, `SURREAL_NS`, `SURREAL_DB`, `SURREAL_USER`, and `SURREAL_PASS` in the process environment. The default local database is `dev/context_layer` at `ws://127.0.0.1:8010`.

`python scripts/run_migrations.py --fake <version>` marks a version as applied without executing its SQL. Use this only after manually applying the corresponding schema changes to the same database.

## Reference schema

`sql/001_schema.surql` is a human-readable schema and query reference. It contains sample data-changing queries, including an example delete; it is not the versioned migration file and is not automatically executed by the MCP server. For actual schema evolution, use numbered migrations in this directory.
