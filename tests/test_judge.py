"""`reveille evals --judge` end to end over the committed fixtures, with a fake
backend standing in for the model: no API key, no network."""

import json

import pytest

from reveille import cli, llm

REPLY = json.dumps({"actionability": 4, "prioritization": 3, "concision": 5, "rationale": "ok."})


class FakeBackend:
    async def complete(self, *, model, system, prompt, max_tokens=1500):
        return REPLY


@pytest.fixture
def judge_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(llm, "AnthropicBackend", FakeBackend)
    monkeypatch.setattr(cli, "JUDGE_HISTORY_DB", tmp_path / "history.sqlite")
    monkeypatch.setenv("REVEILLE_CACHE_DIR", str(tmp_path / "cache"))

    def run():
        assert cli.main(["evals", "--judge"]) == 0
        return capsys.readouterr().out

    return run


def test_schema_invalid_fixture_is_skipped_not_a_crash(judge_run):
    """`malformed.json` fails the Briefing schema by design. The judge can't render
    it, so it must be skipped, and the fixtures sorted after it still judged."""
    out = judge_run()
    assert "judge[malformed] (skipped)" in out
    assert "judge[shallow]" in out
