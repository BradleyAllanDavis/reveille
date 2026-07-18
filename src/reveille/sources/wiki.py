"""Wiki adapter: a directory of markdown docs -> SourceSnapshot.

The "wiki" is any docs tree (in production: the private research wiki).
Recency by mtime is the signal — the morning briefing cares about what
changed, not the whole corpus.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from ..schema import Entity, SourceSnapshot

RECENT_WINDOW_S = 7 * 24 * 3600
MAX_DOCS = 10


def _title_of(path: Path) -> str:
    try:
        for line in path.read_text(errors="replace").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return path.stem


def from_directory(root: str | Path, now: float | None = None) -> SourceSnapshot:
    root = Path(root)
    now = now or time.time()
    recent: list[tuple[float, Path]] = []
    for path in root.rglob("*.md"):
        mtime = path.stat().st_mtime
        if now - mtime <= RECENT_WINDOW_S:
            recent.append((mtime, path))
    recent.sort(reverse=True)

    entities = [
        Entity(
            id=str(path.relative_to(root)),
            kind="recent_doc",
            title=_title_of(path),
            attrs={"age_days": round((now - mtime) / 86400, 1)},
        )
        for mtime, path in recent[:MAX_DOCS]
    ]
    return SourceSnapshot(
        source="wiki", captured_at=datetime.now(timezone.utc), entities=entities
    )
