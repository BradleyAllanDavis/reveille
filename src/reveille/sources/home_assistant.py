"""Home Assistant adapter: raw ``/api/states`` payload -> SourceSnapshot.

``fetch()`` is the live path (long-lived access token, same REST surface the
control plane's ha-* tools use). Everything else works from a recorded states
payload, so tests and evals never need a running HA instance.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..schema import Entity, SourceSnapshot

LOW_BATTERY_PCT = 20


def fetch(base_url: str, token: str) -> list[dict[str, Any]]:
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/states",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def from_states(states: list[dict[str, Any]], captured_at: datetime | None = None) -> SourceSnapshot:
    """Normalize the interesting subset of an HA states payload.

    Interesting = actionable for a morning briefing: open doors/windows,
    low batteries, lights left on, unavailable devices. Everything else is
    noise at 7am.
    """
    entities: list[Entity] = []
    for state in states:
        entity_id = state["entity_id"]
        domain = entity_id.split(".", 1)[0]
        value = state.get("state")
        attrs = state.get("attributes", {})
        name = attrs.get("friendly_name", entity_id)

        if domain == "binary_sensor" and attrs.get("device_class") in ("door", "window", "opening"):
            if value == "on":
                entities.append(
                    Entity(id=entity_id, kind="open_contact", title=name, attrs={"state": value})
                )
        elif domain == "sensor" and attrs.get("device_class") == "battery":
            try:
                pct = float(value)
            except (TypeError, ValueError):
                continue
            if pct <= LOW_BATTERY_PCT:
                entities.append(
                    Entity(id=entity_id, kind="low_battery", title=name, attrs={"pct": pct})
                )
        elif domain == "light" and value == "on":
            entities.append(Entity(id=entity_id, kind="light_on", title=name, attrs={}))
        elif value == "unavailable":
            entities.append(Entity(id=entity_id, kind="unavailable", title=name, attrs={}))

    return SourceSnapshot(
        source="home_assistant",
        captured_at=captured_at or datetime.now(timezone.utc),
        entities=entities,
    )


def from_fixture(path: str | Path) -> SourceSnapshot:
    return from_states(json.loads(Path(path).read_text()))
