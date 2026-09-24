"""Regression tests for context assembly failure paths."""

import asyncio

from context_layer import core


def test_assemble_context_uses_fallback_query_in_semantic_heading(monkeypatch):
    class FakeDatabase:
        async def query(self, _sql, _params=None):
            return [[{
                "id": "handoff:latest",
                "task_slug": "assembly-regression",
                "git_branch": "main",
                "status": "open",
                "decisions": [],
                "next_steps": ["Continue implementation"],
                "raw_content": "Latest context",
            }]]

        async def close(self):
            return None

    async def connect(_ns=None, _db=None):
        return FakeDatabase()

    async def hybrid_search(query, task_slug=None, limit=5):
        assert query == "Continue implementation"
        assert task_slug == "assembly-regression"
        assert limit == 5
        return [{
            "id": "handoff:related",
            "raw_content": "Related context",
            "rrf_score": 0.5,
        }]

    monkeypatch.setattr(core, "_connect", connect)
    monkeypatch.setattr(core, "hybrid_search_handoffs", hybrid_search)

    result = asyncio.run(core.assemble_context(
        "assembly-regression",
        max_tokens=4000,
        include_lineage=False,
        include_semantic=True,
    ))

    semantic = next(section for section in result["sections"]
                    if section["name"] == "semantic_related")
    assert "Continue implementation" in semantic["content"]
    assert "Related context" in semantic["content"]
