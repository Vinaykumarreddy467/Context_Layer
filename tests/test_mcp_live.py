"""Live MCP test: drive the Context Layer MCP server over stdio with a real MCP client."""
import asyncio
import json
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = r"C:\Users\Vinaykumar.R\Downloads\context_layer\context_layer"
SLUG = f"mcp-live-test-{int(time.time())}"
results = []


def _text(res):
    return "\n".join(c.text for c in res.content if hasattr(c, "text"))


def _json(text):
    try:
        return json.loads(text)
    except Exception:
        return None


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


async def main():
    params = StdioServerParameters(command=sys.executable, args=["mcp_server.py"], cwd=ROOT)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            check("initialize", init.serverInfo.name == "context-layer",
                  f"{init.serverInfo.name} {init.serverInfo.version}")

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            check("tools/list", len(tools.tools) >= 15, f"{len(tools.tools)} tools")

            # 1. create
            res = await session.call_tool("create_handoff", {
                "task_slug": SLUG,
                "raw_content": "Live MCP test: OpenWork drives the Context Layer server end to end over stdio.",
                "decisions": [{"text": "Use MCP stdio for the live test", "rationale": "Verify a real client can drive the server"}],
                "next_steps": ["Confirm live test passed"],
            })
            text = _text(res)
            data = _json(text)
            hid = None
            if not res.isError and isinstance(data, dict):
                hid = data.get("id") or (data.get("handoff") or {}).get("id")
            check("create_handoff", bool(hid), f"id={hid} err={text[:80] if res.isError else ''}")

            # 2. duplicate guard: same content again -> same id
            res2 = await session.call_tool("create_handoff", {
                "task_slug": SLUG,
                "raw_content": "Live MCP test: OpenWork drives the Context Layer server end to end over stdio.",
                "decisions": [{"text": "Use MCP stdio for the live test", "rationale": "Verify a real client can drive the server"}],
                "next_steps": ["Confirm live test passed"],
            })
            text2 = _text(res2)
            data2 = _json(text2)
            hid2 = None
            if not res2.isError and isinstance(data2, dict):
                hid2 = data2.get("id") or (data2.get("handoff") or {}).get("id")
            check("duplicate guard", hid2 == hid, f"{hid2} == {hid}")

            # 3. search
            res = await session.call_tool("search_handoffs", {"query": "live MCP test", "task_slug": SLUG, "limit": 3})
            check("search_handoffs", SLUG in _text(res), _text(res)[:120])

            # 4. hybrid
            res = await session.call_tool("hybrid_search_handoffs", {"query": "live MCP test", "task_slug": SLUG, "limit": 3})
            check("hybrid_search_handoffs", SLUG in _text(res), _text(res)[:120])

            # 5. capsule
            res = await session.call_tool("get_context_capsule", {"task_slug": SLUG})
            cap = _text(res)
            check("get_context_capsule", "Live MCP test" in cap, f"{len(cap)} chars")

            # 6. resume
            res = await session.call_tool("resume_handoff", {"task_slug": SLUG})
            check("resume_handoff", "resumed" in _text(res), _text(res)[:80])

            # 7. append next step
            if hid:
                res = await session.call_tool("append_next_step", {"handoff_id": hid, "step": "Appended via live MCP test"})
                check("append_next_step", "Appended via live MCP test" in _text(res), _text(res)[:80])

            # 8. budget report
            res = await session.call_tool("token_budget_report", {"task_slug": SLUG})
            check("token_budget_report", "latest_handoff" in _text(res), _text(res)[:100])

            # 9. resource read
            try:
                res = await session.read_resource(f"context://current/{SLUG}")
                rtext = res.contents[0].text if res.contents else ""
                check("resource context://current", "Live MCP test" in rtext, f"{len(rtext)} chars")
            except Exception as exc:
                check("resource context://current", False, str(exc)[:100])

            # 10. close
            if hid:
                res = await session.call_tool("close_handoff", {"handoff_id": hid})
                check("close_handoff", "closed" in _text(res), _text(res)[:80])

    passed = sum(1 for _, ok in results if ok)
    print(f"\n=== {passed}/{len(results)} checks passed ===")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())