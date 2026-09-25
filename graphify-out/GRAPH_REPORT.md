# Graph Report - context_layer  (2026-09-25)

## Corpus Check
- 62 files · ~46,522 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: .surql 4, .example 1, (none) 1)

## Summary
- 485 nodes · 746 edges · 53 communities (35 shown, 18 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 13 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `37ccc0f6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- core.py
- server.py
- diagnostics.py
- project_identity.py
- Handler
- setup_mcp.py
- context-layer-checkpoint.js
- HandoffTrigger
- Repository structure
- run_migrations.py
- context-layer-handoff.js
- Getting started
- Project handoffs
- test_assemble_context_uses_fallback_query_in_semantic_heading
- test_mcp_e2e.py
- test_mcp_semantic.py
- test_new_tools.py
- test_skills.py
- Agent-initiated checkpoint guidance
- compaction-plugin.ts
- OpenCode Checkpoint Plugin
- Cursor MCP Configuration
- Reference Backfill Script
- MCP Convenience Runner
- Adapter Query Test
- Migration Tests
- Semantic Data Tests
- Python Package
- Context Layer
- Local-first deployment security
- anthropic dependency
- fastembed dependency
- mcp dependency
- surrealdb dependency
- SurrealDB migrations
- Architecture
- MCP reference
- Operations and security
- evaluate_retrieval.py
- test_api_and_sync.py
- Configuration
- Development
- handoff_cli.py
- Context primer: import-test
- auto_handoff.py
- hook.py
- export_capsule.py
- copilot/pre_compact.py
- hooks/pre_compact.py
- test_mcp_live.py
- save_before_compact.py

## God Nodes (most connected - your core abstractions)
1. `_connect()` - 19 edges
2. `_safe()` - 18 edges
3. `assemble_context()` - 13 edges
4. `Handler` - 12 edges
5. `summarize_for_window()` - 11 edges
6. `sync_capsule()` - 11 edges
7. `resolve_task_slug()` - 11 edges
8. `main()` - 11 edges
9. `summarize_and_store()` - 10 edges
10. `main()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `_save_handoff()` --calls--> `summarize_and_store()`  [EXTRACTED]
  adapters/codex/hook.py → context_layer/auto_handoff.py
- `_save_handoff()` --calls--> `sync_capsule()`  [EXTRACTED]
  adapters/codex/hook.py → context_layer/export_capsule.py
- `main()` --calls--> `resolve_task_slug()`  [EXTRACTED]
  adapters/codex/hook.py → context_layer/project_identity.py
- `main()` --calls--> `summarize_and_store()`  [EXTRACTED]
  adapters/copilot/pre_compact.py → context_layer/auto_handoff.py
- `main()` --calls--> `sync_capsule()`  [EXTRACTED]
  adapters/copilot/pre_compact.py → context_layer/export_capsule.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Handoff context persistence and retrieval flow** — readme_project_handoffs, readme_surrealdb_storage, readme_mcp_interface, readme_context_assembly [EXTRACTED 1.00]

## Communities (53 total, 18 thin omitted)

### Community 0 - "core.py"
Cohesion: 0.06
Nodes (62): AsyncSurreal, append_next_step(), assemble_context(), _budget_recommendations(), check_api_key(), close_handoff(), _connect(), _count_tokens() (+54 more)

### Community 1 - "server.py"
Cohesion: 0.05
Nodes (57): append_next_step(), _apply_schema(), auto_summarize_handoff(), close_handoff(), context_for_window(), create_handoff(), current_context(), _db_reachable() (+49 more)

### Community 2 - "diagnostics.py"
Cohesion: 0.12
Nodes (22): load_local_env(), Path, Load local environment settings without overriding the parent process., Read simple KEY=VALUE lines from the project .env file, if present., Namespace, Process, _check_database_and_migrations(), _check_embedding() (+14 more)

### Community 3 - "project_identity.py"
Cohesion: 0.27
Nodes (10): init_project_identity(), main(), Project identity: deterministic task_slug resolution shared by every adapter…, Resolve the task_slug for a working directory. Env override wins, then the…, Create .context-layer.json at cwd with a task_slug (a provided one, or a…, resolve_task_slug(), ensure_project_ready(), Call FIRST on any project before other tools. Creates .vscode/mcp.json (central… (+2 more)

### Community 4 - "Handler"
Cohesion: 0.23
Nodes (4): BaseHTTPRequestHandler, Handler, REST API for Context Layer, so ANY agent or script can read and write context…, _run()

### Community 5 - "setup_mcp.py"
Cohesion: 0.16
Nodes (25): install_windows_cli(), main(), Path, Expose the installed CLI globally for this Windows user., One-command setup for context_layer: checks surreal, creates venv, installs…, claude_desktop_config_path(), deploy_hooks_and_plugin(), ensure_identity() (+17 more)

### Community 6 - "context-layer-checkpoint.js"
Cohesion: 0.22
Nodes (12): autoSlug(), { execFileSync }, fail(), fs, gitBranch(), GROWTH_PCT, latestHandoff(), main() (+4 more)

### Community 7 - "HandoffTrigger"
Cohesion: 0.15
Nodes (11): call_your_model(), ContextLayerHooks, get_next_user_message(), make_checkpoint_node(), Generic agent-loop adapter -- for ANY framework where you have access to each…, Pass an instance of this to your Agent's `hooks=` parameter., raw_loop_example(), HandoffTrigger (+3 more)

### Community 8 - "Repository structure"
Cohesion: 0.25
Nodes (8): Agent and framework adapters, Context Layer Python package, Entry points, Generated and local data, Lifecycle hooks, Repository structure, Schema files, Versioned SQL migrations

### Community 9 - "run_migrations.py"
Cohesion: 0.24
Nodes (13): apply_migration(), _connect(), ensure_version_table(), get_applied_versions(), main(), Show migration status., Migration runner for Context Layer SurrealDB schema. Usage: python…, Create schema_version table if it doesn't exist. (+5 more)

### Community 10 - "context-layer-handoff.js"
Cohesion: 0.39
Nodes (8): autoSlug(), { execFileSync }, fail(), fs, main(), IMPORTANT: SurrealDB must be started with HTTP endpoint enabled:, resume(), summarize()

### Community 11 - "Getting started"
Cohesion: 0.25
Nodes (8): Common setup issues, Connect and verify, Getting started, Initialize a project, Install the service, Manual installation, Requirements, Run the MCP server directly

### Community 12 - "Project handoffs"
Cohesion: 0.25
Nodes (8): Client lifecycle adapters, Token-budgeted context assembly, Local-first memory service, MCP tools and resource interface, Project handoffs, Project identity via task_slug, Skill discovery MCP tools, SurrealDB handoff storage

### Community 14 - "test_mcp_e2e.py"
Cohesion: 0.50
Nodes (4): main(), call(), End-to-end MCP stdio test: spawn mcp_server.py, handshake, call every tool., req()

### Community 15 - "test_mcp_semantic.py"
Cohesion: 0.50
Nodes (4): main(), call(), MCP test for semantic search + lineage tools, with stderr capture on timeout., req()

### Community 16 - "test_new_tools.py"
Cohesion: 0.50
Nodes (4): main(), call(), Test auto_summarize_handoff, get_context_capsule, and window tools without any…, req()

### Community 17 - "test_skills.py"
Cohesion: 0.50
Nodes (4): main(), call(), MCP stdio test for list_skills + get_skill., req()

### Community 18 - "Agent-initiated checkpoint guidance"
Cohesion: 0.50
Nodes (4): Agent-initiated checkpoint guidance, context_for_window retrieval, Handoff persistence guidance, MCP-only client checkpointing

### Community 36 - "SurrealDB migrations"
Cohesion: 0.29
Nodes (7): Manual database and connections, Migration runner, Migration workflow, Reference schema file, schema_version tracking, SurrealDB migrations, Versioned schema migrations

### Community 37 - "Architecture"
Cohesion: 0.33
Nodes (6): Architecture, Automatic capture scope, Component map, Current deployment boundary, Handoff data, Retrieval and context assembly

### Community 38 - "MCP reference"
Cohesion: 0.33
Nodes (6): Assemble and export context, Client adapters, MCP reference, Save and manage handoffs, Search and trace, Skills and project setup

### Community 39 - "Operations and security"
Cohesion: 0.29
Nodes (7): Data handling CLI, Migrations, Operations and security, Readiness diagnostics, Security and privacy, Startup and database, Troubleshooting

### Community 40 - "evaluate_retrieval.py"
Cohesion: 0.47
Nodes (5): evaluate(), load_cases(), main(), Path, Evaluate Context Layer search against a hand-labeled JSON query set.

### Community 41 - "test_api_and_sync.py"
Cohesion: 0.60
Nodes (5): _free_port(), main(), Integration test for the REST API (scripts/api_server.py) and the CONTEXT.md…, _request(), _wait_ready()

### Community 42 - "Configuration"
Cohesion: 0.40
Nodes (5): Client configuration, Configuration, Environment variables, Local and generated files, Project identity

### Community 43 - "Development"
Cohesion: 0.40
Nodes (5): Code changes, Development, Install for development, Retrieval evaluation, Tests and data safety

### Community 44 - "handoff_cli.py"
Cohesion: 0.19
Nodes (16): _backup(), _check(), _consolidate(), _consolidate_local(), _export(), _forget(), _import(), main() (+8 more)

### Community 45 - "Context primer: import-test"
Cohesion: 0.40
Nodes (4): Context primer: import-test, Decisions already made (do not relitigate these), Next steps, Summary

### Community 46 - "auto_handoff.py"
Cohesion: 0.25
Nodes (10): _clean(), _extract_local(), _extract_with_claude(), _get_client(), Auto-summarization: turns a raw conversation transcript into a structured…, Extract a structured handoff from a raw transcript, then persist it through the…, Claude-based extraction (used only when ANTHROPIC_API_KEY is set)., Lazy Anthropic client so importing this module works without ANTHROPIC_API_KEY. (+2 more)

### Community 47 - "hook.py"
Cohesion: 0.36
Nodes (8): _git_branch(), _latest_handoff_id(), main(), Codex lifecycle adapter for loading and saving Context Layer handoffs. Codex…, Extract message text from Codex's JSONL transcript defensively. Codex documents…, _read_transcript(), _save_handoff(), _session_start()

### Community 48 - "export_capsule.py"
Cohesion: 0.28
Nodes (8): _capsule_text(), export_capsule(), Path, Export a portable "context capsule" -- a plain markdown primer you can paste…, Build the pasteable markdown primer from a handoff record., Build a pasteable markdown primer from the latest handoff for a task., Write the latest handoff capsule to CONTEXT.md in project_dir. Returns the…, sync_capsule()

### Community 49 - "copilot/pre_compact.py"
Cohesion: 0.39
Nodes (7): _get(), _git_branch(), _latest_handoff_id(), main(), VS Code Copilot Chat PreCompact hook adapter. IMPORTANT CAVEAT: Copilot's hook…, Try several possible field names, since the exact schema is unconfirmed., _read_transcript()

### Community 50 - "hooks/pre_compact.py"
Cohesion: 0.43
Nodes (6): _git_branch(), _latest_handoff_id(), main(), Claude Code PreCompact hook adapter. This is ONE adapter among several -- it's…, Claude Code transcripts are JSONL -- one JSON object per line, each…, _read_transcript()

### Community 51 - "test_mcp_live.py"
Cohesion: 0.53
Nodes (5): check(), _json(), main(), Live MCP test: drive the Context Layer MCP server over stdio with a real MCP…, _text()

### Community 52 - "save_before_compact.py"
Cohesion: 0.60
Nodes (4): _git_branch(), _latest_handoff_id(), main(), Small helper invoked by the OpenCode TypeScript plugin (compaction-plugin.ts)…

## Knowledge Gaps
- **65 isolated node(s):** `C:\Users\Vinaykumar.R\Downloads\context_layer\context_layer\venv\Scripts\python.exe`, `{ execFileSync }`, `fs`, `TOKENS`, `MIN_INTERVAL` (+60 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 224 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `init_project_identity()` connect `project_identity.py` to `setup_mcp.py`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `load_local_env()` connect `diagnostics.py` to `core.py`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **What connects `C:\Users\Vinaykumar.R\Downloads\context_layer\context_layer\venv\Scripts\python.exe`, `{ execFileSync }`, `fs` to the rest of the system?**
  _65 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `core.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06057692307692308 - nodes in this community are weakly interconnected._
- **Should `server.py` be split into smaller, more focused modules?**
  _Cohesion score 0.053410893707033315 - nodes in this community are weakly interconnected._
- **Should `diagnostics.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11965811965811966 - nodes in this community are weakly interconnected._