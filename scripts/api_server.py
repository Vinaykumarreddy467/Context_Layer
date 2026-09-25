#!/usr/bin/env python3
"""
REST API for Context Layer, so ANY agent or script can read and write
context over plain HTTP -- no MCP support required (GPT Actions, Gemini
extensions, remote agents, curl, anything).

Endpoints:
  GET  /health                          -> {"status": "ok"}
  GET  /context/{task_slug}             -> assemble_context (token-budgeted)
  GET  /capsule/{task_slug}             -> portable markdown primer
  GET  /search?q=...&mode=hybrid&limit=5&task_slug=...
  POST /handoffs                        -> create_handoff (JSON body)
  POST /summarize                       -> auto_handoff.summarize_and_store
  POST /sync                            -> write CONTEXT.md in a project dir

Auth: if CONTEXT_LAYER_API_KEY is set, every request needs
  Authorization: Bearer <key>  or  X-API-Key: <key>

Run:  python scripts/api_server.py [--host 127.0.0.1] [--port 8123]
"""
import argparse
import asyncio
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import context_layer as cl  # noqa: E402
from context_layer import auto_handoff, export_capsule as capsule  # noqa: E402

SEARCH_MODES = {
    "text": cl.search_handoffs,
    "semantic": cl.semantic_search_handoffs,
    "hybrid": cl.hybrid_search_handoffs,
}


def _run(coro):
    return asyncio.run(coro)


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type, Authorization, X-API-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self) -> bool:
        if not cl.API_KEY:
            return True
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return cl.check_api_key(header[7:])
        return cl.check_api_key(self.headers.get("X-API-Key", ""))

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return {}

    def _route(self, method: str) -> None:
        if not self._auth_ok():
            return self._json(401, {"error": "invalid or missing API key"})
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        qs = parse_qs(parsed.query)
        try:
            if method == "GET":
                return self._get(path, qs)
            return self._post(path, self._read_body())
        except TypeError as exc:
            return self._json(400, {"error": f"bad arguments: {exc}"})
        except Exception as exc:
            return self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def _get(self, path: str, qs: dict) -> None:
        if path == "/health":
            return self._json(200, {"status": "ok"})
        if path.startswith("/context/"):
            slug = path[len("/context/"):]
            max_tokens = int(qs.get("max_tokens", ["8000"])[0])
            return self._json(200, _run(cl.assemble_context(slug, max_tokens=max_tokens)))
        if path.startswith("/capsule/"):
            slug = path[len("/capsule/"):]
            return self._json(200, {"capsule": _run(capsule.export_capsule(slug))})
        if path == "/search":
            query = qs.get("q", [""])[0]
            mode = qs.get("mode", ["hybrid"])[0]
            limit = int(qs.get("limit", ["5"])[0])
            task_slug = qs.get("task_slug", [None])[0]
            search = SEARCH_MODES.get(mode)
            if not search:
                return self._json(400, {"error": f"unknown mode '{mode}'"})
            return self._json(200, _run(search(query, task_slug=task_slug, limit=limit)))
        return self._json(404, {"error": f"not found: {path}"})

    def _post(self, path: str, body: dict) -> None:
        if path == "/handoffs":
            return self._json(201, _run(cl.create_handoff(**body)))
        if path == "/summarize":
            return self._json(201, _run(auto_handoff.summarize_and_store(**body)))
        if path == "/sync":
            project_dir = body.get("project_dir")
            if not project_dir:
                return self._json(400, {"error": "missing 'project_dir'"})
            from context_layer import project_identity
            slug = project_identity.resolve_task_slug(project_dir)
            target = _run(capsule.sync_capsule(slug, project_dir))
            if not target:
                return self._json(404, {"error": f"no handoff for task '{slug}'"})
            return self._json(200, {"task_slug": slug, "synced": str(target)})
        return self._json(404, {"error": f"not found: {path}"})

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_OPTIONS(self):
        self._json(204, {})

    def log_message(self, fmt, *args):
        sys.stderr.write("[api] " + (fmt % args) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8123)
    args = parser.parse_args()

    try:
        asyncio.run(cl._ensure_embedder_loaded())
    except Exception as exc:
        print(f"🚧 Could not load the embedding model: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        print("   Run `python scripts/diagnostics.py` for details.", file=sys.stderr)
        return 1

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[Context Layer] API listening on http://{args.host}:{args.port}", file=sys.stderr)
    print("   Endpoints: /health /context/{slug} /capsule/{slug} /search "
          "POST /handoffs /summarize /sync", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())