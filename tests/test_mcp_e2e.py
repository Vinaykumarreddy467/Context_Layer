"""End-to-end MCP stdio test: spawn mcp_server.py, handshake, call every tool."""
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
os.environ.pop("ANTHROPIC_API_KEY", None)  # Ensure local extraction path

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

    # 1. initialize
    r = await call("initialize", {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "e2e-test", "version": "0.1"},
    })
    print("1. INITIALIZE:", r["result"]["serverInfo"])

    # 2. tools/list
    r = await call("tools/list", {})
    tools = [t["name"] for t in r["result"]["tools"]]
    print("2. TOOLS (%d):" % len(tools), tools)

    expected_tools = [
        "create_handoff", "resume_handoff", "search_handoffs", "append_next_step",
        "close_handoff", "auto_summarize_handoff", "semantic_search_handoffs",
        "hybrid_search_handoffs", "get_handoff_lineage", "find_handoffs_by_file",
        "get_context_capsule", "context_for_window", "summarize_for_window",
        "token_budget_report", "list_skills", "get_skill", "ensure_project_ready"
    ]
    for t in expected_tools:
        assert t in tools, f"Missing tool: {t}"

    # 3. create_handoff
    r = await call("tools/call", {
        "name": "create_handoff",
        "arguments": {
            "task_slug": "e2e-test",
            "git_branch": "main",
            "decisions": [{"text": "MCP e2e works", "rationale": "Proving the stdio path"}],
            "next_steps": ["Verify all tools"],
            "raw_content": "End-to-end MCP test handoff.",
        },
    })
    content = r["result"]["content"][0]["text"]
    handoff = json.loads(content)
    hid = str(handoff["id"])
    print("3. CREATE:", hid, "| status:", handoff["status"])
    assert handoff["status"] == "open"

    # 4. resume_handoff
    r = await call("tools/call", {"name": "resume_handoff", "arguments": {"task_slug": "e2e-test"}})
    resumed = json.loads(r["result"]["content"][0]["text"])
    print("4. RESUME: task:", resumed["task_slug"], "| status:", resumed["status"])
    assert resumed["status"] == "resumed"

    # 5. search_handoffs (BM25)
    r = await call("tools/call", {"name": "search_handoffs", "arguments": {"query": "handoff"}})
    found = json.loads(r["result"]["content"][0]["text"])
    found = found.get("result", found)
    if isinstance(found, dict):
        found = [found]
    print("5. SEARCH (BM25): hits:", len(found), "| first:", found[0]["task_slug"] if found else None)
    assert len(found) > 0

    # 6. append_next_step
    r = await call("tools/call", {"name": "append_next_step", "arguments": {"handoff_id": hid, "step": "Appended via MCP"}})
    appended = json.loads(r["result"]["content"][0]["text"])
    print("6. APPEND: next_steps:", appended["next_steps"])
    assert "Appended via MCP" in appended["next_steps"]

    # 7. close_handoff
    r = await call("tools/call", {"name": "close_handoff", "arguments": {"handoff_id": hid}})
    closed = json.loads(r["result"]["content"][0]["text"])
    print("7. CLOSE: status:", closed["status"])
    assert closed["status"] == "closed"

    # 8. auto_summarize_handoff (local extraction)
    r = await call("tools/call", {"name": "auto_summarize_handoff", "arguments": {
        "transcript": "user: We need to add authentication\nassistant: I'll implement JWT-based auth\nuser: Decision: Use JWT over sessions\nassistant: Next step: Add refresh token rotation",
        "task_slug": "auto-summarize-test",
        "git_branch": "main",
    }})
    summarized = json.loads(r["result"]["content"][0]["text"])
    print("8. AUTO_SUMMARIZE: id:", summarized.get("id"), "| status:", summarized.get("extraction_status"))
    assert summarized.get("extraction_status") in ("local", "local_fallback")

    # 9. semantic_search_handoffs
    r = await call("tools/call", {"name": "semantic_search_handoffs", "arguments": {"query": "authentication and tokens", "limit": 3}})
    semantic = json.loads(r["result"]["content"][0]["text"])
    print("9. SEMANTIC_SEARCH: hits:", len(semantic))

    # 10. hybrid_search_handoffs
    r = await call("tools/call", {"name": "hybrid_search_handoffs", "arguments": {"query": "authentication and tokens", "limit": 3}})
    hybrid = json.loads(r["result"]["content"][0]["text"])
    print("10. HYBRID_SEARCH: hits:", len(hybrid))

    # 11. get_handoff_lineage
    r = await call("tools/call", {"name": "get_handoff_lineage", "arguments": {"handoff_id": hid}})
    lineage = json.loads(r["result"]["content"][0]["text"])
    print("11. LINEAGE: backward:", len(lineage.get("continues_from", [])), "forward:", len(lineage.get("continued_by", [])))

    # 12. find_handoffs_by_file
    r = await call("tools/call", {"name": "find_handoffs_by_file", "arguments": {"path": "auth.py", "limit": 5}})
    by_file = json.loads(r["result"]["content"][0]["text"])
    print("12. FIND_BY_FILE: hits:", len(by_file))

    # 13. get_context_capsule
    r = await call("tools/call", {"name": "get_context_capsule", "arguments": {"task_slug": "e2e-test"}})
    capsule = r["result"]["content"][0]["text"]
    print("13. CAPSULE: chars:", len(capsule))
    assert "Context primer" in capsule

    # 14. context_for_window
    r = await call("tools/call", {"name": "context_for_window", "arguments": {"task_slug": "e2e-test", "max_tokens": 4000}})
    ctx = json.loads(r["result"]["content"][0]["text"])
    print("14. CONTEXT_FOR_WINDOW: sections:", len(ctx.get("sections", [])), "total_tokens:", ctx.get("total_tokens"))

    # 15. summarize_for_window
    r = await call("tools/call", {"name": "summarize_for_window", "arguments": {"task_slug": "e2e-test", "target_tokens": 2000}})
    summary = json.loads(r["result"]["content"][0]["text"])
    print("15. SUMMARIZE_FOR_WINDOW: action:", summary.get("action"))

    # 16. token_budget_report
    r = await call("tools/call", {"name": "token_budget_report", "arguments": {"task_slug": "e2e-test"}})
    budget = json.loads(r["result"]["content"][0]["text"])
    print("16. TOKEN_BUDGET_REPORT: current_tokens:", budget.get("current_context_tokens"))

    # 17. list_skills
    r = await call("tools/call", {"name": "list_skills", "arguments": {}})
    skills = json.loads(r["result"]["content"][0]["text"])
    print("17. LIST_SKILLS: count:", len(skills.get("skills", [])))

    # 18. get_skill (non-existent)
    r = await call("tools/call", {"name": "get_skill", "arguments": {"name": "no-such-skill"}})
    missing = json.loads(r["result"]["content"][0]["text"])
    print("18. GET_SKILL (missing):", "error" in missing)
    assert "error" in missing

    # 19. ensure_project_ready
    r = await call("tools/call", {"name": "ensure_project_ready", "arguments": {"project_path": str(Path.cwd())}})
    ready = json.loads(r["result"]["content"][0]["text"])
    print("19. ENSURE_PROJECT_READY: ready:", ready.get("ready"), "slug:", ready.get("slug"))

    proc.terminate()
    await proc.wait()
    print("\nALL 19 STEPS PASSED")


asyncio.run(main())