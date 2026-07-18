"""The coordinator: fan-out analysts, fan-in editor.

Two composition paths, same output contract:

- ``compose()``: the multi-agent path. One analyst agent per source runs
  concurrently (cheap model, narrow system prompt, JSON-only output with a
  one-shot repair retry), then an editor agent writes the executive summary
  and picks top priorities from the analysts' items — it cannot invent new
  ones, which keeps every top priority traceable to a snapshot entity.
- ``compose_offline()``: a deterministic rule-based composer over the same
  snapshots. It exists so CI, tests, and eval fixtures never require an API
  key — and it doubles as the floor the LLM path must beat in the evals.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from pydantic import ValidationError

from .llm import ANALYST_MODEL, EDITOR_MODEL, LLMBackend, extract_json
from .schema import Briefing, Item, Section, SourceRef, SourceSnapshot

SECTION_TITLES = {
    "things": "Tasks",
    "home_assistant": "House",
    "unifi": "Network",
    "wiki": "Recently written",
}

ANALYST_SYSTEM = """\
You are the {source} analyst inside a morning-briefing pipeline. You receive a
JSON snapshot of entities from that source. Produce ONE JSON object, nothing
else, with this shape:

{{"summary": "<one-sentence section summary>",
  "items": [{{"headline": "...", "detail": "...", "priority": 1|2|3,
             "refs": [{{"source": "{source}", "id": "<entity id>"}}]}}]}}

Rules:
- Every item MUST cite at least one ref whose id is an entity id present in
  the snapshot. Never cite an id that is not in the snapshot.
- priority 1 = needs action today, 2 = worth knowing, 3 = FYI.
- At most 6 items. Skip noise. If nothing matters, return an empty items list
  and say so in the summary."""

EDITOR_SYSTEM = """\
You are the editor of a morning briefing. You receive the section drafts as
JSON. Produce ONE JSON object, nothing else:

{"executive_summary": "<2-3 sentences, the morning at a glance>",
 "top_priorities": [<up to 5 items copied VERBATIM (same headline, detail,
                     priority, refs) from the sections' items>]}

Rules:
- top_priorities must be exact copies of existing section items — never write
  new items or alter refs. Prefer priority 1, then 2.
- The executive summary mentions only facts present in the sections."""


class AnalystError(RuntimeError):
    pass


async def _complete_json(backend: LLMBackend, *, model: str, system: str, prompt: str) -> dict:
    """One repair retry: feed the parse/validation error back to the model."""
    reply = await backend.complete(model=model, system=system, prompt=prompt)
    try:
        return extract_json(reply)
    except ValueError as err:
        retry_prompt = (
            f"{prompt}\n\nYour previous reply was not parseable JSON ({err}). "
            "Reply with ONLY the JSON object."
        )
        reply = await backend.complete(model=model, system=system, prompt=retry_prompt)
        return extract_json(reply)


async def run_analyst(
    backend: LLMBackend, snapshot: SourceSnapshot, model: str = ANALYST_MODEL
) -> Section:
    system = ANALYST_SYSTEM.format(source=snapshot.source)
    prompt = snapshot.model_dump_json()
    data = await _complete_json(backend, model=model, system=system, prompt=prompt)
    try:
        return Section(
            source=snapshot.source,
            title=SECTION_TITLES.get(snapshot.source, snapshot.source),
            summary=data.get("summary", ""),
            items=[Item.model_validate(item) for item in data.get("items", [])],
        )
    except ValidationError as err:
        raise AnalystError(f"{snapshot.source} analyst returned invalid items: {err}") from err


async def run_editor(
    backend: LLMBackend, sections: list[Section], model: str = EDITOR_MODEL
) -> tuple[str, list[Item]]:
    prompt = "\n".join(section.model_dump_json() for section in sections)
    data = await _complete_json(backend, model=model, system=EDITOR_SYSTEM, prompt=prompt)
    priorities = [Item.model_validate(item) for item in data.get("top_priorities", [])][:5]
    return data.get("executive_summary", ""), priorities


async def compose(snapshots: list[SourceSnapshot], backend: LLMBackend) -> Briefing:
    sections = list(
        await asyncio.gather(*(run_analyst(backend, snapshot) for snapshot in snapshots))
    )
    executive_summary, top_priorities = await run_editor(backend, sections)
    return Briefing(
        generated_at=datetime.now(timezone.utc),
        executive_summary=executive_summary,
        top_priorities=top_priorities,
        sections=sections,
    )


# --- deterministic path ----------------------------------------------------

_KIND_PRIORITY = {
    # things
    "overdue_task": 1,
    "today_task": 1,
    "deadline_task": 2,
    # home_assistant
    "open_contact": 1,
    "unavailable": 2,
    "low_battery": 2,
    "light_on": 3,
    # unifi
    "subsystem_degraded": 1,
    "new_client": 2,
    "client_count": 3,
    # wiki
    "recent_doc": 3,
}


def compose_offline(snapshots: list[SourceSnapshot]) -> Briefing:
    sections: list[Section] = []
    for snapshot in snapshots:
        items = [
            Item(
                headline=entity.title,
                detail=entity.kind.replace("_", " "),
                priority=_KIND_PRIORITY.get(entity.kind, 3),
                refs=[SourceRef(source=snapshot.source, id=entity.id)],
            )
            for entity in snapshot.entities
        ]
        items.sort(key=lambda item: item.priority)
        items = items[:6]
        counts = len(snapshot.entities)
        sections.append(
            Section(
                source=snapshot.source,
                title=SECTION_TITLES.get(snapshot.source, snapshot.source),
                summary=f"{counts} notable item(s) from {snapshot.source}.",
                items=items,
            )
        )

    all_items = [item for section in sections for item in section.items]
    all_items.sort(key=lambda item: item.priority)
    top = all_items[:5]
    urgent = sum(1 for item in all_items if item.priority == 1)
    summary = (
        f"{urgent} item(s) need action today across {len(sections)} sources; "
        f"{len(all_items)} notable in total."
    )
    return Briefing(
        generated_at=datetime.now(timezone.utc),
        executive_summary=summary,
        top_priorities=top,
        sections=sections,
    )
