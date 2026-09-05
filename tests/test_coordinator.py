"""Multi-agent path with a fake backend: fan-out/fan-in, JSON repair retry,
and the editor's copy-only contract feeding the schema."""

import asyncio
import json

import pytest

from reveille.demo import demo_snapshots
from reveille.coordinator import compose, compose_offline, run_analyst
from reveille.evals.checks import run_checks


class FakeBackend:
    """Replays canned replies; records every prompt for assertions."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def complete(self, *, model, system, prompt, max_tokens=1500):
        self.calls.append({"model": model, "system": system, "prompt": prompt})
        return self.replies.pop(0)


def analyst_reply(source, entity_id):
    return json.dumps(
        {
            "summary": f"one thing from {source}",
            "items": [
                {
                    "headline": f"{source} item",
                    "detail": "",
                    "priority": 1,
                    "refs": [{"source": source, "id": entity_id}],
                }
            ],
        }
    )


def test_compose_fans_out_and_merges():
    snapshots = demo_snapshots()
    first_ids = [snapshot.entities[0].id for snapshot in snapshots]
    replies = [analyst_reply(s.source, i) for s, i in zip(snapshots, first_ids)]
    editor_reply = json.dumps(
        {
            "executive_summary": "Quiet morning.",
            "top_priorities": json.loads(replies[0])["items"],
        }
    )
    backend = FakeBackend(replies + [editor_reply])

    briefing = asyncio.run(compose(snapshots, backend))

    assert len(briefing.sections) == len(snapshots)
    assert briefing.executive_summary == "Quiet morning."
    assert len(backend.calls) == len(snapshots) + 1  # N analysts + 1 editor


def test_json_repair_retry():
    snapshots = demo_snapshots()[:1]
    good = analyst_reply(snapshots[0].source, snapshots[0].entities[0].id)
    backend = FakeBackend(["sorry, here you go!", good])

    section = asyncio.run(run_analyst(backend, snapshots[0]))

    assert len(backend.calls) == 2
    assert "not parseable JSON" in backend.calls[1]["prompt"]
    assert section.items[0].refs[0].id == snapshots[0].entities[0].id


def test_repair_gives_up_after_one_retry():
    snapshots = demo_snapshots()[:1]
    backend = FakeBackend(["nope", "still nope"])
    with pytest.raises(ValueError):
        asyncio.run(run_analyst(backend, snapshots[0]))


def test_offline_composer_passes_its_own_evals():
    snapshots = demo_snapshots()
    briefing = compose_offline(snapshots)
    checks = run_checks(json.loads(briefing.model_dump_json()), snapshots)
    failed = [check.name for check in checks if not check.passed]
    assert not failed, failed
