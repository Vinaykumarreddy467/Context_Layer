"""
Generic agent-loop adapter -- for ANY framework where you have access to
each turn as it happens (OpenAI Agents SDK, LangGraph, CrewAI, a custom
Python loop, etc). This is the "other agents" answer: unlike Claude Code's
PreCompact hook (platform-specific), this works with anything that lets
you run a bit of code after each turn.

The engine underneath (trigger.py's HandoffTrigger) is already
framework-agnostic -- this file just shows the wiring pattern for three
common cases. Copy whichever block matches your framework.
"""

import asyncio

from context_layer.trigger import HandoffTrigger


# ---------------------------------------------------------------------
# 1. Raw Python loop (works for literally anything -- a REPL, a script,
#    a custom orchestrator you already have)
# ---------------------------------------------------------------------

async def raw_loop_example():
    # task_slug is resolved from the current directory via
    # project_identity (env var -> .context-layer.json -> basename).
    # Pass task_slug=... explicitly only when you want manual control.
    trigger = HandoffTrigger(git_branch="main", token_budget=6000)

    while True:
        user_msg = get_next_user_message()       # replace with your own input source
        trigger.add_turn("user", user_msg)

        assistant_msg = call_your_model(user_msg)  # replace with your own model call
        trigger.add_turn("assistant", assistant_msg)

        # Call this after every turn. It's a no-op until the token
        # budget is crossed, at which point it summarizes, stores, and
        # resets automatically -- no manual decision needed.
        handoff = await trigger.maybe_trigger()
        if handoff:
            print(f"Auto-checkpointed: {handoff['id']}")


# ---------------------------------------------------------------------
# 2. OpenAI Agents SDK -- has a `hooks` / lifecycle-callback system.
#    Wire HandoffTrigger into whichever callback fires after each model
#    response (check the SDK's current docs for the exact hook name/
#    signature, since these evolve -- this shows the pattern, not a
#    guaranteed-current API call).
# ---------------------------------------------------------------------

class ContextLayerHooks:
    """Pass an instance of this to your Agent's `hooks=` parameter."""

    def __init__(self, task_slug: str | None = None, git_branch: str = "main"):
        self.trigger = HandoffTrigger(task_slug, git_branch)

    async def on_agent_end(self, context, agent, output):
        # Fires after each agent turn completes, per the SDK's lifecycle
        # hooks. Feed the turn's text into the trigger the same way as
        # the raw-loop example above.
        self.trigger.add_turn("assistant", str(output))
        await self.trigger.maybe_trigger()


# ---------------------------------------------------------------------
# 3. LangGraph -- wrap HandoffTrigger as a graph node that runs after
#    your main agent node, or call it inside a node's own function body.
# ---------------------------------------------------------------------

def make_checkpoint_node(task_slug: str | None = None, git_branch: str = "main"):
    trigger = HandoffTrigger(task_slug, git_branch)

    async def checkpoint_node(state):
        last_message = state["messages"][-1]
        trigger.add_turn(last_message.type, last_message.content)
        handoff = await trigger.maybe_trigger()
        if handoff:
            state["last_handoff_id"] = handoff["id"]
        return state

    return checkpoint_node


# Replace these two with your actual framework's I/O calls.
def get_next_user_message() -> str:
    raise NotImplementedError

def call_your_model(user_msg: str) -> str:
    raise NotImplementedError
