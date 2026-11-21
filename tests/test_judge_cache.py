"""The judge cache must save every repeat model call and never serve a stale or
corrupt verdict. A counting fake backend makes "0 additional calls" an assertion,
not a claim; no test here touches a real API."""

import json
import sqlite3

import pytest
from pydantic import ValidationError

from reveille import cli, llm
from reveille.evals import history
from reveille.evals import judge as judge_mod
from reveille.evals.cache import ResultCache
from reveille.evals.judge import cached_judge, judge_key
from reveille.schema import Briefing

REPLY = json.dumps({"actionability": 4, "prioritization": 3, "concision": 5, "rationale": "ok."})


def _judge_inputs() -> list[str]:
    inputs = []
    for path in sorted((cli.FIXTURES / "briefings").glob("*.json")):
        try:
            inputs.append(Briefing.model_validate_json(path.read_text()).to_markdown())
        except ValidationError:
            pass  # schema-invalid fixtures are skipped by the judge
    return inputs


# The fixture set today: 6 briefings, 5 that parse, 4 distinct rendered inputs
# (golden and hallucinated differ only in source refs, which markdown omits).
N_FIXTURES = len(list((cli.FIXTURES / "briefings").glob("*.json")))
JUDGEABLE = len(_judge_inputs())
DISTINCT = len(set(_judge_inputs()))
SKIPPED = N_FIXTURES - JUDGEABLE


class CountingBackend:
    def __init__(self, reply: str = REPLY) -> None:
        self.calls = 0
        self.reply = reply

    async def complete(self, *, model, system, prompt, max_tokens=1500):
        self.calls += 1
        return self.reply


@pytest.fixture
def cache(tmp_path):
    return ResultCache(tmp_path / "cache")


def test_second_call_is_a_hit_with_zero_model_calls(cache):
    backend = CountingBackend()
    first, status1 = cached_judge(backend, "briefing", cache)
    second, status2 = cached_judge(backend, "briefing", cache)
    assert (status1, status2) == ("miss", "hit")
    assert first == second
    assert backend.calls == 1


@pytest.mark.parametrize(
    "change",
    [
        {"briefing": "different briefing"},
        {"model": "claude-haiku-4-5"},
        {"max_tokens": 400},
    ],
)
def test_changed_input_model_or_params_miss(cache, change):
    backend = CountingBackend()
    cached_judge(backend, "briefing", cache)
    briefing = change.pop("briefing", "briefing")
    _, status = cached_judge(backend, briefing, cache, **change)
    assert status == "miss"
    assert backend.calls == 2


@pytest.mark.parametrize(("attr", "value"), [("RUBRIC", "a new rubric"), ("JUDGE_VERSION", "2")])
def test_changed_rubric_or_version_miss(cache, monkeypatch, attr, value):
    backend = CountingBackend()
    cached_judge(backend, "briefing", cache)
    before = judge_key("briefing")
    monkeypatch.setattr(judge_mod, attr, value)
    assert judge_key("briefing") != before
    cached_judge(backend, "briefing", cache)
    assert backend.calls == 2


def test_bypass_calls_the_model_every_time():
    backend = CountingBackend()
    for _ in range(2):
        _, status = cached_judge(backend, "briefing", None)
        assert status == "bypassed"
    assert backend.calls == 2


@pytest.mark.parametrize(
    "junk",
    [
        "{not json",
        "",
        "[]",
        "null",
        '{"actionability": 4}',
        '{"actionability": 9, "prioritization": 1, "concision": 1}',
        '{"actionability": Infinity, "prioritization": 1, "concision": 1}',
        '{"actionability": "high", "prioritization": 1, "concision": 1}',
    ],
)
def test_corrupt_or_invalid_entry_degrades_to_miss_and_heals(cache, junk):
    backend = CountingBackend()
    cached_judge(backend, "briefing", cache)
    (entry,) = cache.dir.glob("*.json")
    entry.write_text(junk)
    assert cached_judge(backend, "briefing", cache)[1] == "miss"
    assert backend.calls == 2
    assert cached_judge(backend, "briefing", cache)[1] == "hit"  # the miss rewrote the entry


def test_malformed_reply_is_not_cached(cache):
    backend = CountingBackend(reply="no json here")
    with pytest.raises(ValueError):
        cached_judge(backend, "briefing", cache)
    assert list(cache.dir.glob("*.json")) == []


def test_clear_only_removes_cache_entries(cache):
    assert cache.clear() == 0  # a cache dir that doesn't exist yet is not an error
    cached_judge(CountingBackend(), "briefing", cache)
    (cache.dir / f"{'a' * 64}.json.123.tmp").write_text("{")  # a stale temp file
    (cache.dir / "notes.json").write_text("{}")  # someone else's file
    assert cache.clear() == 2
    assert [p.name for p in cache.dir.iterdir()] == ["notes.json"]


# --- end to end through `reveille evals --judge` ---------------------------------------


@pytest.fixture
def run_evals(tmp_path, monkeypatch, capsys):
    backend = CountingBackend()
    monkeypatch.setenv("REVEILLE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(cli, "JUDGE_HISTORY_DB", tmp_path / "history.sqlite")
    monkeypatch.setattr(llm, "AnthropicBackend", lambda: backend)

    def run(*flags):
        assert cli.main(["evals", "--judge", *flags]) == 0
        return capsys.readouterr().out

    run.backend = backend
    run.cache_dir = tmp_path / "cache"
    run.history_rows = lambda: sqlite3.connect(tmp_path / "history.sqlite").execute(
        "SELECT count(*) FROM judge_runs"
    ).fetchone()[0]
    return run


def test_warm_rerun_makes_zero_model_calls(run_evals):
    cold = run_evals()
    # Identical inputs dedupe even on a cold run: one call per distinct briefing.
    assert f"judge: {JUDGEABLE - DISTINCT} hits, {DISTINCT} misses, {SKIPPED} skipped ({DISTINCT} model calls)" in cold
    assert run_evals.backend.calls == DISTINCT

    warm = run_evals()
    assert f"judge: {JUDGEABLE} hits, 0 misses, {SKIPPED} skipped (0 model calls)" in warm
    assert run_evals.backend.calls == DISTINCT  # zero additional calls
    assert "skipped-deterministic" in warm


def test_history_gets_one_row_per_case_and_no_duplicates_on_rerun(run_evals):
    run_evals()
    assert run_evals.history_rows() == JUDGEABLE  # a cold-run dedupe hit still records its case
    run_evals()
    assert run_evals.history_rows() == JUDGEABLE  # warm hits add nothing


def test_a_cached_verdict_that_differs_from_the_latest_row_is_recorded(run_evals):
    run_evals()
    # As if the fixture had been edited (new verdict recorded) and then reverted.
    history.record(cli.JUDGE_HISTORY_DB, "golden", {"actionability": 1, "prioritization": 1, "concision": 1})
    out = run_evals()
    assert run_evals.backend.calls == DISTINCT  # still served from cache
    assert "vs previous run: actionability 1->4" in out
    assert run_evals.history_rows() == JUDGEABLE + 2


def test_cli_no_cache_writes_nothing(run_evals):
    out = run_evals("--no-cache")
    assert f"judge: 0 hits, 0 misses, {JUDGEABLE} bypassed, {SKIPPED} skipped ({JUDGEABLE} model calls)" in out
    assert not run_evals.cache_dir.exists()


def test_cli_no_cache_ignores_a_warm_cache(run_evals):
    run_evals()  # populate: a --no-cache that still read would now report hits
    out = run_evals("--no-cache")
    assert f"judge: 0 hits, 0 misses, {JUDGEABLE} bypassed" in out
    assert run_evals.backend.calls == DISTINCT + JUDGEABLE


def test_cli_clear_cache_empties_dir_then_runs(run_evals):
    run_evals()
    assert len(list(run_evals.cache_dir.glob("*.json"))) == DISTINCT
    out = run_evals("--clear-cache")
    assert f"cleared {DISTINCT} cache entries" in out
    assert f"{DISTINCT} misses" in out
    assert run_evals.backend.calls == 2 * DISTINCT
