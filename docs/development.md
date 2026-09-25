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
python tests/test_handoff.py
python tests/test_adapter_query.py
python tests/test_api_and_sync.py
```

Do not aim integration runs at a database whose contents must be preserved.

## Code changes

- Keep schema changes in a new numbered file under `sql/migrations/`; do not rewrite a migration that has shipped or been applied.
- Keep MCP protocol output on stdout and startup/logging messages on stderr for stdio clients.
- Preserve clear startup and diagnostic errors so users can distinguish database, migration, model, and client setup failures.
- Keep client-specific lifecycle assumptions inside adapters and document limitations when host event support is incomplete.
- Never commit `.env`, real credentials, or machine-specific generated paths.

See [Migration workflow](../sql/migrations/README.md) before changing the schema.

## Retrieval evaluation

`scripts/evaluate_retrieval.py` compares search results with a labeled JSON dataset. Each case needs a query, project `task_slug`, and one or more relevant handoff IDs:

```json
{
  "cases": [
    {
      "query": "Why did we choose SurrealDB?",
      "task_slug": "context-layer",
      "relevant_ids": ["handoff:REPLACE_WITH_ID"]
    }
  ]
}
```

The baseline is reproducible: `scripts/eval_fixture.py` creates six deterministic handoffs under the `eval-fixture` task slug (fixed content, so embeddings and scores are stable), writes a gold set with the real record IDs to `output/eval/gold_set.json`, and prints the evaluation command. No machine-specific handoff IDs are committed. Recreate the fixture and re-run the baseline after retrieval changes:

```text
python scripts/eval_fixture.py
python scripts/evaluate_retrieval.py output/eval/gold_set.json --search hybrid -k 5
```

Recorded baseline (hybrid `-k 5`): hit rate 1.000, mean recall 1.000, mean precision 0.200, MRR 0.917.

Run each search mode against the same labeled set to compare rankings:

```text
python scripts/evaluate_retrieval.py output/eval/gold_set.json --search hybrid -k 5
python scripts/evaluate_retrieval.py output/eval/gold_set.json --search text -k 5 --json
python scripts/evaluate_retrieval.py output/eval/gold_set.json --search semantic -k 5 --min-mrr 0.6
```

Remove the fixture handoffs when done:

```text
python scripts/eval_fixture.py --cleanup
```

The evaluator only reads/searches the configured database; it does not create handoffs. `hit_rate@k` is the fraction of queries with any expected handoff in the results; `mean_recall@k` is the average fraction of expected handoffs found; `mean_precision@k` is the average fraction of returned slots that are relevant; `MRR@k` rewards putting a relevant result near the top. These scores reflect the quality of the labeled examples, so review expected IDs carefully and keep the dataset representative of real resume questions.
