# MCP reference

The Context Layer server exposes 17 MCP tools and the resource template `context://current/{task_slug}`. MCP clients generally start the server over stdio using the generated project configuration.

## Save and manage handoffs

| Tool | Use |
|---|---|
| `create_handoff` | Save structured decisions, next steps, content, and project/branch metadata. |
| `auto_summarize_handoff` | Extract a summary, decisions, and next steps from supplied transcript content and save it. |
| `append_next_step` | Add a next step to an existing handoff. |
| `close_handoff` | Mark a handoff complete. |
| `resume_handoff` | Return the latest handoff for a project and mark it resumed. |

## Search and trace

| Tool | Use |
|---|---|
| `search_handoffs` | Search handoffs by text, optionally scoped by project. |
| `semantic_search_handoffs` | Find handoffs by vector similarity. |
| `hybrid_search_handoffs` | Combine full-text and vector search. |
| `find_handoffs_by_file` | Find handoffs referring to a path or filename. |
| `get_handoff_lineage` | Inspect linked predecessor/successor handoffs. |

## Assemble and export context

| Tool/resource | Use |
|---|---|
| `context_for_window` | Assemble relevant project context for a token budget. |
| `summarize_for_window` | Request a compressed context summary for a target budget. |
| `token_budget_report` | Inspect stored context size and token budget guidance. |
| `get_context_capsule` | Export a portable Markdown primer. |
| `context://current/{task_slug}` | Read assembled context for the named project. |

## Skills and project setup

| Tool | Use |
|---|---|
| `list_skills` | List skill packs discovered from configured skill directories. |
| `get_skill` | Read the content of a named skill pack. |
| `ensure_project_ready` | Create missing project identity and VS Code MCP configuration for a supplied project path. |

Tool argument schemas are exposed by the server through MCP `tools/list`; use the connected client's tool inspector for the authoritative schema for the installed version.

Text and semantic search results include each handoff's `id` so callers can trace results and retrieval evaluation can compare them with labeled expected IDs.

## Client adapters

| Client/pattern | Integration | Behavior and caveat |
|---|---|---|
| Codex | `adapters/codex/hook.py` | Loads context at session start; saves before compaction and at session end. MCP server registration and project hook trust are separate client steps. |
| Claude Code | `hooks/pre_compact.py` | Captures at the configured `PreCompact` event. |
| VS Code Copilot | `adapters/copilot/pre_compact.py` | Pre-compaction integration; event/payload support depends on the client version. |
| OpenCode | `adapters/opencode/` | Plugins and hooks connect to session/compaction lifecycle events. |
| Custom Python agent | `adapters/generic_loop.py`, `context_layer/trigger.py` | Example token-threshold checkpoint flow. |
| MCP-only client | `adapters/PROACTIVE_INSTRUCTIONS.md` | Agent-initiated calls guided by project instructions; no automatic lifecycle hook. |

Host hook formats are subject to change. Adapters should fail without interrupting host work; review and trust generated local hooks before enabling them.
