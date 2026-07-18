"""Judge-score history: a local sqlite side-store so editorial-quality trend
is visible across runs, not just the latest ``--judge`` invocation.

Same shape as the control plane's own score side-stores (docs/DECISIONS.md
lineage table): an append-only log, queried for trend, never a pass/fail gate
itself -- that job belongs to the deterministic checks and evals/baseline.json.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DDL = """
CREATE TABLE IF NOT EXISTS judge_runs (
    recorded_at    TEXT NOT NULL,
    case_name      TEXT NOT NULL,
    actionability  INTEGER NOT NULL,
    prioritization INTEGER NOT NULL,
    concision      INTEGER NOT NULL,
    rationale      TEXT NOT NULL
)
"""


def record(db_path: str | Path, case_name: str, verdict: dict, recorded_at: str | None = None) -> None:
    recorded_at = recorded_at or datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_DDL)
        conn.execute(
            "INSERT INTO judge_runs VALUES (?, ?, ?, ?, ?, ?)",
            (
                recorded_at,
                case_name,
                verdict["actionability"],
                verdict["prioritization"],
                verdict["concision"],
                verdict.get("rationale", ""),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def trend(db_path: str | Path, case_name: str, limit: int = 10) -> list[tuple[str, int, int, int]]:
    """Most recent rows for one case, newest first."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_DDL)
        return conn.execute(
            "SELECT recorded_at, actionability, prioritization, concision FROM judge_runs "
            "WHERE case_name = ? ORDER BY recorded_at DESC LIMIT ?",
            (case_name, limit),
        ).fetchall()
    finally:
        conn.close()
