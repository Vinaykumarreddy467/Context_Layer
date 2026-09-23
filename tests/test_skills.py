"""MCP stdio test for list_skills + get_skill."""
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
# Use the project's own skills directory if it exists
project_root = Path(__file__).resolve().parent.parent.parent
skills_dirs = [
    str(project_root / ".opencode" / "skills"),
    str(project_root / "skills"),
]
os.environ["SKILLS_DIRS"] = os.pathsep.join([d for d in skills_dirs if Path(d).exists()])

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

    async def call(method, params, timeout=60):
        proc.stdin.write((json.dumps(req(method, params)) + "\n").encode())
        await proc.stdin.drain()
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
        return json.loads(line)

    r = await call("initialize", {
        "protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": "skills-test", "version": "0.1"},
    })
    print("1. INITIALIZE:", r["result"]["serverInfo"])

    r = await call("tools/list", {})
    tools = [t["name"] for t in r["result"]["tools"]]
    assert "list_skills" in tools and "get_skill" in tools, tools
    print("2. TOOLS:", len(tools), "incl. list_skills + get_skill")

    r = await call("tools/call", {"name": "list_skills", "arguments": {}})
    skills = json.loads(r["result"]["content"][0]["text"])
    skills = skills["skills"]
    names = [s["name"] for s in skills]
    print("3. LIST:", len(skills), "skills, e.g.", names[:5])

    # Test get_skill with first available skill (if any)
    if names:
        r = await call("tools/call", {"name": "get_skill", "arguments": {"name": names[0]}})
        skill = json.loads(r["result"]["content"][0]["text"])
        assert "content" in skill, skill
        print("4. GET:", names[0], "%d chars" % len(skill["content"]))
    else:
        print("4. GET: no skills available, skipping")

    # Test get_skill with non-existent skill
    r = await call("tools/call", {"name": "get_skill", "arguments": {"name": "no-such-skill"}})
    missing = json.loads(r["result"]["content"][0]["text"])
    assert "error" in missing, missing
    print("5. MISSING:", missing["error"][:60])

    proc.terminate()
    await proc.wait()
    print("\nALL 5 STEPS PASSED")


asyncio.run(main())