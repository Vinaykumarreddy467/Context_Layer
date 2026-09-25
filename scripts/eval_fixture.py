#!/usr/bin/env python3
"""
Create a deterministic retrieval-evaluation fixture and gold set.

Creates handoffs with fixed content under the task_slug 'eval-fixture',
writes a gold set JSON whose relevant_ids are the real record ids, and
prints the exact evaluation command. No machine-specific handoff ids are
committed: the gold set is generated at evaluation time, so a fresh
database can reproduce the baseline.

Usage:
    python scripts/eval_fixture.py                 # create fixture + gold set
    python scripts/eval_fixture.py --cleanup       # delete fixture handoffs
    python scripts/evaluate_retrieval.py output/eval/gold_set.json --search hybrid -k 5
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import context_layer as cl

FIXTURE_SLUG = "eval-fixture"
OUT = ROOT / "output" / "eval" / "gold_set.json"

# Deterministic fixture: one handoff per topic, one query per handoff.
# Content is fixed so embeddings (and therefore the baseline) are stable.
FIXTURE = [
    {
        "topic": "task_slug resolution",
        "content": (
            "How task_slug is resolved for a project: project_identity.py checks the "
            "CONTEXT_LAYER_TASK_SLUG environment override first, then walks up the "
            "directory tree looking for a .context-layer.json identity file, and finally "
            "falls back to the project directory basename."
        ),
        "query": "How is task_slug resolved for a project?",
    },
    {
        "topic": "test scripts",
        "content": (
            "The test scripts run against the live SurrealDB instance: test_handoff, "
            "test_api_and_sync, test_migrations, and test_mcp_live all pass against "
            "ws://127.0.0.1:8010 with the dev namespace and context_layer database."
        ),
        "query": "Which test scripts pass against the live database?",
    },
    {
        "topic": "MCP server connection",
        "content": (
            "Connecting the context-layer MCP server to an agent: run python mcp_server.py "
            "over stdio and register it as an MCP server in the client configuration, then "
            "the handoff tools appear in the agent's tool list."
        ),
        "query": "Connect the context-layer MCP server to an agent",
    },
    {
        "topic": "retrieval evaluation",
        "content": (
            "Retrieval evaluation: build a gold set of queries with relevant handoff ids, "
            "then measure hit rate, mean recall, mean precision, and MRR at k using "
            "scripts/evaluate_retrieval.py."
        ),
        "query": "Curate a retrieval evaluation dataset and record a baseline",
    },
    {
        "topic": "licensing",
        "content": (
            "Licensing: add an open-source LICENSE file before wider distribution of the "
            "project so downstream users know the terms under which the code is released."
        ),
        "query": "Add an open-source LICENSE before wider distribution",
    },
    {
        "topic": "identity file",
        "content": (
            "Project identity: create the .context-layer.json file with the task_slug so "
            "adapters and the sync endpoint resolve the same slug for the project."
        ),
        "query": "Create the .context-layer.json identity file",
    },
]


async def cleanup() -> None:
    db = await cl._connect()
    try:
        await db.query("DELETE handoff WHERE task_slug = $slug;", {"slug": FIXTURE_SLUG})
    finally:
        await db.close()


async def create_fixture() -> dict:
    await cleanup()  # fresh fixture each run keeps the baseline deterministic
    ids = {}
    for item in FIXTURE:
        handoff = await cl.create_handoff(
            task_slug=FIXTURE_SLUG,
            git_branch="main",
            decisions=[{"text": f"Fixture: {item['topic']}", "rationale": "deterministic eval data"}],
            next_steps=["Run the retrieval evaluation"],
            raw_content=item["content"],
        )
        ids[item["topic"]] = str(handoff["id"])
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cleanup", action="store_true",
                        help="delete the fixture handoffs and exit")
    args = parser.parse_args()

    if args.cleanup:
        asyncio.run(cleanup())
        print(f"Deleted fixture handoffs under task_slug '{FIXTURE_SLUG}'.")
        return 0

    ids = asyncio.run(create_fixture())
    cases = [
        {"query": item["query"], "task_slug": FIXTURE_SLUG,
         "relevant_ids": [ids[item["topic"]]]}
        for item in FIXTURE
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "description": "Deterministic retrieval-eval fixture (see scripts/eval_fixture.py)",
        "cases": cases,
    }, indent=2), encoding="utf-8")

    print(f"Created {len(cases)} fixture handoffs under task_slug '{FIXTURE_SLUG}'.")
    print(f"Gold set written to {OUT.relative_to(ROOT)}")
    print("Run the evaluation:")
    print(f"  python scripts/evaluate_retrieval.py {OUT.relative_to(ROOT)} --search hybrid -k 5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())