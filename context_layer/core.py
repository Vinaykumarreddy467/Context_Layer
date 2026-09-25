"""
Context Layer: core data-access functions for the handoff/ledger system.
Wraps SurrealDB so nothing downstream ever has to write SurrealQL.

Requires: pip install surrealdb
Schema is managed by the versioned migrations in `sql/migrations/`.
"""

import asyncio
import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Optional

from surrealdb import AsyncSurreal
from surrealdb.data.types.record_id import RecordID

# Separates the generated summary from captured transcript text in raw_content.
HANDOFF_CONTENT_SEPARATOR = "\n\n===CONTEXT_LAYER_SUMMARY_TRANSCRIPT_SEPARATOR===\n\n"

# Connect to a standalone `surreal start` server, not a second embedded
# instance -- two embedded processes can't safely share one RocksDB file.
SURREAL_URL = os.environ.get("SURREAL_URL", "ws://127.0.0.1:8010")
SURREAL_NS = os.environ.get("SURREAL_NS", "dev")
SURREAL_DB = os.environ.get("SURREAL_DB", "context_layer")
SURREAL_USER = os.environ.get("SURREAL_USER", "root")
SURREAL_PASS = os.environ.get("SURREAL_PASS", "")

# Multi-tenancy: optional namespace prefix for isolation (e.g., "user_123_")
# Set CONTEXT_LAYER_TENANT_PREFIX to enable. Empty = single-tenant (default).
TENANT_PREFIX = os.environ.get("CONTEXT_LAYER_TENANT_PREFIX", "")
# Auth: optional API key for MCP server (set CONTEXT_LAYER_API_KEY to enable)
API_KEY = os.environ.get("CONTEXT_LAYER_API_KEY", "")

# Local embedding model (fastembed, ONNX, offline, no API key).
# 384-dim vectors matching the HNSW index in context-layer-queries.surql.
_embedder = None
_embedder_loading = False
_embedder_ready = asyncio.Event()

async def _ensure_embedder_loaded():
    """Load embedder in background thread to avoid blocking event loop."""
    global _embedder, _embedder_loading
    if _embedder is not None:
        return
    if _embedder_loading:
        await _embedder_ready.wait()
        return
    _embedder_loading = True
    _embedder_ready.clear()
    try:
        from fastembed import TextEmbedding
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        _embedder = await loop.run_in_executor(
            None, lambda: TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        )
    except Exception:
        # Reset loading flag so future calls can retry
        _embedder_loading = False
        raise
    finally:
        # Always wake waiters: on success they see _embedder set; on
        # failure they fall through to _get_embedder() which raises.
        _embedder_ready.set()


def _get_embedder():
    """Get embedder, loading synchronously if not ready (fallback)."""
    global _embedder
    if _embedder is None:
        # Synchronous fallback - should only happen if called before async init
        from fastembed import TextEmbedding
        _embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _embedder


def _embed(text: str) -> list[float]:
    """Embed text locally into a 384-dim vector."""
    return list(_get_embedder().embed([text]))[0].tolist()


async def _embed_async(text: str) -> list[float]:
    """Async version that ensures embedder is loaded without blocking."""
    await _ensure_embedder_loaded()
    return list(_get_embedder().embed([text]))[0].tolist()


def _to_record_id(s: str) -> RecordID:
    """Parse 'handoff:abc' (or 'handoff:⟨...⟩') into a RecordID for RELATE."""
    table, _, key = s.partition(":")
    return RecordID(table, key.strip("⟨⟩"))


def _content_hash(raw_content: str) -> str:
    """SHA-256 over whitespace-normalized raw_content for duplicate detection."""
    normalized = " ".join(raw_content.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _tenant_ns(base_ns: str) -> str:
    """Apply tenant prefix to namespace for multi-tenancy isolation."""
    if TENANT_PREFIX:
        return f"{TENANT_PREFIX}{base_ns}"
    return base_ns


async def _connect(ns: Optional[str] = None, db: Optional[str] = None) -> AsyncSurreal:
    """Connect to SurrealDB. Optional ns/db override for multi-tenancy."""
    database = AsyncSurreal(SURREAL_URL)
    await database.connect()
    await database.signin({"username": SURREAL_USER, "password": SURREAL_PASS})
    await database.use(_tenant_ns(ns or SURREAL_NS), db or SURREAL_DB)
    return database


def check_api_key(provided: Optional[str]) -> bool:
    """Verify API key if auth is enabled. Returns True if valid or auth disabled."""
    if not API_KEY:
        return True  # auth disabled
    return provided == API_KEY


# --- File/ref extraction: first-class metadata on handoffs ---

_FILE_EXT = (
    r"py|ts|tsx|js|jsx|rs|go|java|kt|cs|cpp|c|h|hpp|rb|php|sql|json|jsonc|"
    r"yaml|yml|toml|md|html|css|scss|sh|ps1|bat|tf|vue|svelte|ipynb|txt|ini|"
    r"cfg|lock|mod|sum|xml|proto|graphql|surql|env"
)
# A path must not be embedded in another word or URL path segment.
# Second alternative: Windows absolute paths (C:\...\file.py) — the
# lookbehind in the first branch would reject them (segment preceded by \).
_FILE_RE = re.compile(
    r"(?<![\w/\\])(?:[\w./\\-]+\.(?:" + _FILE_EXT + r"))(?::\d+(?:-\d+)?)?"
    r"|(?<![A-Za-z])[A-Za-z]:[\\/][\w./\\-]*\.(?:" + _FILE_EXT + r")(?::\d+(?:-\d+)?)?",
    re.I,
)
# Match issue refs but not inside URLs - negative lookbehind for / or :
_REF_RE = re.compile(
    r"(?<![\w/:])(?:#\d+|(?:[A-Z][A-Z0-9]{1,9}-\d+)|(?:GH|PR)-?\d+)(?![\w-])"
)
_URL_REF_RE = re.compile(r"https?://[^\s)]+/(?:issues|pull|merge_requests)/\d+")
_TRAIL = ".,;:!?)]}>\"'"


def extract_files_refs(*texts: str) -> tuple[list[str], list[str]]:
    """Extract file paths and issue/requirement refs from handoff text.

    Files: path-like tokens with a known code/doc extension, optional :line.
    Refs: #123, ABC-123 (Jira), GH-123/PR-123, and issue/PR/merge URLs.
    Returns (files, refs), deduped in first-mention order, capped at 50 each.
    """
    blob = "\n".join(t for t in texts if t)
    files, refs = [], []
    for m in _FILE_RE.finditer(blob):
        f = m.group(0).rstrip(_TRAIL)
        if f not in files and _FILE_RE.fullmatch(f):
            files.append(f)
    for m in _REF_RE.finditer(blob):
        r = m.group(0)
        if r not in refs:
            refs.append(r)
    for m in _URL_REF_RE.finditer(blob):
        u = m.group(0).rstrip(_TRAIL)
        if u not in refs:
            refs.append(u)
    return files[:50], refs[:50]


# --- Context assembly helpers (new) ---

try:
    import tiktoken
except ModuleNotFoundError as exc:
    if exc.name != "tiktoken":
        raise
    tiktoken = None

if tiktoken is not None:
    # Errors from a broken install or unavailable encoding should surface;
    # only the optional package being absent uses the estimate fallback.
    _enc = tiktoken.get_encoding("cl100k_base")
    def _count_tokens(text: str) -> int:
        return len(_enc.encode(text))
else:
    # tiktoken is optional; use a rough estimate when it is not installed.
    def _count_tokens(text: str) -> int:
        return max(1, len(text) // 4)


def _estimate_tokens(text: str) -> int:
    """Token count using tiktoken if available, else rough estimate."""
    return _count_tokens(text)


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to roughly max_tokens, preferring to keep the end."""
    if _estimate_tokens(text) <= max_tokens:
        return text
    # Binary search for the truncation point
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _estimate_tokens(text[-mid:]) <= max_tokens:
            lo = mid
        else:
            hi = mid - 1
    if lo == 0:
        return "[truncated]"
    return "...[truncated]...\n" + text[-lo:]


def _fmt_decisions(decisions) -> str:
    return "\n".join(
        f"- {d.get('text', '')}: {d.get('rationale', '')}"
        for d in (decisions or [])
    )


def _fmt_steps(steps) -> str:
    return "\n".join(f"- {s}" for s in (steps or []))


async def assemble_context(
    task_slug: str,
    max_tokens: int = 8000,
    include_lineage: bool = True,
    include_semantic: bool = True,
    semantic_query: Optional[str] = None,
) -> dict:
    """
    Assemble a prioritized context package for a task within a token budget.
    
    Priority order (highest first):
    1. Latest handoff (decisions, next_steps, raw_content)
    2. Lineage chain (predecessor handoffs)
    3. Semantic search results for semantic_query (or latest next_steps as query)
    4. Related handoffs from same project (same git_branch)
    
    Each section is truncated to fit within max_tokens.
    """
    db = await _connect()
    try:
        # 1. Get latest handoff
        latest_result = await db.query(
            "SELECT * FROM handoff WHERE task_slug = $slug "
            "ORDER BY timestamp DESC LIMIT 1;",
            {"slug": task_slug},
        )
        latest_rows = latest_result[0] if latest_result else []
        if not latest_rows:
            return {"task_slug": task_slug, "sections": [], "total_tokens": 0}
        
        latest = latest_rows[0]
        
        # Build sections with token budgets
        sections = []
        remaining = max_tokens
        
        # Section 1: Latest handoff (highest priority, gets ~40% of budget)
        latest_budget = int(max_tokens * 0.4)
        extra = ""
        if latest.get("files"):
            extra += "## Files\n" + "\n".join(f"- {f}" for f in latest["files"]) + "\n"
        if latest.get("refs"):
            extra += "## Refs\n" + "\n".join(f"- {r}" for r in latest["refs"]) + "\n"
        latest_content = f"""# Latest Handoff ({latest['id']})
## Task: {latest['task_slug']} | Branch: {latest.get('git_branch') or 'unknown'} | Status: {latest['status']}
## Decisions
{_fmt_decisions(latest.get('decisions', []))}
## Next Steps
{_fmt_steps(latest.get('next_steps', []))}
{extra}## Raw Content
{latest.get('raw_content', '')}"""
        latest_truncated = _truncate_to_tokens(latest_content, latest_budget)
        sections.append({
            "name": "latest_handoff",
            "priority": 1,
            "tokens": _estimate_tokens(latest_truncated),
            "content": latest_truncated,
        })
        remaining -= sections[-1]["tokens"]
        
        # Section 2: Lineage (if requested and budget allows)
        if include_lineage and remaining > 500:
            lineage_budget = min(int(max_tokens * 0.3), remaining - 500)
            backward = await db.query(
                "SELECT * FROM type::record($id)->continues_from->handoff;",
                {"id": latest["id"]},
            )
            lineage_rows = backward[0] if backward else []
            if lineage_rows:
                lineage_content = "# Lineage (Predecessor Handoffs)\n"
                for h in lineage_rows:
                    lineage_content += f"\n## {h['id']} ({h['task_slug']})\n"
                    lineage_content += f"Decisions:\n{_fmt_decisions(h.get('decisions', []))}\n"
                    lineage_content += f"Next Steps:\n{_fmt_steps(h.get('next_steps', []))}\n"
                    lineage_content += f"Content: {h.get('raw_content', '')[:500]}...\n"
                lineage_truncated = _truncate_to_tokens(lineage_content, lineage_budget)
                sections.append({
                    "name": "lineage",
                    "priority": 2,
                    "tokens": _estimate_tokens(lineage_truncated),
                    "content": lineage_truncated,
                })
                remaining -= sections[-1]["tokens"]
        
        # Section 3: Related context via hybrid search (BM25 + vector, RRF-fused)
        if include_semantic and remaining > 500:
            semantic_budget = min(int(max_tokens * 0.2), remaining - 500)
            # Better fallback: use summary or raw_content excerpt instead of just task_slug
            fallback_query = (
                semantic_query 
                or " ".join(latest.get("next_steps", [])[:3]) 
                or latest.get("summary", "")[:200]
                or latest.get("raw_content", "")[:200]
                or task_slug
            )
            semantic_rows = await hybrid_search_handoffs(fallback_query, task_slug=task_slug, limit=5)
            if semantic_rows:
                semantic_content = f"# Related Context (hybrid search: '{fallback_query}')\n"
                for h in semantic_rows:
                    if h["id"] == latest["id"]:
                        continue  # skip self
                    semantic_content += f"\n## {h['id']} (relevance: {h.get('rrf_score', 0):.2f})\n"
                    semantic_content += h.get("raw_content", "")[:300] + "...\n"
                semantic_truncated = _truncate_to_tokens(semantic_content, semantic_budget)
                sections.append({
                    "name": "semantic_related",
                    "priority": 3,
                    "tokens": _estimate_tokens(semantic_truncated),
                    "content": semantic_truncated,
                })
                remaining -= sections[-1]["tokens"]
        
        # Section 4: Same-branch handoffs (if budget allows and branch known)
        if remaining > 500 and latest.get("git_branch"):
            branch_budget = min(int(max_tokens * 0.1), remaining - 500)
            branch_result = await db.query(
                "SELECT * FROM handoff WHERE git_branch = $branch AND task_slug != $slug "
                "ORDER BY timestamp DESC LIMIT 3;",
                {"branch": latest["git_branch"], "slug": task_slug},
            )
            branch_rows = branch_result[0] if branch_result else []
            if branch_rows:
                branch_content = f"# Other Tasks on Branch '{latest['git_branch']}'\n"
                for h in branch_rows:
                    branch_content += f"\n## {h['id']} ({h['task_slug']})\n"
                    branch_content += f"Decisions:\n{_fmt_decisions(h.get('decisions', []))}\n"
                    branch_content += f"Next Steps:\n{_fmt_steps(h.get('next_steps', []))}\n"
                branch_truncated = _truncate_to_tokens(branch_content, branch_budget)
                sections.append({
                    "name": "same_branch",
                    "priority": 4,
                    "tokens": _estimate_tokens(branch_truncated),
                    "content": branch_truncated,
                })
        
        total_tokens = sum(s["tokens"] for s in sections)
        return {
            "task_slug": task_slug,
            "latest_handoff_id": str(latest["id"]),
            "sections": sections,
            "total_tokens": total_tokens,
            "max_tokens": max_tokens,
        }
    finally:
        await db.close()


async def get_current_context(task_slug: str) -> Optional[dict]:
    """
    Get the minimal current context for a task: latest handoff + immediate lineage.
    Lightweight version of assemble_context for quick access.
    """
    return await assemble_context(task_slug, max_tokens=4000, include_lineage=True, include_semantic=False)


# --- Existing functions ---


async def create_handoff(
    task_slug: str,
    git_branch: Optional[str] = None,
    decisions: Optional[list[dict]] = None,
    next_steps: Optional[list[str]] = None,
    raw_content: str = "",
    token_count: int = 0,
    continues_from_id: Optional[str] = None,
    summary: str = "",
    *,
    platform_session_id: Optional[str] = None,
) -> dict:
    """Create a new handoff, optionally chained to a predecessor by id.

    platform_session_id: the originating platform's native session id
    (e.g. Claude Code's session_id), stored purely as metadata for
    debugging/traceability. It is NOT a linking key -- task_slug is the
    only thing that links handoffs across platforms.

    Duplicate guard: hooks (PreCompact + SessionEnd) can fire twice with
    identical content. A handoff with the same task_slug AND the same
    normalized content (content_hash) stored within the last 60 seconds
    is treated as a duplicate and the existing record is returned.
    platform_session_id alone is never a duplicate signal.
    """
    decisions = decisions or []
    next_steps = next_steps or []
    db = await _connect()
    try:
        content_hash = _content_hash(raw_content)
        dup = await db.query(
            "SELECT * FROM handoff WHERE task_slug = $slug AND content_hash = $hash "
            "AND timestamp > time::now() - 60s ORDER BY timestamp DESC LIMIT 1;",
            {"slug": task_slug, "hash": content_hash},
        )
        rows = dup[0] if dup else []
        if rows:
            return rows[0]

        files, refs = extract_files_refs(
            raw_content, summary,
            " ".join(d.get("text", "") for d in decisions),
            " ".join(next_steps),
        )
        data = {
            "task_slug": task_slug,
            "git_branch": git_branch,
            "status": "open",
            "version": 1,
            "decisions": decisions,
            "next_steps": next_steps,
            "raw_content": raw_content,
            "summary": summary,
            "platform_session_id": platform_session_id,
            "token_count": token_count,
            "files": files,
            "refs": refs,
            "content_hash": content_hash,
            "embedding": await _embed_async(raw_content),
            # timestamp omitted: schema default time::now() sets it
        }

        if continues_from_id:
            # Validate the predecessor up front: RELATE to a missing record
            # silently creates a dangling edge instead of failing.
            prev = _to_record_id(continues_from_id)
            exists = await db.query(
                "SELECT VALUE count() FROM type::record($prev) GROUP ALL;",
                {"prev": prev},
            )
            if not exists or not exists[0] or not exists[0][0]:
                raise ValueError(f"continues_from_id not found: {continues_from_id}")
            # Create the handoff and its lineage edge atomically: if any
            # statement fails the transaction rolls back, so no orphan
            # handoff is left behind.
            result = await db.query(
                "BEGIN TRANSACTION; "
                "LET $new = CREATE handoff CONTENT $data; "
                "LET $new_id = $new[0].id; "
                "RELATE $new_id->continues_from->$prev; "
                "COMMIT TRANSACTION; "
                "SELECT * FROM $new_id;",
                {"data": data, "prev": prev},
            )
            rows = result[-1] if result else []
            if not rows:
                raise RuntimeError("handoff created but lineage could not be confirmed")
            return rows[0]

        created = await db.create("handoff", data)
        return created[0] if isinstance(created, list) else created
    finally:
        await db.close()


async def get_latest_handoff(task_slug: str) -> Optional[dict]:
    """Fetch the most recent handoff for a task, without side effects."""
    db = await _connect()
    try:
        result = await db.query(
            "SELECT * FROM handoff WHERE task_slug = $slug "
            "ORDER BY timestamp DESC LIMIT 1;",
            {"slug": task_slug},
        )
        rows = result[0] if result else []
        return rows[0] if rows else None
    finally:
        await db.close()


async def resume_handoff(task_slug: str) -> Optional[dict]:
    """Fetch the most recent handoff for a task and mark it resumed."""
    latest = await get_latest_handoff(task_slug)
    if not latest:
        return None
    db = await _connect()
    try:
        return await db.update(latest["id"]).merge({"status": "resumed"})
    finally:
        await db.close()


async def search_handoffs(
    query: str, task_slug: Optional[str] = None, limit: int = 5
) -> list[dict]:
    """Full-text (BM25) search across handoff content."""
    db = await _connect()
    try:
        if task_slug:
            sql = (
                "SELECT id, task_slug, raw_content, files, refs, timestamp, "
                "search::score(1) AS relevance FROM handoff "
                "WHERE task_slug = $slug AND raw_content @1@ $q "
                "ORDER BY relevance DESC LIMIT $limit;"
            )
            params = {"slug": task_slug, "q": query, "limit": limit}
        else:
            sql = (
                "SELECT id, task_slug, raw_content, files, refs, timestamp, "
                "search::score(1) AS relevance FROM handoff "
                "WHERE raw_content @1@ $q "
                "ORDER BY relevance DESC LIMIT $limit;"
            )
            params = {"q": query, "limit": limit}

        result = await db.query(sql, params)
        return result[0] if result else []
    finally:
        await db.close()


async def semantic_search_handoffs(
    query: str, task_slug: Optional[str] = None, limit: int = 5
) -> list[dict]:
    """Semantic (vector) search across handoff content, using the HNSW index."""
    db = await _connect()
    try:
        vector = _embed(query)
        # Clamp limit to reasonable range for KNN literal
        k = max(1, min(int(limit), 100))
        if task_slug:
            sql = (
                "SELECT id, task_slug, raw_content, files, refs, timestamp, "
                "(1 - vector::distance::knn()) AS relevance FROM handoff "
                f"WHERE task_slug = $slug AND embedding <|{k}, 40|> $vector "
                "ORDER BY relevance DESC;"
            )
            params = {"slug": task_slug, "vector": vector}
        else:
            sql = (
                "SELECT id, task_slug, raw_content, files, refs, timestamp, "
                "(1 - vector::distance::knn()) AS relevance FROM handoff "
                f"WHERE embedding <|{k}, 40|> $vector "
                "ORDER BY relevance DESC;"
            )
            params = {"vector": vector}

        result = await db.query(sql, params)
        return result[0] if result else []
    finally:
        await db.close()


async def hybrid_search_handoffs(
    query: str, task_slug: Optional[str] = None, limit: int = 5
) -> list[dict]:
    """Hybrid search: BM25 full-text + vector semantic, fused with reciprocal rank fusion (search::rrf)."""
    db = await _connect()
    try:
        vector = _embed(query)
        pool = max(limit * 4, 10)  # candidate pool per leg; rrf re-ranks
        k = int(pool)  # <|K, EF|> requires a literal integer, not a param
        # Clamp limit to reasonable range
        limit = max(1, min(int(limit), 100))
        if task_slug:
            sql = (
                "LET $vs = SELECT id, task_slug, raw_content, files, refs, timestamp, "
                "vector::distance::knn() AS distance FROM handoff "
                f"WHERE task_slug = $slug AND embedding <|{k}, 40|> $vector; "
                "LET $ft = SELECT id, task_slug, raw_content, files, refs, timestamp, "
                "search::score(1) AS score FROM handoff "
                "WHERE task_slug = $slug AND raw_content @1@ $q "
                "ORDER BY score DESC LIMIT $pool; "
                f"search::rrf([$vs, $ft], 60, {limit});"
            )
            params = {"slug": task_slug, "vector": vector, "q": query, "pool": pool}
        else:
            sql = (
                "LET $vs = SELECT id, task_slug, raw_content, files, refs, timestamp, "
                "vector::distance::knn() AS distance FROM handoff "
                f"WHERE embedding <|{k}, 40|> $vector; "
                "LET $ft = SELECT id, task_slug, raw_content, files, refs, timestamp, "
                "search::score(1) AS score FROM handoff "
                "WHERE raw_content @1@ $q "
                "ORDER BY score DESC LIMIT $pool; "
                f"search::rrf([$vs, $ft], 60, {limit});"
            )
            params = {"vector": vector, "q": query, "pool": pool}

        result = await db.query(sql, params)
        # SurrealDB 3.x returns fused array as last statement result; handle empty/malformed
        if not result:
            return []
        fused = result[-1]
        if not isinstance(fused, list):
            return []
        return fused[:limit]
    finally:
        await db.close()


async def find_handoffs_by_file(path: str, limit: int = 10) -> list[dict]:
    """Find handoffs referencing a file path: exact match or path suffix
    (e.g. 'auth.py' matches 'src/auth.py'). Answers 'which handoffs touched
    this file'."""
    db = await _connect()
    try:
        result = await db.query(
            "SELECT id, task_slug, git_branch, timestamp, files, refs FROM handoff "
            "WHERE files != NONE AND string::contains(array::join(files, ' '), $path) "
            "ORDER BY timestamp DESC LIMIT $limit;",
            {"path": path, "limit": limit},
        )
        return result[0] if result else []
    finally:
        await db.close()


async def get_handoff_lineage(handoff_id: str) -> dict:
    """Walk the handoff chain: what this handoff continues from, and what continued from it."""
    db = await _connect()
    try:
        backward = await db.query(
            "SELECT * FROM type::record($id)->continues_from->handoff;",
            {"id": handoff_id},
        )
        forward = await db.query(
            "SELECT * FROM type::record($id)<-continues_from<-handoff;",
            {"id": handoff_id},
        )
        return {
            "handoff_id": handoff_id,
            "continues_from": backward[0] if backward else [],
            "continued_by": forward[0] if forward else [],
        }
    finally:
        await db.close()


async def append_next_step(handoff_id: str, step: str) -> dict:
    """Append a next step to an existing handoff without overwriting the array."""
    db = await _connect()
    try:
        result = await db.query(
            "UPDATE type::record($id) SET next_steps += $step RETURN AFTER;",
            {"id": handoff_id, "step": step},
        )
        return result[0][0]
    finally:
        await db.close()


async def close_handoff(handoff_id: str) -> dict:
    """Mark a handoff as closed."""
    db = await _connect()
    try:
        result = await db.query(
            "UPDATE type::record($id) MERGE $data RETURN AFTER;",
            {"id": handoff_id, "data": {"status": "closed"}},
        )
        rows = result[0] if result else []
        if not rows:
            raise ValueError(f"Handoff not found: {handoff_id}")
        return rows[0]
    finally:
        await db.close()


# --- Window management (new) ---

async def summarize_for_window(
    task_slug: str,
    target_tokens: int = 4000,
    max_raw_chars: int = 2000,
) -> dict:
    """
    Auto-summarize the task's context to fit within target_tokens.
    Creates a new handoff with compressed content if needed.
    
    Strategy:
    1. Get FULL context (no truncation)
    2. If already under budget, return as-is
    3. Otherwise, extract key info and create compressed handoff
    4. Return the compressed context
    """
    # Get full context without budget truncation
    ctx = await assemble_context(task_slug, max_tokens=32000)
    if ctx["total_tokens"] <= target_tokens:
        return {"action": "none", "context": ctx, "reason": "already within budget"}
    
    # Extract key info for compression
    db = await _connect()
    try:
        latest_result = await db.query(
            "SELECT * FROM handoff WHERE task_slug = $slug ORDER BY timestamp DESC LIMIT 1;",
            {"slug": task_slug},
        )
    finally:
        await db.close()
    latest_rows = latest_result[0] if latest_result else []
    if not latest_rows:
        return {"action": "none", "context": ctx, "reason": "no handoffs"}
    latest = latest_rows[0]
    
    # Build compressed content
    compressed = f"""# Compressed Context for {task_slug}
## Key Decisions
{_fmt_decisions(latest.get('decisions', []))}
## Active Next Steps
{_fmt_steps(latest.get('next_steps', []))}
## Summary
{latest.get('raw_content', '')[:max_raw_chars]}...
## Full Lineage: {len(await get_lineage_ids(latest['id']))} predecessor(s)
"""
    
    # Create new handoff with compressed content
    db = await _connect()
    try:
        files, refs = extract_files_refs(compressed)
        created = await db.create("handoff", {
            "task_slug": task_slug,
            "git_branch": latest.get("git_branch"),
            "status": "open",
            "decisions": latest.get("decisions", []),
            "next_steps": latest.get("next_steps", []),
            "raw_content": compressed,
            "token_count": _estimate_tokens(compressed),
            "files": files,
            "refs": refs,
            "content_hash": _content_hash(compressed),
            "embedding": await _embed_async(compressed),
        })
        record = created[0] if isinstance(created, list) else created
        return {
            "action": "compressed",
            "new_handoff_id": str(record["id"]),
            "old_tokens": ctx["total_tokens"],
            "new_tokens": _estimate_tokens(compressed),
            "context": await assemble_context(task_slug, max_tokens=target_tokens),
        }
    finally:
        await db.close()


async def get_lineage_ids(handoff_id: str, _seen: Optional[set[str]] = None) -> list:
    """Get all predecessor handoff IDs in the chain."""
    seen = _seen if _seen is not None else set()
    current_id = str(handoff_id)
    if current_id in seen:
        return []
    seen.add(current_id)
    db = await _connect()
    try:
        result = await db.query(
            "SELECT * FROM type::record($id)->continues_from->handoff;",
            {"id": handoff_id},
        )
        rows = result[0] if result else []
        ids = []
        # Recursively get deeper lineage while avoiding cyclic/repeated records.
        for r in rows:
            predecessor_id = str(r["id"])
            if predecessor_id in seen:
                continue
            ids.append(predecessor_id)
            ids.extend(await get_lineage_ids(predecessor_id, seen))
        return ids
    finally:
        await db.close()


async def get_token_budget_report(task_slug: str) -> dict:
    """
    Report on token usage for a task's context.
    Useful for monitoring and debugging window pressure.
    """
    ctx = await assemble_context(task_slug, max_tokens=32000)
    db = await _connect()
    try:
        latest_result = await db.query(
            "SELECT * FROM handoff WHERE task_slug = $slug ORDER BY timestamp DESC LIMIT 1;",
            {"slug": task_slug},
        )
    finally:
        await db.close()
    latest_rows = latest_result[0] if latest_result else []
    
    return {
        "task_slug": task_slug,
        "latest_handoff": str(latest_rows[0]["id"]) if latest_rows else None,
        "current_context_tokens": ctx["total_tokens"],
        "sections": [
            {"name": s["name"], "tokens": s["tokens"], "priority": s["priority"]}
            for s in ctx["sections"]
        ],
        "recommendations": _budget_recommendations(ctx["total_tokens"]),
    }


def _budget_recommendations(total_tokens: int) -> list[str]:
    """Generate recommendations based on token usage."""
    recs = []
    if total_tokens > 24000:
        recs.append("CRITICAL: Context exceeds typical 24k window; run summarize_for_window")
    elif total_tokens > 16000:
        recs.append("WARNING: Context >16k; consider compression before next model call")
    elif total_tokens > 8000:
        recs.append("NOTICE: Context >8k; monitor for window pressure")
    else:
        recs.append("OK: Context fits comfortably in standard windows")
    return recs
