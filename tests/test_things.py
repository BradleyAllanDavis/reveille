"""Things adapter against a synthetic database with the real schema shape.

Builds a minimal TMTask table (same columns/enums as Things 3.15+, including
the packed binary date format) so the SQL is exercised for real without
touching a live task database.
"""

import sqlite3
from datetime import date

import pytest

from reveille.sources.things import from_database

TODAY = date(2026, 7, 18)


def packed(d: date) -> int:
    """Things binary date: bits [16..26] year, [12..15] month, [7..11] day."""
    return (d.year << 16) | (d.month << 12) | (d.day << 7)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "main.sqlite"
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE TMTask (
            uuid TEXT PRIMARY KEY, title TEXT, status INTEGER, trashed INTEGER,
            type INTEGER, rt1_recurrenceRule BLOB, startDate INTEGER,
            deadline INTEGER, todayIndex INTEGER, project TEXT
        )"""
    )
    rows = [
        # (uuid, title, status, trashed, type, recur, startDate, deadline, todayIndex, project)
        ("t1", "due today", 0, 0, 0, None, packed(TODAY), None, 1, None),
        ("t2", "started last week", 0, 0, 0, None, packed(date(2026, 7, 11)), None, 2, None),
        ("t3", "overdue deadline", 0, 0, 0, None, None, packed(date(2026, 7, 10)), 3, None),
        ("t4", "deadline in window", 0, 0, 0, None, None, packed(date(2026, 7, 23)), 4, None),
        ("t5", "deadline far out", 0, 0, 0, None, None, packed(date(2026, 9, 1)), 5, None),
        ("t6", "future start", 0, 0, 0, None, packed(date(2026, 8, 1)), None, 6, None),
        ("t7", "completed", 3, 0, 0, None, packed(TODAY), None, 7, None),
        ("t8", "trashed", 0, 1, 0, None, packed(TODAY), None, 8, None),
        ("t9", "a project", 0, 0, 1, None, packed(TODAY), None, 9, None),
        ("t10", "recurring template", 0, 0, 0, b"rrule", packed(TODAY), None, 10, None),
        ("t11", "unscheduled", 0, 0, 0, None, None, None, 11, None),
        ("t12", "unset dates stored as zero", 0, 0, 0, None, 0, 0, 12, None),
    ]
    conn.executemany("INSERT INTO TMTask VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return path


def test_classification(db):
    snapshot = from_database(str(db), today=TODAY)
    by_id = {entity.id: entity.kind for entity in snapshot.entities}
    assert by_id == {
        "t1": "today_task",
        "t2": "today_task",      # past start date still surfaces today
        "t3": "overdue_task",
        "t4": "deadline_task",   # within the 7-day window
    }


def test_opens_read_only(db):
    snapshot = from_database(str(db), today=TODAY)
    assert snapshot.source == "things"
    # the adapter must not have written anything
    conn = sqlite3.connect(db)
    count = conn.execute("SELECT COUNT(*) FROM TMTask").fetchone()[0]
    conn.close()
    assert count == 12
