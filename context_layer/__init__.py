"""Persistent, model-agnostic context storage for AI agent workflows."""

from .env import load_local_env

load_local_env()

from .core import (
    API_KEY,
    HANDOFF_CONTENT_SEPARATOR,
    SURREAL_DB,
    SURREAL_NS,
    SURREAL_PASS,
    SURREAL_URL,
    SURREAL_USER,
    TENANT_PREFIX,
    append_next_step,
    assemble_context,
    check_api_key,
    close_handoff,
    create_handoff,
    extract_files_refs,
    find_handoffs_by_file,
    get_current_context,
    get_handoff_lineage,
    get_lineage_ids,
    get_token_budget_report,
    hybrid_search_handoffs,
    resume_handoff,
    search_handoffs,
    semantic_search_handoffs,
    summarize_for_window,
)
from .core import _connect, _ensure_embedder_loaded

__all__ = [
    "API_KEY",
    "HANDOFF_CONTENT_SEPARATOR",
    "SURREAL_DB",
    "SURREAL_NS",
    "SURREAL_PASS",
    "SURREAL_URL",
    "SURREAL_USER",
    "TENANT_PREFIX",
    "append_next_step",
    "assemble_context",
    "check_api_key",
    "close_handoff",
    "create_handoff",
    "extract_files_refs",
    "find_handoffs_by_file",
    "get_current_context",
    "get_handoff_lineage",
    "get_lineage_ids",
    "get_token_budget_report",
    "hybrid_search_handoffs",
    "resume_handoff",
    "search_handoffs",
    "semantic_search_handoffs",
    "summarize_for_window",
    "_connect",
    "_ensure_embedder_loaded",
]
