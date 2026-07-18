"""Optional LLM-judge layer on top of the deterministic checks.

Deterministic checks catch contract violations (hallucinated refs, missed
urgent items, secret leakage). What they can't measure is editorial quality:
would a human actually act on this briefing? That's what a model-graded
rubric is for. It's deliberately additive and optional — the core suite never
depends on a key — and judge scores are reported alongside, not blended into,
the deterministic total, so a rubric drift can't mask a grounding regression.
"""

from __future__ import annotations

import asyncio

from ..llm import EDITOR_MODEL, LLMBackend, extract_json

RUBRIC = """\
Score this morning briefing on three axes, each 1-5 (5 best):

- actionability: do priority items say what to DO, concretely, this morning?
- prioritization: is the ordering defensible — urgent above informational?
- concision: signal density; no filler, no repetition, nothing a busy reader
  would skip.

Reply with ONLY a JSON object:
{"actionability": n, "prioritization": n, "concision": n,
 "rationale": "<two sentences>"}"""


async def judge(backend: LLMBackend, briefing_markdown: str, model: str = EDITOR_MODEL) -> dict:
    reply = await backend.complete(model=model, system=RUBRIC, prompt=briefing_markdown)
    data = extract_json(reply)
    scores = {axis: int(data[axis]) for axis in ("actionability", "prioritization", "concision")}
    if not all(1 <= score <= 5 for score in scores.values()):
        raise ValueError(f"judge returned out-of-range scores: {scores}")
    return {**scores, "rationale": str(data.get("rationale", ""))}


def judge_sync(backend: LLMBackend, briefing_markdown: str, model: str = EDITOR_MODEL) -> dict:
    return asyncio.run(judge(backend, briefing_markdown, model))
