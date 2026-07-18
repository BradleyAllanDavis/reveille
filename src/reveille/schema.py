"""Core data contracts.

Two halves, deliberately decoupled so the evals harness can score any
(snapshots, briefing) pair regardless of how the briefing was produced:

- ``SourceSnapshot`` / ``Entity``: the normalized, point-in-time view of one
  upstream source (Things, Home Assistant, UniFi, wiki). Adapters map raw
  source data into this shape; everything downstream is source-agnostic.
- ``Briefing``: the structured output contract. Every claim in a briefing
  carries ``SourceRef``s back into the snapshots, which is what makes
  hallucination detection a mechanical check instead of a vibe.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

SOURCES = ("things", "home_assistant", "unifi", "wiki")


class Entity(BaseModel):
    """One normalized fact from a source (a task, a sensor state, a client, a doc)."""

    id: str
    kind: str
    title: str
    attrs: dict[str, Any] = Field(default_factory=dict)


class SourceSnapshot(BaseModel):
    source: str
    captured_at: datetime
    entities: list[Entity] = Field(default_factory=list)

    def ids(self) -> set[str]:
        return {e.id for e in self.entities}


class SourceRef(BaseModel):
    """A citation from a briefing claim back to a snapshot entity."""

    source: str
    id: str

    @property
    def key(self) -> str:
        return f"{self.source}:{self.id}"


class Item(BaseModel):
    headline: str
    detail: str = ""
    priority: int = Field(default=2, ge=1, le=3)  # 1 = act today, 3 = FYI
    refs: list[SourceRef] = Field(default_factory=list)


class Section(BaseModel):
    source: str
    title: str
    summary: str = ""
    items: list[Item] = Field(default_factory=list)


class Briefing(BaseModel):
    generated_at: datetime
    executive_summary: str
    top_priorities: list[Item] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)

    def all_refs(self) -> list[SourceRef]:
        refs: list[SourceRef] = []
        for item in self.top_priorities:
            refs.extend(item.refs)
        for section in self.sections:
            for item in section.items:
                refs.extend(item.refs)
        return refs

    def to_markdown(self) -> str:
        lines = [f"# Morning briefing — {self.generated_at:%Y-%m-%d}", ""]
        lines += [self.executive_summary, ""]
        if self.top_priorities:
            lines.append("## Top priorities")
            for item in self.top_priorities:
                lines.append(f"- **{item.headline}**" + (f" — {item.detail}" if item.detail else ""))
            lines.append("")
        for section in self.sections:
            lines.append(f"## {section.title}")
            if section.summary:
                lines.append(section.summary)
            for item in section.items:
                lines.append(f"- {item.headline}" + (f" — {item.detail}" if item.detail else ""))
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"
