# Development

This guide is for contributors working in the Context Layer checkout. See [Repository map](../FOLDER_STRUCTURE.md) for the package and script layout.

## Install for development

The package declares runtime dependencies in `pyproject.toml` and optional development dependencies under the `dev` extra:

```text
python -m venv venv
# Activate the environment for your shell.
python -m pip install -e ".[dev]"
```

Configure `.env` and a disposable SurrealDB database before running integration scripts.

## Tests and data safety

Files under `tests/` are executable integration scripts. They are not a conventional pytest suite; several connect to the configured database, start MCP, create records, or load the embedding model. Review a script before running it and point it at disposable test data. Examples:

```text
python tests/test_mcp_e2e.py
python tests/test_mcp_semantic.py
python tests/test_migrations.py
```

Do not aim integration runs at a database whose contents must be preserved.

## Code changes

- Keep schema changes in a new numbered file under `sql/migrations/`; do not rewrite a migration that has shipped or been applied.
- Keep MCP protocol output on stdout and startup/logging messages on stderr for stdio clients.
- Preserve clear startup and diagnostic errors so users can distinguish database, migration, model, and client setup failures.
- Keep client-specific lifecycle assumptions inside adapters and document limitations when host event support is incomplete.
- Never commit `.env`, real credentials, or machine-specific generated paths.

See [Migration workflow](../sql/migrations/README.md) before changing the schema.

