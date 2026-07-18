"""UniFi adapter: raw controller payloads -> SourceSnapshot.

Works from a recorded ``{"health": [...], "clients": [...]}`` payload (the
shapes returned by ``/api/s/<site>/stat/health`` and ``/stat/sta``). A live
fetch path can be added behind the same normalizer when needed; the evals
harness only ever sees the normalized snapshot.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..schema import Entity, SourceSnapshot

NEW_CLIENT_WINDOW_S = 24 * 3600


def from_payload(payload: dict[str, Any], captured_at: datetime | None = None) -> SourceSnapshot:
    captured = captured_at or datetime.now(timezone.utc)
    entities: list[Entity] = []

    for subsystem in payload.get("health", []):
        name = subsystem.get("subsystem", "unknown")
        status = subsystem.get("status", "unknown")
        if status != "ok":
            entities.append(
                Entity(
                    id=f"health/{name}",
                    kind="subsystem_degraded",
                    title=f"{name} subsystem {status}",
                    attrs={"status": status},
                )
            )

    clients = payload.get("clients", [])
    now_ts = captured.timestamp()
    for client in clients:
        first_seen = client.get("first_seen", 0)
        if now_ts - first_seen <= NEW_CLIENT_WINDOW_S:
            mac = client.get("mac", "unknown")
            entities.append(
                Entity(
                    id=f"client/{mac}",
                    kind="new_client",
                    title=client.get("hostname") or client.get("name") or mac,
                    attrs={"network": client.get("network", "")},
                )
            )

    entities.append(
        Entity(
            id="clients/summary",
            kind="client_count",
            title=f"{len(clients)} clients online",
            attrs={"count": len(clients)},
        )
    )

    return SourceSnapshot(source="unifi", captured_at=captured, entities=entities)


def from_fixture(path: str | Path) -> SourceSnapshot:
    """Load a recorded payload; honors an optional top-level ``captured_at``
    so new-client detection is deterministic in tests and evals."""
    payload = json.loads(Path(path).read_text())
    captured_at = (
        datetime.fromisoformat(payload["captured_at"]) if "captured_at" in payload else None
    )
    return from_payload(payload, captured_at=captured_at)
