"""Things 3 adapter: the local SQLite database -> SourceSnapshot.

Read-only by construction (SQLite URI ``mode=ro``) — the briefing pipeline
never writes to the task database. Schema facts (tables, status/start enums,
the packed binary date format) follow the Things 3 database as of v3.15+.

DB resolution order: explicit path arg -> $THINGSDB -> the agent-readable
mirror (macOS TCC blocks headless agents from the live DB; the control plane
maintains a mirror copy) -> the live database.

"Today" in Things is derived, not a stored flag: an incomplete task whose
start date is set and not in the future (whether filed Anytime or Someday).
Overdue is a deadline before today. Both decode the packed date column:
bits [16..27] year, [12..15] month, [7..11] day.
"""

from __future__ import annotations

import glob
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ..schema import Entity, SourceSnapshot

MIRROR_PATH = "~/.cache/things-mirror/main.sqlite"
LIVE_GLOB = (
    "~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac"
    "/ThingsData-*/Things Database.thingsdatabase/main.sqlite"
)

# Packed-date decode: printf-style ISO date from the binary column.
_ISO = "printf('%d-%02d-%02d', ({col} & 134152192) >> 16, ({col} & 61440) >> 12, ({col} & 3968) >> 7)"

DEADLINE_WINDOW_DAYS = 7

_QUERY = f"""
SELECT
    task.uuid,
    task.title,
    {_ISO.format(col='task.startDate')} AS start_date,
    {_ISO.format(col='task.deadline')}  AS deadline,
    COALESCE(task.startDate, 0) != 0 AS has_start,
    COALESCE(task.deadline, 0)  != 0 AS has_deadline,
    task.todayIndex,
    project.title AS project_title
FROM TMTask AS task
LEFT OUTER JOIN TMTask AS project ON task.project = project.uuid
WHERE task.status = 0        -- incomplete
  AND task.trashed = 0
  AND task.type = 0          -- to-do (not project/heading)
  AND task.rt1_recurrenceRule IS NULL
  AND (COALESCE(task.startDate, 0) != 0 OR COALESCE(task.deadline, 0) != 0)
ORDER BY task.todayIndex
"""


def resolve_db_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    if env := os.environ.get("THINGSDB"):
        return Path(env).expanduser()
    mirror = Path(MIRROR_PATH).expanduser()
    if mirror.exists():
        return mirror
    matches = glob.glob(os.path.expanduser(LIVE_GLOB))
    if matches:
        return Path(matches[0])
    raise FileNotFoundError("no Things database found (set $THINGSDB or pass a path)")


def from_database(db_path: str | None = None, today: date | None = None) -> SourceSnapshot:
    path = resolve_db_path(db_path)
    today = today or date.today()
    horizon = today + timedelta(days=DEADLINE_WINDOW_DAYS)

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(_QUERY).fetchall()
    finally:
        conn.close()

    entities: list[Entity] = []
    for row in rows:
        start = date.fromisoformat(row["start_date"]) if row["has_start"] else None
        deadline = date.fromisoformat(row["deadline"]) if row["has_deadline"] else None

        if deadline and deadline < today:
            kind = "overdue_task"
        elif start and start <= today:
            kind = "today_task"
        elif deadline and deadline <= horizon:
            kind = "deadline_task"
        else:
            continue  # scheduled for the future: not this morning's problem

        entities.append(
            Entity(
                id=row["uuid"],
                kind=kind,
                title=row["title"],
                attrs={
                    "project": row["project_title"] or "",
                    "deadline": deadline.isoformat() if deadline else None,
                },
            )
        )

    return SourceSnapshot(
        source="things", captured_at=datetime.now(timezone.utc), entities=entities
    )
