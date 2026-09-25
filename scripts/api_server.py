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
  POST /sync                            -> write CONTEXT.md in a project dir (defaults to repo root)

Auth: if CONTEXT_LAYER_API_KEY is set, every request needs
  Authorization: Bearer <key>  or  X-API-Key: <key>

Run:  python scripts/api_server.py [--host 127.0.0.1] [--port 8123]
"""
import argparse
import asyncio
import json
import re
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

TASK_SLUG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
MAX_BODY_BYTES = 1024 * 1024  # 1 MiB


class ApiError(Exception):
    """Structured error: rendered as {"error": {"code", "message"}}."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _require_slug(slug: str) -> None:
    if not TASK_SLUG_RE.match(slug or ""):
        raise ApiError(
            400, "invalid_task_slug",
            "task_slug must match ^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$",
        )


def _parse_int(value: str, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(400, f"invalid_{name}", f"{name} must be an integer")


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

    def _error(self, status: int, code: str, message: str) -> None:
        return self._json(status, {"error": {"code": code, "message": message}})

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
            raise ApiError(400, "invalid_json", "request body is not valid JSON")

    def _route(self, method: str) -> None:
        if not self._auth_ok():
            return self._error(401, "unauthorized", "invalid or missing API key")
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > MAX_BODY_BYTES:
            return self._error(
                413, "body_too_large",
                f"request body exceeds {MAX_BODY_BYTES} bytes",
            )
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        qs = parse_qs(parsed.query)
        try:
            if method == "GET":
                return self._get(path, qs)
            return self._post(path, self._read_body())
        except ApiError as exc:
            return self._error(exc.status, exc.code, exc.message)
        except TypeError as exc:
            return self._error(400, "bad_arguments", f"bad arguments: {exc}")
        except Exception as exc:
            return self._error(500, "internal_error", f"{type(exc).__name__}: {exc}")

    def _get(self, path: str, qs: dict) -> None:
        if path == "/health":
            return self._json(200, {"status": "ok"})
        if path.startswith("/context/"):
            slug = path[len("/context/"):]
            _require_slug(slug)
            max_tokens = _parse_int(qs.get("max_tokens", ["8000"])[0], "max_tokens")
            if not 256 <= max_tokens <= 32000:
                raise ApiError(
                    400, "invalid_max_tokens",
                    "max_tokens must be between 256 and 32000",
                )
            return self._json(200, _run(cl.assemble_context(slug, max_tokens=max_tokens)))
        if path.startswith("/capsule/"):
            slug = path[len("/capsule/"):]
            _require_slug(slug)
            return self._json(200, {"capsule": _run(capsule.export_capsule(slug))})
        if path == "/search":
            query = qs.get("q", [""])[0]
            mode = qs.get("mode", ["hybrid"])[0]
            limit = _parse_int(qs.get("limit", ["5"])[0], "limit")
            if not 1 <= limit <= 100:
                raise ApiError(400, "invalid_limit", "limit must be between 1 and 100")
            task_slug = qs.get("task_slug", [None])[0]
            if task_slug:
                _require_slug(task_slug)
            search = SEARCH_MODES.get(mode)
            if not search:
                raise ApiError(400, "invalid_mode", f"unknown mode '{mode}'")
            return self._json(200, _run(search(query, task_slug=task_slug, limit=limit)))
        raise ApiError(404, "not_found", f"not found: {path}")

    def _post(self, path: str, body: dict) -> None:
        if path == "/handoffs":
            _require_slug(body.get("task_slug", ""))
            for field in ("decisions", "next_steps", "raw_content"):
                if field not in body:
                    raise ApiError(400, "missing_field", f"missing required field '{field}'")
            return self._json(201, _run(cl.create_handoff(**body)))
        if path == "/summarize":
            _require_slug(body.get("task_slug", ""))
            return self._json(201, _run(auto_handoff.summarize_and_store(**body)))
        if path == "/sync":
            project_dir = body.get("project_dir") or str(ROOT)
            from context_layer import project_identity
            slug = project_identity.resolve_task_slug(project_dir)
            target = _run(capsule.sync_capsule(slug, project_dir))
            if not target:
                raise ApiError(404, "no_handoff", f"no handoff for task '{slug}'")
            return self._json(200, {"task_slug": slug, "synced": str(target)})
        raise ApiError(404, "not_found", f"not found: {path}")

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