# Graph Report - context_layer  (2026-09-21)

> **Generated snapshot:** This report predates the current `context_layer/` package layout and Codex adapter. References to the former `context_layer.py` module are historical. Do not use this generated graph as the current source tree or API reference; regenerate it from the current checkout before relying on its counts or relationships.

## Corpus Check
- Corpus is ~7,708 words - fits in a single context window. You may not need a graph.

## Summary
- 143 nodes · 217 edges · 15 communities (11 shown, 4 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 8 edges (avg confidence: 0.89)
- Token cost: 4,200 input · 2,100 output

## Community Hubs (Navigation)
- Core Data Layer
- MCP Server Tools
- Generic Loop Adapter
- Core Concepts
- Auto-Handoff Engine
- Copilot Hook Adapter
- Claude Code Hook Adapter
- E2E MCP Test
- Semantic MCP Test
- New Tools Test
- Capsule Export
- OpenCode Plugin
- MCP Runner
- MCP Dependency

## God Nodes (most connected - your core abstractions)
1. `_connect()` - 13 edges
2. `_safe()` - 13 edges
3. `create_handoff()` - 9 edges
4. `HandoffTrigger` - 9 edges
5. `summarize_and_store()` - 8 edges
6. `main()` - 7 edges
7. `resume_handoff()` - 6 edges
8. `semantic_search_handoffs()` - 6 edges
9. `main()` - 6 edges
10. `ContextLayerHooks` - 5 edges

## Surprising Connections (you probably didn't know these)
- `_latest_handoff_id()` --calls--> `_connect()`  [EXTRACTED]
  adapters/copilot/pre_compact.py → context_layer.py
- `main()` --calls--> `summarize_and_store()`  [EXTRACTED]
  adapters/copilot/pre_compact.py → auto_handoff.py
- `ContextLayerHooks` --uses--> `HandoffTrigger`  [INFERRED]
  adapters/generic_loop.py → trigger.py
- `_latest_handoff_id()` --calls--> `_connect()`  [EXTRACTED]
  adapters/opencode/save_before_compact.py → context_layer.py
- `summarize_and_store()` --calls--> `create_handoff()`  [EXTRACTED]
  auto_handoff.py → context_layer.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Offline semantic search pipeline** — readme_semantic_search, readme_embedding_model, readme_hnsw_index, readme_surrealdb, requirements_fastembed [INFERRED 0.85]
- **Handoff checkpointing flow across agents** — readme_handoff, readme_graph_lineage, readme_mcp_tools, adapters_proactive_instructions_instruction_based_checkpointing [INFERRED 0.75]

## Communities (15 total, 4 thin omitted)

### Community 0 - "Core Data Layer"
Cohesion: 0.10
Nodes (28): AsyncSurreal, append_next_step(), close_handoff(), _connect(), create_handoff(), _embed(), _get_embedder(), get_handoff_lineage() (+20 more)

### Community 1 - "MCP Server Tools"
Cohesion: 0.15
Nodes (22): append_next_step(), auto_summarize_handoff(), close_handoff(), create_handoff(), get_context_capsule(), get_handoff_lineage(), MCP server exposing the context-layer as tools for any MCP-compatible agent…, Automatically extract decisions, next steps, and a summary from a raw… (+14 more)

### Community 2 - "Generic Loop Adapter"
Cohesion: 0.15
Nodes (11): call_your_model(), ContextLayerHooks, get_next_user_message(), make_checkpoint_node(), Generic agent-loop adapter -- for ANY framework where you have access to each…, Pass an instance of this to your Agent's `hooks=` parameter., raw_loop_example(), HandoffTrigger (+3 more)

### Community 3 - "Core Concepts"
Cohesion: 0.18
Nodes (14): Cursor Setup, Instruction-Based Checkpointing, PreCompact Hook, Context Layer, BGE Small Embedding Model, Graph Lineage (continues_from), Handoff Record, HNSW Vector Index (+6 more)

### Community 4 - "Auto-Handoff Engine"
Cohesion: 0.25
Nodes (9): _latest_handoff_id(), main(), Small helper invoked by the OpenCode TypeScript plugin (compaction-plugin.ts)…, Anthropic, _get_client(), Auto-summarization: turns a raw conversation transcript into a structured…, Lazy client so importing this module works without ANTHROPIC_API_KEY., Extract a structured handoff from a raw transcript via Claude, then persist it… (+1 more)

### Community 5 - "Copilot Hook Adapter"
Cohesion: 0.36
Nodes (8): _get(), _git_branch(), _latest_handoff_id(), main(), VS Code Copilot Chat PreCompact hook adapter. IMPORTANT CAVEAT: Copilot's hook…, Try several possible field names, since the exact schema is unconfirmed., _read_transcript(), _task_slug()

### Community 6 - "Claude Code Hook Adapter"
Cohesion: 0.39
Nodes (7): _git_branch(), _latest_handoff_id(), main(), Claude Code PreCompact hook adapter. This is ONE adapter among several -- it's…, Claude Code transcripts are JSONL -- one JSON object per line, each…, _read_transcript(), _task_slug()

### Community 7 - "E2E MCP Test"
Cohesion: 0.50
Nodes (4): main(), call(), End-to-end MCP stdio test: spawn mcp_server.py, handshake, call every tool., req()

### Community 8 - "Semantic MCP Test"
Cohesion: 0.50
Nodes (4): main(), call(), MCP test for the 2 new tools, with stderr capture on timeout., req()

### Community 9 - "New Tools Test"
Cohesion: 0.50
Nodes (4): main(), call(), Test the 2 new tools (auto_summarize_handoff, get_context_capsule) without any…, req()

### Community 10 - "Capsule Export"
Cohesion: 0.50
Nodes (3): export_capsule(), Export a portable "context capsule" -- a plain markdown primer you can paste…, Build a pasteable markdown primer from the latest handoff for a task.

## Ambiguous Edges - Review These
- `Cursor Setup` → `PreCompact Hook`  [AMBIGUOUS]
  adapters/PROACTIVE_INSTRUCTIONS.md · relation: conceptually_related_to

## Knowledge Gaps
- **6 isolated node(s):** `BGE Small Embedding Model`, `HNSW Vector Index`, `fastembed dependency`, `surrealdb dependency`, `anthropic dependency` (+1 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 57 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Cursor Setup` and `PreCompact Hook`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `_connect()` connect `Core Data Layer` to `Auto-Handoff Engine`, `Copilot Hook Adapter`, `Claude Code Hook Adapter`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `summarize_and_store()` connect `Auto-Handoff Engine` to `Core Data Layer`, `MCP Server Tools`, `Copilot Hook Adapter`, `Claude Code Hook Adapter`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **What connects `BGE Small Embedding Model`, `HNSW Vector Index`, `fastembed dependency` to the rest of the system?**
  _6 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Core Data Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.09879032258064516 - nodes in this community are weakly interconnected._
- **Should `Generic Loop Adapter` be split into smaller, more focused modules?**
  _Cohesion score 0.14619883040935672 - nodes in this community are weakly interconnected._
