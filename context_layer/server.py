"""
MCP server exposing the context-layer as tools for any MCP-compatible
agent (Claude Code, Claude Desktop, Cursor, etc.) to call directly.

Requires: pip install "mcp[cli]"
Run with: python start_mcp.py
"""

import base64
import os
import shutil
import socket
import sys
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from surrealdb.data.types.datetime import Datetime, PreciseDatetime
from surrealdb.data.types.duration import Duration
from surrealdb.data.types.geometry import Geometry, GeometryCollection
from surrealdb.data.types.null import NullType
from surrealdb.data.types.range import Range
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table

from context_layer import auto_handoff
import context_layer as cl
from context_layer import export_capsule as capsule

mcp = FastMCP("context-layer")

# --- Zero-setup: auto-start SurrealDB + apply schema if needed ---
ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "data" / "handoffs.db"


def _db_reachable() -> bool:
    try:
        import asyncio

        async def probe():
            db = await cl._connect()
            try:
                await db.query("INFO FOR DB;")
            finally:
                await db.close()

        asyncio.run(probe())
        return True
    except Exception:
        return False


def _tcp_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _apply_schema() -> None:
    """Apply pending migrations from sql/migrations/."""
    import asyncio
    from pathlib import Path

    MIGRATIONS_DIR = ROOT / "sql" / "migrations"

    async def apply():
        db = await cl._connect()
        try:
            # Ensure schema_version table exists
            await db.query("""
                DEFINE TABLE IF NOT EXISTS schema_version SCHEMAFULL;
                DEFINE FIELD IF NOT EXISTS version ON schema_version TYPE int;
                DEFINE FIELD IF NOT EXISTS applied_at ON schema_version TYPE datetime DEFAULT time::now();
                DEFINE FIELD IF NOT EXISTS description ON schema_version TYPE string;
                DEFINE INDEX IF NOT EXISTS version_idx ON schema_version FIELDS version UNIQUE;
            """)

            # Get applied versions
            result = await db.query("SELECT version FROM schema_version ORDER BY version;")
            rows = result[0] if result else []
            applied = {r["version"] for r in rows}

            # Find all migration files
            migration_files = sorted(MIGRATIONS_DIR.glob("*.surql"))
            if not migration_files:
                print("schema: no migration files found", file=sys.stderr)
                return

            import re
            for mf in migration_files:
                match = re.match(r"(\d{4})_(.+)\.surql", mf.name)
                if not match:
                    print(f"schema: skipping {mf.name}: invalid name format", file=sys.stderr)
                    continue

                version = int(match.group(1))
                description = match.group(2).replace("_", " ")

                if version in applied:
                    continue

                print(f"schema: applying migration {version:04d}: {description}", file=sys.stderr)
                sql = mf.read_text(encoding="utf-8")
                for stmt in sql.split(";"):
                    stmt = stmt.strip()
                    if not stmt:
                        continue
                    try:
                        await db.query(stmt)
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            raise
                # Record migration
                await db.create("schema_version", {"version": version, "description": description})

        finally:
            await db.close()

    asyncio.run(apply())


def _ensure_surreal() -> None:
    """Start SurrealDB as a subprocess if not reachable, then apply schema.

The DB process outlives this server (intended): adapters and other tools
connect to the configured SurrealDB endpoint.
    """
    if not _db_reachable():
        import subprocess
        import time

        endpoint = urlsplit(cl.SURREAL_URL)
        host = endpoint.hostname or "127.0.0.1"
        port = endpoint.port or (443 if endpoint.scheme == "wss" else 8000)
        if _tcp_reachable(host, port):
            raise RuntimeError(
                f"SurrealDB is responding at {cl.SURREAL_URL}, but Context Layer could not "
                "authenticate or select the configured namespace/database. Check SURREAL_USER, "
                "SURREAL_PASS, SURREAL_NS, and SURREAL_DB in .env."
            )
        if not cl.SURREAL_PASS:
            raise RuntimeError(
                "SURREAL_PASS is missing. Copy .env.example to .env and set the local "
                "SurrealDB password before starting the MCP server."
            )
        if host not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError(
                f"SurrealDB is not reachable at {cl.SURREAL_URL}. This is not a local "
                "endpoint, so Context Layer cannot start a database process for it. Check "
                "the remote database service and .env settings."
            )
        surreal_executable = shutil.which("surreal")
        if not surreal_executable:
            raise RuntimeError(
                f"SurrealDB is not reachable at {cl.SURREAL_URL}, and the `surreal` "
                "executable is not on PATH. Install SurrealDB, then run "
                "`python scripts/diagnostics.py` for a readiness check."
            )

        print(f"[Context Layer] SurrealDB is asleep; starting it at {cl.SURREAL_URL}...",
              file=sys.stderr)
        DB_DIR.parent.mkdir(parents=True, exist_ok=True)
        db_log = DB_DIR.parent / "surrealdb.log"
        try:
            bind_address = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
            with db_log.open("wb") as log_file:
                proc = subprocess.Popen(
                    [surreal_executable, "start", "--username", cl.SURREAL_USER,
                     "--password", cl.SURREAL_PASS, "--bind", bind_address,
                     f"rocksdb://{DB_DIR}"],
                    stdout=log_file, stderr=subprocess.STDOUT,
                )
        except OSError as exc:
            raise RuntimeError(f"Could not launch SurrealDB: {exc}") from exc
        # Wait for readiness with timeout, capture stderr on failure
        for _ in range(30):
            time.sleep(1)
            if _db_reachable():
                print(f"[Context Layer] SurrealDB is ready at {cl.SURREAL_URL}.", file=sys.stderr)
                break
            if proc.poll() is not None:
                detail = db_log.read_text(encoding="utf-8", errors="replace")[-1200:].strip()
                raise RuntimeError(
                    "SurrealDB exited before it became ready. "
                    + (f"Startup detail: {detail}" if detail else f"See {db_log} for details.")
                )
        else:
            if proc.poll() is not None:
                detail = db_log.read_text(encoding="utf-8", errors="replace")[-1200:].strip()
                raise RuntimeError(
                    "SurrealDB exited before it became ready. "
                    + (f"Startup detail: {detail}" if detail else f"See {db_log} for details.")
                )
            raise RuntimeError(
                f"SurrealDB did not become ready at {cl.SURREAL_URL} within 30 seconds. "
                f"Check .env and the port; SurrealDB logs are at {db_log}."
            )
    _apply_schema()  # idempotent; safe on every start


def _safe(v):
    """Convert SurrealDB and Python values to JSON-safe MCP response values."""
    if isinstance(v, RecordID):
        return str(v)
    if isinstance(v, PreciseDatetime):
        return v.isoformat_with_nanoseconds()
    if isinstance(v, Datetime):
        return v.dt
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, NullType):
        return None
    if isinstance(v, Decimal):
        # JSON has no decimal type; a string avoids silently losing precision.
        return str(v)
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, bytes):
        return "base64:" + base64.b64encode(v).decode("ascii")
    if isinstance(v, Duration):
        return str(v)
    if isinstance(v, Range):
        return str(v)
    if isinstance(v, Table):
        return v.table_name
    if isinstance(v, Geometry):
        return {"type": type(v).__name__, "coordinates": _safe(v.get_coordinates())}
    if isinstance(v, GeometryCollection):
        return {"type": "GeometryCollection", "geometries": _safe(v.geometries)}
    if isinstance(v, Mapping):
        return {k: _safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_safe(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return sorted((_safe(x) for x in v), key=repr)
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    raise TypeError(f"Cannot convert {type(v).__name__} to a JSON-safe MCP value")


@mcp.tool()
async def create_handoff(
    task_slug: str,
    git_branch: str,
    decisions: list[dict],
    next_steps: list[str],
    raw_content: str,
    token_count: int = 0,
    continues_from_id: Optional[str] = None,
    *,
    platform_session_id: Optional[str] = None,
) -> dict:
    """
    Save a new handoff (context checkpoint) for a task.

    Call this when a conversation is getting long, a major milestone is
    reached, or a session is ending, so a future session can resume
    cleanly instead of re-explaining everything.

    decisions: list of {"text": "...", "rationale": "..."} objects --
        always include the *why*, not just the outcome, so a future
        session doesn't relitigate a settled choice.
    continues_from_id: id of a prior handoff (e.g. "handoff:abc123") to
        chain this one to, if this continues earlier work.
    platform_session_id: the originating platform's native session id,
        stored as metadata for debugging only -- never used to link
        handoffs (task_slug is the linking key).
    """
    return _safe(await cl.create_handoff(
        task_slug, git_branch, decisions, next_steps, raw_content,
        token_count, continues_from_id, platform_session_id=platform_session_id,
    ))


@mcp.tool()
async def resume_handoff(task_slug: str) -> Optional[dict]:
    """
    Load the most recent handoff for a task so a session can continue it
    without the user re-explaining context. Marks the handoff 'resumed'.
    Returns None if no handoff exists yet for this task_slug.
    """
    return _safe(await cl.resume_handoff(task_slug))


@mcp.tool()
async def search_handoffs(
    query: str, task_slug: Optional[str] = None, limit: int = 5
) -> list[dict]:
    """
    Full-text search across all saved handoffs. Optionally scope to one
    task_slug. Use this to find a past decision or context on a topic
    without knowing which specific handoff it's recorded in.
    """
    return _safe(await cl.search_handoffs(query, task_slug, limit))


@mcp.tool()
async def append_next_step(handoff_id: str, step: str) -> dict:
    """Add a next step to an existing handoff, e.g. 'handoff:abc123'."""
    return _safe(await cl.append_next_step(handoff_id, step))


@mcp.tool()
async def close_handoff(handoff_id: str) -> dict:
    """Mark a handoff as closed/done, e.g. 'handoff:abc123'."""
    return _safe(await cl.close_handoff(handoff_id))


@mcp.tool()
async def auto_summarize_handoff(
    transcript: str,
    task_slug: str,
    git_branch: str,
    continues_from_id: Optional[str] = None,
) -> dict:
    """
    Automatically extract decisions, next steps, and a summary from a raw
    conversation transcript, then save it as a handoff -- no manual
    decisions/next_steps writing required. Use this instead of
    create_handoff when you have raw conversation text rather than
    already-structured fields.
    """
    return _safe(await auto_handoff.summarize_and_store(
        transcript, task_slug, git_branch, continues_from_id
    ))


@mcp.tool()
async def semantic_search_handoffs(
    query: str, task_slug: Optional[str] = None, limit: int = 5
) -> list[dict]:
    """
    Semantic (meaning-based) search across handoff content using local
    embeddings -- finds related context even when the exact words don't
    match. Use this when keyword search misses, or to find conceptually
    similar past work. Runs fully offline, no API key.
    """
    return _safe(await cl.semantic_search_handoffs(query, task_slug, limit))


@mcp.tool()
async def hybrid_search_handoffs(
    query: str, task_slug: Optional[str] = None, limit: int = 5
) -> list[dict]:
    """
    Hybrid search: BM25 full-text + vector semantic, fused via reciprocal
    rank fusion (search::rrf). Best default for finding relevant past
    context -- catches exact terms AND paraphrases. Prefer this over
    search_handoffs or semantic_search_handoffs unless you need one mode.
    """
    return _safe(await cl.hybrid_search_handoffs(query, task_slug, limit))


@mcp.tool()
async def get_handoff_lineage(handoff_id: str) -> dict:
    """
    Walk the handoff chain for a handoff (e.g. 'handoff:abc123'): which
    handoffs it continues from (its history) and which continued from it
    (its successors). Use this to trace how a task evolved across sessions.
    """
    return _safe(await cl.get_handoff_lineage(handoff_id))


@mcp.tool()
async def find_handoffs_by_file(path: str, limit: int = 10) -> list[dict]:
    """
    Find handoffs that reference a file path: exact match or path suffix
    (e.g. 'auth.py' matches 'src/auth.py'). Answers 'which handoffs touched
    this file'. File references are extracted automatically at handoff
    creation from the transcript text.
    """
    return _safe(await cl.find_handoffs_by_file(path, limit))


@mcp.tool()
async def get_context_capsule(task_slug: str) -> str:
    """
    Get a portable markdown primer for a task, suitable for pasting into
    any AI chat -- including ones that don't support MCP (ChatGPT, Gemini,
    a bare API call, etc). Use this when the user wants to continue this
    work somewhere other than an MCP-connected agent.
    """
    return _safe(await capsule.export_capsule(task_slug))


@mcp.resource("context://current/{task_slug}")
async def current_context(task_slug: str) -> str:
    """
    MCP resource: auto-assembled current context for a task.
    Returns markdown with latest handoff, lineage, and related context.
    Agents can read this proactively without tool calls.
    """
    ctx = await cl.get_current_context(task_slug)
    if not ctx:
        return f"No context found for task: {task_slug}"
    return "\n\n".join(s["content"] for s in ctx["sections"])


@mcp.tool()
async def context_for_window(
    task_slug: str,
    max_tokens: int = 8000,
    semantic_query: Optional[str] = None,
) -> dict:
    """
    Get prioritized context for a task, truncated to fit within max_tokens.
    
    Returns assembled sections (latest handoff, lineage, semantic matches,
    same-branch tasks) with token counts. Use this when the agent needs
    to inject relevant context into a conversation with a limited window.
    
    max_tokens: target token budget (default 8000)
    semantic_query: custom query for semantic section (default: next_steps)
    """
    return _safe(await cl.assemble_context(
        task_slug, max_tokens, include_lineage=True, include_semantic=True, semantic_query=semantic_query
    ))


@mcp.tool()
async def summarize_for_window(
    task_slug: str,
    target_tokens: int = 4000,
) -> dict:
    """
    Auto-summarize a task's context to fit within target_tokens.
    If context exceeds budget, creates a new compressed handoff.
    
    Returns: {action: "none"|"compressed", new_handoff_id?, old_tokens, new_tokens, context}
    """
    return _safe(await cl.summarize_for_window(task_slug, target_tokens))


@mcp.tool()
async def token_budget_report(task_slug: str) -> dict:
    """
    Report on token usage for a task's context with recommendations.
    Use this to monitor window pressure and decide when to compress.
    """
    return _safe(await cl.get_token_budget_report(task_slug))


SKILLS_DIRS = [d for d in os.environ.get("SKILLS_DIRS", "").split(os.pathsep) if d]

# Cache for skills listing
_skills_cache: dict = {"mtime": 0, "skills": []}


def _skill_files():
    """Yield (name, path) for each SKILL.md: <dir> itself or <dir>/*/SKILL.md."""
    seen = set()
    for base in SKILLS_DIRS:
        base = Path(base)
        direct = base / "SKILL.md"
        paths = [direct] if direct.is_file() else sorted(base.glob("*/SKILL.md"))
        for path in paths:
            name = path.parent.name
            if name not in seen:  # ponytail: first dir wins on duplicates; merge if that matters
                seen.add(name)
                yield name, path


def _skill_meta(path):
    """name/description from SKILL.md frontmatter; dir name if absent."""
    # ponytail: naive scan, no yaml dep; multiline YAML values break it -- add pyyaml then
    name, desc = path.parent.name, ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"name": name, "description": desc}
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if line.startswith("name:"):
                name = line.partition(":")[2].strip()
            elif line.startswith("description:"):
                desc = line.partition(":")[2].strip()
    return {"name": name, "description": desc}


def _get_cached_skills():
    """Get skills with filesystem mtime-based cache invalidation."""
    global _skills_cache
    # Check if any skill directory has changed
    current_mtime = 0
    for base in SKILLS_DIRS:
        base_path = Path(base)
        if base_path.exists():
            for p in base_path.rglob("SKILL.md"):
                try:
                    current_mtime = max(current_mtime, p.stat().st_mtime)
                except OSError:
                    pass
    if current_mtime > _skills_cache["mtime"]:
        _skills_cache["skills"] = [_skill_meta(p) for _, p in _skill_files()]
        _skills_cache["mtime"] = current_mtime
    return _skills_cache["skills"]


@mcp.tool()
async def list_skills() -> dict:
    """
    List locally installed skill packs (SKILL.md) -- name + one-line
    description only. Call get_skill(name) to fetch one skill's full
    instructions. List first, fetch on demand; never preload them all.
    """
    return {"skills": _get_cached_skills()}


@mcp.tool()
async def get_skill(name: str) -> dict:
    """
    Fetch the full SKILL.md instructions for one locally installed skill
    by name (see list_skills). Follow the returned content for the task
    at hand.
    """
    for skill_name, path in _skill_files():
        if skill_name == name:
            return {"name": skill_name, "content": path.read_text(encoding="utf-8")}
    # ponytail: exact match only; add fuzzy matching if misses annoy
    return {"error": f"skill '{name}' not found. Call list_skills for available names."}


@mcp.tool()
async def ensure_project_ready(project_path: str, task_slug: str = "") -> dict:
    """
    Call FIRST on any project before other tools. Creates .vscode/mcp.json
    (central server entry) + .context-layer.json identity if missing, then
    returns {"ready": True, "slug": ...}. Pass project_path = workspace root.
    """
    # ponytail: sync disk writes inside async tool; thread off if slow
    import json as _json
    import sys as _sys
    from context_layer import project_identity as _pi
    from pathlib import Path as _Path
    root = _Path(project_path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    vscode = root / ".vscode" / "mcp.json"
    if not vscode.is_file():
        vscode.parent.mkdir(parents=True, exist_ok=True)
        server_root = ROOT
        vscode.write_text(_json.dumps({"servers": {"context-layer": {
            "type": "stdio", "command": _sys.executable, "args": ["start_mcp.py"],
            "cwd": str(server_root), "env": {}}}}, indent=2) + "\n",
            encoding="utf-8")
        created.append(".vscode/mcp.json")
    slug = task_slug or _pi.resolve_task_slug(str(root))
    if not (root / _pi.IDENTITY_FILE).is_file():
        slug = _pi.init_project_identity(str(root), slug if (task_slug or slug != root.name) else root.name)
        created.append(".context-layer.json")
    return {"ready": True, "slug": slug, "created": created}


def main() -> int:
    print("[Context Layer] Checking SurrealDB before starting MCP...", file=sys.stderr)
    try:
        _ensure_surreal()
    except Exception as exc:
        print("\n🚧 Context Layer could not get its database ready; the MCP server was not started.",
              file=sys.stderr)
        print(f"   {exc}", file=sys.stderr)
        print("   Check SurrealDB and .env, then run `python scripts/diagnostics.py`.", file=sys.stderr)
        return 1
    print("[Context Layer] SurrealDB and migrations are ready.", file=sys.stderr)

    try:
        # Warm the embedding model before MCP starts serving stdio requests.
        import asyncio
        asyncio.run(cl._ensure_embedder_loaded())
    except Exception as exc:
        print("\n🚧 SurrealDB is ready, but Context Layer could not load its embedding model.",
              file=sys.stderr)
        print(f"   {type(exc).__name__}: {exc}", file=sys.stderr)
        print("   Run `python scripts/diagnostics.py` for details.", file=sys.stderr)
        return 1

    print("[Context Layer] MCP is ready and waiting for a client over stdio.", file=sys.stderr)
    print("   This terminal is not an interactive prompt. Connect an MCP client or press Ctrl+C to stop.",
          file=sys.stderr)
    mcp.run()
    return 0


if __name__ == "__main__":
    main()
