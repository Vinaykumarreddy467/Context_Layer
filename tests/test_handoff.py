import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import context_layer as cl

async def test():
    handoff = await cl.create_handoff(
        task_slug="test-task",
        git_branch="main",
        decisions=[{"text": "Testing the setup", "rationale": "Sanity check"}],
        next_steps=["Confirm this works"],
        raw_content="First test handoff.",
    )
    print("Created:", handoff)

    resumed = await cl.resume_handoff("test-task")
    print("Resumed:", resumed)

asyncio.run(test())