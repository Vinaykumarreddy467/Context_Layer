"""
Focused reliability tests for Context Layer:

1. Duplicate-checkpoint guard: dedup only on task_slug + content_hash
   (SHA-256 over normalized raw_content); platform_session_id alone is
   never a duplicate signal; historic records without a hash still load.
2. Safe create + lineage: handoff and continues_from edge are created
   atomically; an invalid continues_from_id errors and leaves no orphan.
3. REST API input validation: invalid limit / max_tokens / task_slug /
   JSON body return 400 with the stable {"error": {"code", "message"}}
   shape; creating a handoff without git_branch works end to end.

Requires a running SurrealDB (default ws://127.0.0.1:8010) and .env.

Run:  python tests/test_reliability.py
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Set before importing context_layer so the API key is active for the
# whole test (the spawned server inherits this env too).
os.environ["CONTEXT_LAYER_API_KEY"] = "test-key-123"

import context_layer as cl  # noqa: E402
from context_layer.core import _embed_async  # noqa: E402

SLUG = f"reliability-{int(time.time())}"
SLUG2 = f"{SLUG}-b"


async def _wipe() -> None:
    db = await cl._connect()
    try:
        await db.query("DELETE handoff WHERE task_slug IN [$a, $b];",
                       {"a": SLUG, "b": SLUG2})
    finally:
        await db.close()


async def test_duplicate_guard() -> None:
    await _wipe()

    # (a) same content twice within 60s -> original handoff returned
    h1 = await cl.create_handoff(
        task_slug=SLUG, decisions=[{"text": "d", "rationale": "r"}],
        next_steps=["n"], raw_content="duplicate guard content alpha",
    )
    h2 = await cl.create_handoff(
        task_slug=SLUG, decisions=[{"text": "d", "rationale": "r"}],
        next_steps=["n"], raw_content="duplicate guard content alpha",
    )
    assert str(h1["id"]) == str(h2["id"]), "same content must dedupe within 60s"
    assert h2.get("content_hash"), "duplicate return must carry content_hash"

    # (b) different content, same platform_session_id -> second handoff
    h3 = await cl.create_handoff(
        task_slug=SLUG, decisions=[{"text": "d", "rationale": "r"}],
        next_steps=["n"], raw_content="duplicate guard content beta",
        platform_session_id="sess-1",
    )
    assert str(h1["id"]) != str(h3["id"]), \
        "platform_session_id alone must not dedupe different content"

    # (c) different tasks, identical content -> separate handoffs
    h4 = await cl.create_handoff(
        task_slug=SLUG2, decisions=[{"text": "d", "rationale": "r"}],
        next_steps=["n"], raw_content="duplicate guard content alpha",
    )
    assert str(h1["id"]) != str(h4["id"]), \
        "identical content in different tasks must not dedupe"

    # (d) historic record without content_hash still loads and resumes
    db = await cl._connect()
    try:
        created = await db.create("handoff", {
            "task_slug": SLUG, "git_branch": "main", "status": "open", "version": 1,
            "decisions": [], "next_steps": [],
            "raw_content": "historic record without a content hash",
            "summary": "", "token_count": 0, "files": [], "refs": [],
            "embedding": await _embed_async("historic record without a content hash"),
        })
    finally:
        await db.close()
    historic = created[0] if isinstance(created, list) else created
    assert not historic.get("content_hash"), "fixture must simulate a pre-0004 record"

    latest = await cl.get_latest_handoff(SLUG)
    assert latest is not None and str(latest["id"]) == str(historic["id"])
    resumed = await cl.resume_handoff(SLUG)
    assert resumed is not None and resumed["status"] == "resumed"
    ctx = await cl.assemble_context(SLUG, max_tokens=4000)
    assert ctx["total_tokens"] > 0, "historic record must assemble into context"

    print("PASS: duplicate guard (content_hash) + historic records")


async def test_lineage_safety() -> None:
    # (a) valid predecessor -> lineage confirmed
    parent = await cl.create_handoff(
        task_slug=SLUG, decisions=[], next_steps=[],
        raw_content="lineage parent content",
    )
    child = await cl.create_handoff(
        task_slug=SLUG, decisions=[], next_steps=[],
        raw_content="lineage child content",
        continues_from_id=str(parent["id"]),
    )
    lineage = await cl.get_handoff_lineage(str(child["id"]))
    assert any(str(r["id"]) == str(parent["id"]) for r in lineage["continues_from"]), \
        "child must link to its parent"

    # (b) invalid continues_from_id -> clear error
    before = await cl.get_latest_handoff(SLUG)
    try:
        await cl.create_handoff(
            task_slug=SLUG, decisions=[], next_steps=[],
            raw_content="lineage orphan content",
            continues_from_id="handoff:doesnotexist",
        )
        raise AssertionError("expected ValueError for invalid continues_from_id")
    except ValueError as exc:
        assert "continues_from_id not found" in str(exc), exc

    # (c) no orphan handoff left behind
    after = await cl.get_latest_handoff(SLUG)
    assert str(before["id"]) == str(after["id"]), \
        "failed create must not leave an orphan handoff"

    print("PASS: lineage safety (transaction, no orphans)")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _request(port: int, method: str, path: str, body=None, key="test-key-123"):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_api_validation() -> None:
    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "api_server.py"),
         "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.time() + 120
        while time.time() < deadline:
            try:
                status, _ = _request(port, "GET", "/health")
                if status == 200:
                    break
            except Exception:
                time.sleep(1)
        else:
            raise TimeoutError("API server did not become ready")

        # invalid limit -> 400 invalid_limit
        for bad in ("0", "101", "abc"):
            status, body = _request(port, "GET", f"/search?q=test&limit={bad}")
            assert status == 400 and body["error"]["code"] == "invalid_limit", body

        # invalid max_tokens -> 400 invalid_max_tokens
        for bad in ("100", "99999", "abc"):
            status, body = _request(port, "GET", f"/context/{SLUG}?max_tokens={bad}")
            assert status == 400 and body["error"]["code"] == "invalid_max_tokens", body

        # invalid task_slug -> 400 invalid_task_slug
        status, body = _request(port, "GET", "/context/-bad")
        assert status == 400 and body["error"]["code"] == "invalid_task_slug", body
        status, body = _request(port, "POST", "/handoffs", {"task_slug": "bad slug!"})
        assert status == 400 and body["error"]["code"] == "invalid_task_slug", body

        # invalid JSON body -> 400 invalid_json
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/handoffs", method="POST",
            data=b"{not json",
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer test-key-123"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status, body = resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            status, body = e.code, json.loads(e.read())
        assert status == 400 and body["error"]["code"] == "invalid_json", body

        # optional git_branch: create / resume / assemble all work
        status, handoff = _request(port, "POST", "/handoffs", {
            "task_slug": SLUG,
            "decisions": [{"text": "d", "rationale": "r"}],
            "next_steps": ["n"],
            "raw_content": "api optional git_branch content",
        })
        assert status == 201, handoff
        assert handoff.get("git_branch") is None, handoff
        status, context = _request(port, "GET", f"/context/{SLUG}?max_tokens=2000")
        assert status == 200 and "sections" in context, context
        status, capsule = _request(port, "GET", f"/capsule/{SLUG}")
        assert status == 200 and SLUG in capsule["capsule"], capsule

        print("PASS: API validation + optional git_branch")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


def main() -> None:
    asyncio.run(test_duplicate_guard())
    asyncio.run(test_lineage_safety())
    test_api_validation()
    asyncio.run(_wipe())
    print("RELIABILITY TESTS PASSED")


if __name__ == "__main__":
    main()