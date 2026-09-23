# Checkpointing from MCP-only clients

Some MCP clients do not provide a reliable event immediately before they compact or discard a conversation. In those clients, Context Layer can still be used, but checkpointing depends on the agent following instructions; it is not an automatic hook.

Add guidance like this to the client’s project rules or system prompt:

```text
You can use Context Layer MCP tools to keep durable project context.

- Resolve this project’s task_slug from its .context-layer.json file or the
  CONTEXT_LAYER_TASK_SLUG environment variable.
- At the start of work, call context_for_window with that task_slug to load
  relevant context. Use resume_handoff when you explicitly want to mark the
  latest handoff as resumed.
- At meaningful milestones or before ending a long task, save a handoff.
  Use create_handoff when decisions and next steps are already structured;
  use auto_summarize_handoff when you have a transcript to summarize.
- Search prior handoffs before asking the user to repeat project decisions.
- Include only work-relevant content. Do not save secrets or unrelated
  sensitive material in raw_content.
```

This approach depends on the agent remembering to call the tools. Use a client’s native lifecycle adapter where available for automatic session and compaction checkpoints. See the adapter table in the project README.
