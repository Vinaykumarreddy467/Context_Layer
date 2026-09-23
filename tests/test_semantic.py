"""Test semantic search + graph lineage (data layer)."""
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import context_layer as cl


async def main():
    h1 = await cl.create_handoff(
        "semantic-demo", "main",
        [{"text": "Use JWT", "rationale": "Stateless"}],
        ["Add refresh rotation"],
        "We decided to use JWT tokens for authentication because they are stateless and work across services. The login endpoint needs rate limiting.",
    )
    print("1. created:", h1["id"])

    h2 = await cl.create_handoff(
        "semantic-demo", "main",
        [{"text": "Added refresh", "rationale": "Closes theft window"}],
        ["Deploy to staging"],
        "Continued: implemented refresh token rotation to close the token theft window. Next is deploying to staging.",
        continues_from_id=str(h1["id"]),
    )
    print("2. created chained:", h2["id"])

    res = await cl.semantic_search_handoffs("how do we handle login security and session tokens?")
    print("3. semantic hits:", [(r["task_slug"], round(r["relevance"], 3)) for r in res])

    lin = await cl.get_handoff_lineage(str(h2["id"]))
    print("4. lineage backward:", [str(x["id"]) for x in lin["continues_from"]])
    print("5. lineage forward:", [str(x["id"]) for x in lin["continued_by"]])

    await cl.close_handoff(str(h2["id"]))
    print("6. closed. ALL OK")


asyncio.run(main())