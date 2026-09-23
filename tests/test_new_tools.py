"""Test auto_summarize_handoff, get_context_capsule, and window tools without any API key."""
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
os.environ.pop("ANTHROPIC_API_KEY", None)  # ensure NO key

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

    async def call(method, params, timeout=30):
        proc.stdin.write((json.dumps(req(method, params)) + "\n").encode())
        await proc.stdin.drain()
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
        return json.loads(line)

    r = await call("initialize", {
        "protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": "new-tools-test", "version": "0.1"},
    })
    print("1. INITIALIZE:", r["result"]["serverInfo"])

    r = await call("tools/list", {})
    tools = [t["name"] for t in r["result"]["tools"]]
    print("2. TOOLS:", len(tools), "tools")

    # Create a test handoff first
    r = await call("tools/call", {
        "name": "create_handoff",
        "arguments": {
            "task_slug": "new-tools-test",
            "git_branch": "main",
            "decisions": [{"text": "Test decision", "rationale": "Testing"}],
            "next_steps": ["Test step"],
            "raw_content": "Test handoff for new tools.",
        },
    })
    handoff = json.loads(r["result"]["content"][0]["text"])
    hid = str(handoff["id"])
    print("Created test handoff:", hid)

    # get_context_capsule (no key needed)
    r = await call("tools/call", {"name": "get_context_capsule", "arguments": {"task_slug": "new-tools-test"}})
    text = r["result"]["content"][0]["text"]
    print("3. CAPSULE:", text[:200].replace("\n", " | "))
    assert "Context primer" in text
    assert "Test decision" in text

    # auto_summarize_handoff (no key -> local extraction)
    r = await call("tools/call", {"name": "auto_summarize_handoff", "arguments": {
        "transcript": "user: We need to add authentication\nassistant: I'll implement JWT-based auth\nuser: Decision: Use JWT over sessions\nassistant: Next step: Add refresh token rotation",
        "task_slug": "auto-summarize-test",
        "git_branch": "main",
    }})
    summarized = json.loads(r["result"]["content"][0]["text"])
    print("4. AUTO_SUMMARIZE (no key):", summarized.get("extraction_status"))
    assert summarized.get("extraction_status") in ("local", "local_fallback")
    assert "extraction_warning" not in summarized or summarized["extraction_warning"] is None

    # context_for_window
    r = await call("tools/call", {"name": "context_for_window", "arguments": {"task_slug": "new-tools-test", "max_tokens": 4000}})
    ctx = json.loads(r["result"]["content"][0]["text"])
    print("5. CONTEXT_FOR_WINDOW: sections:", len(ctx.get("sections", [])), "tokens:", ctx.get("total_tokens"))
    assert ctx.get("total_tokens", 0) > 0

    # summarize_for_window
    r = await call("tools/call", {"name": "summarize_for_window", "arguments": {"task_slug": "new-tools-test", "target_tokens": 2000}})
    summary = json.loads(r["result"]["content"][0]["text"])
    print("6. SUMMARIZE_FOR_WINDOW: action:", summary.get("action"))

    # token_budget_report
    r = await call("tools/call", {"name": "token_budget_report", "arguments": {"task_slug": "new-tools-test"}})
    budget = json.loads(r["result"]["content"][0]["text"])
    print("7. TOKEN_BUDGET_REPORT: current_tokens:", budget.get("current_context_tokens"))
    assert "recommendations" in budget

    proc.terminate()
    await proc.wait()
    print("\nALL 7 STEPS PASSED - server ran with zero API keys")


asyncio.run(main())