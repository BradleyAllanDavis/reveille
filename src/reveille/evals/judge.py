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
from .cache import ResultCache, cache_key

# Bump when scoring logic changes in a way the rubric text and model id don't
# capture (parsing, validation, axes): it invalidates every cached verdict.
JUDGE_VERSION = "1"
JUDGE_MAX_TOKENS = 1500
AXES = ("actionability", "prioritization", "concision")

RUBRIC = """\
Score this morning briefing on three axes, each 1-5 (5 best):

- actionability: do priority items say what to DO, concretely, this morning?
- prioritization: is the ordering defensible — urgent above informational?
- concision: signal density; no filler, no repetition, nothing a busy reader
  would skip.

Reply with ONLY a JSON object:
{"actionability": n, "prioritization": n, "concision": n,
 "rationale": "<two sentences>"}"""


def _validated(data: dict) -> dict:
    try:
        scores = {axis: int(data[axis]) for axis in AXES}
    except OverflowError as exc:  # int(float("inf")): JSON admits Infinity and 1e999
        raise ValueError(f"judge returned a non-finite score: {exc}") from exc
    if not all(1 <= score <= 5 for score in scores.values()):
        raise ValueError(f"judge returned out-of-range scores: {scores}")
    return {**scores, "rationale": str(data.get("rationale", ""))}


async def judge(
    backend: LLMBackend, briefing_markdown: str, model: str = EDITOR_MODEL, max_tokens: int = JUDGE_MAX_TOKENS
) -> dict:
    reply = await backend.complete(model=model, system=RUBRIC, prompt=briefing_markdown, max_tokens=max_tokens)
    return _validated(extract_json(reply))


def judge_key(briefing_markdown: str, model: str = EDITOR_MODEL, max_tokens: int = JUDGE_MAX_TOKENS) -> str:
    return cache_key(
        step="judge",
        version=JUDGE_VERSION,
        rubric=RUBRIC,
        model=model,
        max_tokens=max_tokens,
        content=briefing_markdown,
    )


def cached_judge(
    backend: LLMBackend,
    briefing_markdown: str,
    cache: ResultCache | None,
    model: str = EDITOR_MODEL,
    max_tokens: int = JUDGE_MAX_TOKENS,
) -> tuple[dict, str]:
    """Return ``(verdict, status)``; status is ``hit``, ``miss`` or ``bypassed`` (cache is None).

    The *validated verdict* is cached, not the raw reply, so a malformed model reply
    is never memoized. A stored entry that fails the same validation is a miss."""
    if cache is None:
        return asyncio.run(judge(backend, briefing_markdown, model, max_tokens)), "bypassed"
    key = judge_key(briefing_markdown, model, max_tokens)
    stored = cache.get(key)
    if stored is not None:
        try:
            return _validated(stored), "hit"
        except (KeyError, TypeError, ValueError):
            pass
    verdict = asyncio.run(judge(backend, briefing_markdown, model, max_tokens))
    cache.put(key, verdict)
    return verdict, "miss"
