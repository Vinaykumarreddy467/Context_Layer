"""
Integration test for the REST API (scripts/api_server.py) and the
CONTEXT.md sync path. Requires a running SurrealDB (default ws://127.0.0.1:8010)
and the .env file, like the other tests/ scripts.

Run:  python tests/test_api_and_sync.py
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
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

SLUG = f"api-test-{int(time.time())}"


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


def _wait_ready(port: int, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, _ = _request(port, "GET", "/health")
            if status == 200:
                return
        except Exception:
            time.sleep(1)
    raise TimeoutError("API server did not become ready")


def main() -> None:
    # Auth logic unit check (no server needed).
    assert cl.check_api_key("test-key-123") is True
    assert cl.check_api_key("wrong") is False

    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "api_server.py"),
         "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    try:
        _wait_ready(port)

        # 401 without the key.
        status, _ = _request(port, "GET", "/health", key="")
        assert status == 401, f"expected 401 without key, got {status}"

        # Create a handoff.
        status, handoff = _request(port, "POST", "/handoffs", {
            "task_slug": SLUG,
            "git_branch": "main",
            "decisions": [{"text": "Use stdlib http.server",
                           "rationale": "Zero new dependencies"}],
            "next_steps": ["Run the test"],
            "raw_content": "API test handoff for the REST bridge.",
        })
        assert status == 201, f"create failed: {status} {handoff}"

        # Capsule contains the summary.
        status, capsule = _request(port, "GET", f"/capsule/{SLUG}")
        assert status == 200 and SLUG in capsule["capsule"], capsule

        # Search finds it (raw_content is what hybrid search ranks).
        # Scoped to this run's slug: repeated runs accumulate identical
        # records, and an unscoped top-5 search would be dominated by them.
        status, results = _request(
            port, "GET",
            f"/search?q=REST%20bridge&mode=hybrid&limit=5&task_slug={SLUG}")
        assert status == 200 and any(
            r.get("task_slug") == SLUG for r in results
        ), results

        # assemble_context returns sections.
        status, context = _request(port, "GET", f"/context/{SLUG}?max_tokens=2000")
        assert status == 200 and "sections" in context, context

        # Sync writes CONTEXT.md into a project dir with an identity file.
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".context-layer.json").write_text(
                json.dumps({"task_slug": SLUG}), encoding="utf-8")
            status, synced = _request(port, "POST", "/sync",
                                      {"project_dir": tmp})
            assert status == 200, synced
            target = Path(synced["synced"])
            assert target.is_file() and SLUG in target.read_text(encoding="utf-8")

        print(f"PASS: api + sync (slug={SLUG})")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()