"""
Auto-summarization: turns a raw conversation transcript into a structured
handoff automatically, then stores it through the context layer.

Two extraction paths:
  1. Claude API  -- used when ANTHROPIC_API_KEY is set (best quality)
  2. Local rules -- zero-dependency fallback so any agent/IDE (opencode,
     VS Code Copilot, Cursor, Claude Code, Codex, Qoder) can auto-summarize
     without an API key or network access.

Requires: pip install anthropic  (only for the Claude path)
"""

import json
import logging
import os
import re
from typing import Optional

import context_layer as cl

_client = None
logger = logging.getLogger("context-layer.auto-handoff")


def _get_client():
    """Lazy Anthropic client so importing this module works without ANTHROPIC_API_KEY."""
    global _client
    if _client is None:
        from anthropic import Anthropic
        _client = Anthropic()  # reads ANTHROPIC_API_KEY from env automatically
    return _client

EXTRACTION_PROMPT = """You are extracting a structured handoff from a raw \
conversation transcript, so a future AI session can resume this work \
without re-reading everything.

Respond with ONLY a JSON object (no markdown, no preamble, no code fences) \
matching this exact shape:
{
  "decisions": [{"text": "...", "rationale": "..."}],
  "next_steps": ["...", "..."],
  "summary": "A concise 2-4 sentence summary of what happened and where things stand."
}

Rules:
- Only include decisions that were actually settled, with the real reason \
they were made -- never invent a rationale that wasn't discussed.
- next_steps must be concrete and actionable, not vague ("continue work" \
is not acceptable; "add rate limiting to the login endpoint" is).
- Do not include anything not actually present in the transcript.

Transcript:
"""

# --- Local rule-based extraction (no API key) ---

_DECISION_RE = re.compile(
    r"(?i)\b(decision|decided|we chose|we'll use|we will use|we are using|"
    r"settled on|agreed on|going with|use \w+ over|prefer\b)"
)
_STEP_RE = re.compile(
    r"(?i)\b(next step|next:|todo|then |after that|follow up|remaining|"
    r"still need|still to do|to do next)\b"
)
_STRIP_RE = re.compile(
    r"^(?:\s*[-*•>#]+\s*|\s*(?:user|assistant|human|ai)\s*:\s*|"
    r"\s*(?:decision|decided|next step|next|todo)\s*:\s*)",
    re.I,
)


def _clean(line: str) -> str:
    for _ in range(3):  # strip stacked prefixes: "user: decision: ..."
        new = _STRIP_RE.sub("", line).strip()
        if new == line:
            break
        line = new
    return line.rstrip(".").strip()


def _extract_local(transcript: str) -> dict:
    """Heuristic extraction: decisions/steps from marker lines, summary from
    the first user message. Good enough to resume work; the Claude path is
    strictly better when a key is available."""
    decisions, steps = [], []
    
    # Process transcript in paragraphs to catch multi-line decisions/steps
    paragraphs = re.split(r'\n\s*\n', transcript)
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Check each line in paragraph
        for raw in para.splitlines():
            line = raw.strip()
            if not line:
                continue
            if _DECISION_RE.search(line) and len(line) < 500:
                text = _clean(line)
                if text and text not in [d["text"] for d in decisions]:
                    decisions.append({"text": text, "rationale": "stated in transcript"})
            elif _STEP_RE.search(line) and len(line) < 500:
                text = _clean(line)
                if text and text not in steps:
                    steps.append(text)
        # Also check the whole paragraph for decisions/steps (multi-line)
        if _DECISION_RE.search(para) and len(para) < 500:
            text = _clean(para)
            if text and text not in [d["text"] for d in decisions]:
                decisions.append({"text": text, "rationale": "stated in transcript"})
        elif _STEP_RE.search(para) and len(para) < 500:
            text = _clean(para)
            if text and text not in steps:
                steps.append(text)

    # Summary: first user message, truncated to ~3 sentences
    summary = ""
    for raw in transcript.splitlines():
        if re.match(r"(?i)^(user|human)\s*:", raw):
            summary = _clean(raw).strip()
            break
    if not summary:
        summary = _clean(transcript.strip())[:280]
    summary = re.split(r"(?<=[.!?])\s+", summary)[:3]
    summary = " ".join(summary)[:400]

    return {
        "decisions": decisions[:8],
        "next_steps": steps[:8],
        "summary": summary or "Session transcript captured for context.",
    }


async def summarize_and_store(
    transcript: str,
    task_slug: str,
    git_branch: str,
    continues_from_id: Optional[str] = None,
    *,
    platform_session_id: Optional[str] = None,
) -> dict:
    """
    Extract a structured handoff from a raw transcript, then persist it
    through the context layer. Uses Claude when ANTHROPIC_API_KEY is set,
    otherwise falls back to local rule-based extraction -- so it works in
    any agent/IDE with zero configuration.

    platform_session_id: the originating platform's native session id,
        stored as metadata for debugging only (never a linking key).
    """
    extraction_status = "local"
    extraction_warning = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            extracted = await _extract_with_claude(transcript)
            extraction_status = "claude"
        except Exception as e:
            # Keep handoff capture available, but report that its structured
            # fields came from the lower-confidence local rule-based extractor.
            extracted = _extract_local(transcript)
            extraction_status = "local_fallback"
            extraction_warning = (
                "Claude extraction failed "
                f"({type(e).__name__}: {e}); local rule-based extraction was used."
            )
            logger.warning("%s", extraction_warning)
            extracted["summary"] = (
                "[Warning: Claude extraction failed; local rule-based extraction was used.]\n\n"
                + extracted["summary"]
            )
    else:
        extracted = _extract_local(transcript)

    combined_content = (
        extracted.get("summary", "")
        + cl.HANDOFF_CONTENT_SEPARATOR
        + transcript
    )

    handoff = await cl.create_handoff(
        task_slug=task_slug,
        git_branch=git_branch,
        decisions=extracted.get("decisions", []),
        next_steps=extracted.get("next_steps", []),
        raw_content=combined_content,
        summary=extracted.get("summary", ""),
        token_count=len(transcript) // 4,  # rough estimate; swap for a real tokenizer if precision matters
        continues_from_id=continues_from_id,
        platform_session_id=platform_session_id,
    )
    # Keep extraction diagnostics in the tool result, not the persisted
    # schema-full handoff record, so API failures do not alter DB schema.
    handoff["extraction_status"] = extraction_status
    if extraction_warning:
        handoff["extraction_warning"] = extraction_warning
    return handoff


async def _extract_with_claude(transcript: str) -> dict:
    """Claude-based extraction (used only when ANTHROPIC_API_KEY is set)."""
    # Use a valid, current model; can be overridden via env
    model = os.environ.get("CONTEXT_LAYER_CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
    response = _get_client().messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": EXTRACTION_PROMPT + transcript}],
    )

    raw_text = response.content[0].text.strip()
    # Defensively strip code fences in case the model adds them anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    return json.loads(raw_text)
