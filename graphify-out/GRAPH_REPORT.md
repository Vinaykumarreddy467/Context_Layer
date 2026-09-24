# Graph Report - context_layer  (2026-09-24)

## Corpus Check
- Corpus is ~21,085 words - fits in a single context window. You may not need a graph.

## Summary
- 380 nodes · 579 edges · 36 communities (18 shown, 18 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Handoff Data and Search
- MCP Server and Capsules
- Environment and Readiness
- Copilot Handoff Adapter
- OpenCode and Project Identity
- Installation and Platform Setup
- Automatic Checkpoint Hook
- Generic Agent Loop Adapter
- Project Layout and Migrations
- Database Migration Runner
- Codex Lifecycle Hooks
- MCP Launchers
- Product Architecture Overview
- Context Assembly Regression
- MCP End-to-End Tests
- Semantic Search Tests
- Window Management Tests
- Skill Discovery Tests
- Agent Workflow Guidance
- OpenCode Compaction Plugin
- OpenCode Checkpoint Plugin
- Cursor MCP Configuration
- Reference Backfill Script
- MCP Convenience Runner
- Adapter Query Test
- Migration Tests
- Semantic Data Tests
- Python Package
- Context Layer Concept
- Local Security Guidance
- Anthropic Dependency
- Embedding Model Dependency
- MCP Dependency
- SurrealDB Dependency

## God Nodes (most connected - your core abstractions)
1. `_connect()` - 18 edges
2. `_safe()` - 16 edges
3. `assemble_context()` - 13 edges
4. `summarize_for_window()` - 11 edges
5. `main()` - 11 edges
6. `summarize_and_store()` - 10 edges
7. `resolve_task_slug()` - 10 edges
8. `HandoffTrigger` - 9 edges
9. `_run()` - 9 edges
10. `Repository structure` - 8 edges

## Surprising Connections (you probably didn't know these)
- `_save_handoff()` --calls--> `summarize_and_store()`  [EXTRACTED]
  adapters/codex/hook.py → context_layer/auto_handoff.py
- `main()` --calls--> `resolve_task_slug()`  [EXTRACTED]
  adapters/codex/hook.py → context_layer/project_identity.py
- `main()` --calls--> `resolve_task_slug()`  [EXTRACTED]
  adapters/copilot/pre_compact.py → context_layer/project_identity.py
- `ContextLayerHooks` --uses--> `HandoffTrigger`  [INFERRED]
  adapters/generic_loop.py → context_layer/trigger.py
- `main()` --calls--> `summarize_and_store()`  [EXTRACTED]
  adapters/opencode/save_before_compact.py → context_layer/auto_handoff.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Handoff context persistence and retrieval flow** — readme_project_handoffs, readme_surrealdb_storage, readme_mcp_interface, readme_context_assembly [EXTRACTED 1.00]

## Communities (36 total, 18 thin omitted)

### Community 0 - "Handoff Data and Search"
Cohesion: 0.06
Nodes (59): AsyncSurreal, append_next_step(), assemble_context(), _budget_recommendations(), check_api_key(), close_handoff(), _connect(), _count_tokens() (+51 more)

### Community 1 - "MCP Server and Capsules"
Cohesion: 0.06
Nodes (54): export_capsule(), Export a portable "context capsule" -- a plain markdown primer you can paste…, Build a pasteable markdown primer from the latest handoff for a task., append_next_step(), _apply_schema(), auto_summarize_handoff(), close_handoff(), context_for_window() (+46 more)

### Community 2 - "Environment and Readiness"
Cohesion: 0.12
Nodes (22): load_local_env(), Path, Load local environment settings without overriding the parent process., Read simple KEY=VALUE lines from the project .env file, if present., Namespace, Process, _check_database_and_migrations(), _check_embedding() (+14 more)

### Community 3 - "Copilot Handoff Adapter"
Cohesion: 0.13
Nodes (21): _get(), _git_branch(), _latest_handoff_id(), main(), VS Code Copilot Chat PreCompact hook adapter. IMPORTANT CAVEAT: Copilot's hook…, Try several possible field names, since the exact schema is unconfirmed., _read_transcript(), _clean() (+13 more)

### Community 4 - "OpenCode and Project Identity"
Cohesion: 0.13
Nodes (20): _git_branch(), _latest_handoff_id(), main(), Small helper invoked by the OpenCode TypeScript plugin (compaction-plugin.ts)…, init_project_identity(), main(), Project identity: deterministic task_slug resolution shared by every adapter…, Resolve the task_slug for a working directory. Env override wins, then the… (+12 more)

### Community 5 - "Installation and Platform Setup"
Cohesion: 0.19
Nodes (22): main(), One-command setup for context_layer: checks surreal, creates venv, installs…, claude_desktop_config_path(), deploy_hooks_and_plugin(), ensure_identity(), load_or_create_config(), main(), Path (+14 more)

### Community 6 - "Automatic Checkpoint Hook"
Cohesion: 0.15
Nodes (19): autoSlug(), { execFileSync }, fail(), fs, gitBranch(), GROWTH_PCT, latestHandoff(), main() (+11 more)

### Community 7 - "Generic Agent Loop Adapter"
Cohesion: 0.14
Nodes (12): call_your_model(), ContextLayerHooks, get_next_user_message(), make_checkpoint_node(), Generic agent-loop adapter -- for ANY framework where you have access to each…, Pass an instance of this to your Agent's `hooks=` parameter., raw_loop_example(), HandoffTrigger (+4 more)

### Community 8 - "Project Layout and Migrations"
Cohesion: 0.12
Nodes (15): Agent and framework adapters, Context Layer Python package, Entry points, Generated and local data, Lifecycle hooks, Repository structure, Schema files, Versioned SQL migrations (+7 more)

### Community 9 - "Database Migration Runner"
Cohesion: 0.24
Nodes (13): apply_migration(), _connect(), ensure_version_table(), get_applied_versions(), main(), Show migration status., Migration runner for Context Layer SurrealDB schema. Usage: python…, Create schema_version table if it doesn't exist. (+5 more)

### Community 10 - "Codex Lifecycle Hooks"
Cohesion: 0.36
Nodes (8): _git_branch(), _latest_handoff_id(), main(), Codex lifecycle adapter for loading and saving Context Layer handoffs. Codex…, Extract message text from Codex's JSONL transcript defensively. Codex documents…, _read_transcript(), _save_handoff(), _session_start()

### Community 11 - "MCP Launchers"
Cohesion: 0.32
Nodes (6): main(), Compatibility entry point; ``start_mcp.py`` is the friendly starter., main(), _project_python(), Path, Start Context Layer, check SurrealDB, and serve MCP over stdio.

### Community 12 - "Product Architecture Overview"
Cohesion: 0.25
Nodes (8): Client lifecycle adapters, Token-budgeted context assembly, Local-first memory service, MCP tools and resource interface, Project handoffs, Project identity via task_slug, Skill discovery MCP tools, SurrealDB handoff storage

### Community 14 - "MCP End-to-End Tests"
Cohesion: 0.50
Nodes (4): main(), call(), End-to-end MCP stdio test: spawn mcp_server.py, handshake, call every tool., req()

### Community 15 - "Semantic Search Tests"
Cohesion: 0.50
Nodes (4): main(), call(), MCP test for semantic search + lineage tools, with stderr capture on timeout., req()

### Community 16 - "Window Management Tests"
Cohesion: 0.50
Nodes (4): main(), call(), Test auto_summarize_handoff, get_context_capsule, and window tools without any…, req()

### Community 17 - "Skill Discovery Tests"
Cohesion: 0.50
Nodes (4): main(), call(), MCP stdio test for list_skills + get_skill., req()

### Community 18 - "Agent Workflow Guidance"
Cohesion: 0.50
Nodes (4): Agent-initiated checkpoint guidance, context_for_window retrieval, Handoff persistence guidance, MCP-only client checkpointing

## Knowledge Gaps
- **32 isolated node(s):** `Entry points`, `Generated and local data`, `Schema files`, `Manual database and connections`, `Migration workflow` (+27 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 170 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `load_local_env()` connect `Environment and Readiness` to `Handoff Data and Search`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `init_project_identity()` connect `OpenCode and Project Identity` to `Installation and Platform Setup`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **What connects `Entry points`, `Generated and local data`, `Schema files` to the rest of the system?**
  _32 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Handoff Data and Search` be split into smaller, more focused modules?**
  _Cohesion score 0.06393442622950819 - nodes in this community are weakly interconnected._
- **Should `MCP Server and Capsules` be split into smaller, more focused modules?**
  _Cohesion score 0.056866303690260134 - nodes in this community are weakly interconnected._
- **Should `Environment and Readiness` be split into smaller, more focused modules?**
  _Cohesion score 0.11965811965811966 - nodes in this community are weakly interconnected._
- **Should `Copilot Handoff Adapter` be split into smaller, more focused modules?**
  _Cohesion score 0.12681159420289856 - nodes in this community are weakly interconnected._