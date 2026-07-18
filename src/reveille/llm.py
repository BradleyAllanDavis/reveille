"""Thin LLM backend seam.

One protocol, two implementations: the real Anthropic client and a fake for
tests. Keeping the seam this narrow is what lets the whole pipeline — and the
evals harness — run deterministically in CI with no API key.
"""

from __future__ import annotations

import json
import re
from typing import Protocol

ANALYST_MODEL = "claude-haiku-4-5"
EDITOR_MODEL = "claude-sonnet-5"


class LLMBackend(Protocol):
    async def complete(self, *, model: str, system: str, prompt: str, max_tokens: int = 1500) -> str:
        ...


class AnthropicBackend:
    def __init__(self) -> None:
        from anthropic import AsyncAnthropic  # lazy: keeps offline paths import-free

        self._client = AsyncAnthropic()

    async def complete(self, *, model: str, system: str, prompt: str, max_tokens: int = 1500) -> str:
        msg = await self._client.messages.create(
            model=model,
            system=system,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in msg.content if block.type == "text")


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict:
    """Parse a JSON object out of a model reply, tolerating code fences and prose."""
    match = _FENCE.search(text)
    if match:
        text = match.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object found in reply: {text[:200]!r}")
    return json.loads(text[start : end + 1])
