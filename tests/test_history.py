"""Judge-score history side-store: records append, trend queries return them
newest-first, scoped to their own case."""

from reveille.evals import history


def test_record_and_trend(tmp_path):
    db = tmp_path / "judge_history.sqlite"
    history.record(db, "golden", {"actionability": 4, "prioritization": 3, "concision": 5}, "t1")
    history.record(db, "golden", {"actionability": 5, "prioritization": 5, "concision": 5}, "t2")
    history.record(db, "shallow", {"actionability": 1, "prioritization": 1, "concision": 1}, "t1")

    rows = history.trend(db, "golden")
    assert rows == [("t2", 5, 5, 5), ("t1", 4, 3, 5)]
    assert history.trend(db, "shallow") == [("t1", 1, 1, 1)]


def test_trend_respects_limit(tmp_path):
    db = tmp_path / "judge_history.sqlite"
    for i in range(5):
        history.record(db, "golden", {"actionability": i, "prioritization": i, "concision": i}, f"t{i}")
    assert len(history.trend(db, "golden", limit=2)) == 2
