"""MCP test for semantic search + lineage tools, with stderr capture on timeout."""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

os.environ["SURREAL_URL"] = "ws://127.0.0.1:8010"
os.environ["SURREAL_NS"] = "dev"
os.environ["SURREAL_DB"] = "context_layer"
os.environ["SURREAL_USER"] = "root"
os.environ["SURREAL_PASS"] = "root"
os.environ.pop("ANTHROPIC_API_KEY", None)

_id = 0


def req(method, params):
    global _id
    _id += 1
    return {"jsonrpc": "2.0", "id": _id, "method": method, "params": params}


async def main():
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(Path(__file__).resolve().parent.parent / "mcp_server.py"),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def call(method, params, timeout=90):
        proc.stdin.write((json.dumps(req(method, params)) + "\n").encode())
        await proc.stdin.drain()
        try:
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
            return json.loads(line)
        except asyncio.TimeoutError:
            print("TIMEOUT on", method)
            proc.terminate()
            await asyncio.sleep(1)
            err = await proc.stderr.read()
            print("STDERR:", err.decode()[:3000])
            raise

    await call("initialize", {
        "protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": "semantic-test", "version": "0.1"},
    })
    r = await call("tools/list", {})
    tools = [t["name"] for t in r["result"]["tools"]]
    print("1. TOOLS (%d):" % len(tools), tools)

    # Create test handoffs
    r = await call("tools/call", {
        "name": "create_handoff",
        "arguments": {
            "task_slug": "semantic-mcp-test",
            "git_branch": "main",
            "decisions": [{"text": "Use JWT", "rationale": "Stateless"}],
            "next_steps": ["Add refresh rotation"],
            "raw_content": "We decided to use JWT tokens for authentication because they are stateless and work across services. The login endpoint needs rate limiting.",
        },
    })
    h1 = json.loads(r["result"]["content"][0]["text"])
    h1_id = str(h1["id"])
    print("Created handoff 1:", h1_id)

    r = await call("tools/call", {
        "name": "create_handoff",
        "arguments": {
            "task_slug": "semantic-mcp-test",
            "git_branch": "main",
            "decisions": [{"text": "Added refresh", "rationale": "Closes theft window"}],
            "next_steps": ["Deploy to staging"],
            "raw_content": "Continued: implemented refresh token rotation to close the token theft window. Next is deploying to staging.",
            "continues_from_id": h1_id,
        },
    })
    h2 = json.loads(r["result"]["content"][0]["text"])
    h2_id = str(h2["id"])
    print("Created handoff 2 (chained):", h2_id)

    # Test semantic_search_handoffs
    r = await call("tools/call", {"name": "semantic_search_handoffs", "arguments": {"query": "how do we handle login security and session tokens?", "limit": 3}})
    text = r["result"]["content"][0]["text"]
    print("2. SEMANTIC:", text[:300].replace("\n", " | "))

    # Test get_handoff_lineage with our created handoff
    r = await call("tools/call", {"name": "get_handoff_lineage", "arguments": {"handoff_id": h2_id}})
    text = r["result"]["content"][0]["text"]
    print("3. LINEAGE:", text[:300].replace("\n", " | "))

    # Test hybrid_search_handoffs
    r = await call("tools/call", {"name": "hybrid_search_handoffs", "arguments": {"query": "authentication and tokens", "limit": 3}})
    text = r["result"]["content"][0]["text"]
    print("4. HYBRID:", text[:300].replace("\n", " | "))

    proc.terminate()
    await proc.wait()
    print("\nDONE")


asyncio.run(main())