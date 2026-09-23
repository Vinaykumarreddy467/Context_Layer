"""
Automatic trigger: watches cumulative token usage in a conversation and
fires a handoff on its own once a budget threshold is crossed -- this is
the piece that removes the need for anyone to manually decide "now."

Wire this into wherever you manage conversation state: an agent loop, a
wrapper around your model calls, a chat backend, etc. It is not itself a
standing service -- you call it from your own turn loop.
"""

from typing import Optional

from . import auto_handoff, project_identity
from .core import _estimate_tokens


class HandoffTrigger:
    def __init__(
        self,
        task_slug: Optional[str] = None,
        git_branch: str = "main",
        token_budget: int = 6000,
        cwd: Optional[str] = None,
    ):
        """
        task_slug: explicit override (raw manual control). If None, it is
        resolved from cwd via project_identity.resolve_task_slug() -- the
        same deterministic resolution every other adapter uses.
        """
        self.task_slug = task_slug or project_identity.resolve_task_slug(cwd or ".")
        self.git_branch = git_branch
        self.token_budget = token_budget
        self.running_tokens = 0
        self.last_handoff_id: Optional[str] = None
        self.transcript_buffer: list[str] = []

    def add_turn(self, role: str, content: str) -> None:
        """Call this once after every turn (user or assistant) in the conversation."""
        self.transcript_buffer.append(f"{role}: {content}")
        self.running_tokens += _estimate_tokens(content)

    async def maybe_trigger(self) -> Optional[dict]:
        """
        Call this right after add_turn(). If the token budget has been
        exceeded, this automatically summarizes and stores a handoff,
        chains it to the previous one, and resets the buffer so the next
        chunk of conversation starts fresh. Returns None if no trigger fired.
        """
        if self.running_tokens < self.token_budget:
            return None

        transcript = "\n".join(self.transcript_buffer)
        handoff = await auto_handoff.summarize_and_store(
            transcript=transcript,
            task_slug=self.task_slug,
            git_branch=self.git_branch,
            continues_from_id=self.last_handoff_id,
        )

        self.last_handoff_id = handoff["id"]
        self.transcript_buffer = []
        self.running_tokens = 0
        return handoff
