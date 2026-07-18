"""Raw source payloads map to the normalized snapshot correctly."""

import io
import json
from pathlib import Path

from reveille.sources import home_assistant, unifi, wiki

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _fake_urlopen(responses):
    """A urllib.request.urlopen replacement serving canned JSON bodies in
    call order; records every request made for header/URL assertions."""
    calls = []

    def fake(req, context=None, timeout=None):
        calls.append(req)
        return io.BytesIO(json.dumps(responses[len(calls) - 1]).encode())

    return fake, calls


def kinds(snapshot):
    return {entity.kind for entity in snapshot.entities}


def test_ha_extracts_actionable_states():
    snapshot = home_assistant.from_fixture(FIXTURES / "ha_states.json")
    assert snapshot.source == "home_assistant"
    ids = snapshot.ids()
    assert "binary_sensor.garage_side_door" in ids       # open door
    assert "binary_sensor.kitchen_window" not in ids     # closed: noise
    assert "sensor.back_door_lock_battery" in ids        # 12% battery
    assert "sensor.thermostat_battery" not in ids        # 88%: fine
    assert "light.basement_workbench" in ids
    assert "sensor.upstairs_motion" in ids               # unavailable
    assert "climate.main_floor" not in ids               # normal state: noise
    assert kinds(snapshot) == {"open_contact", "low_battery", "light_on", "unavailable"}


def test_unifi_flags_degraded_subsystem_and_new_client():
    snapshot = unifi.from_fixture(FIXTURES / "unifi_payload.json")
    ids = snapshot.ids()
    assert "health/wlan" in ids                          # warning -> degraded
    assert "health/wan" not in ids                       # ok: noise
    assert "client/aa:bb:cc:00:00:03" in ids             # first_seen 1h before capture
    assert "client/aa:bb:cc:00:00:01" not in ids         # long-known client
    assert "clients/summary" in ids


def test_wiki_picks_recent_docs_only(tmp_path):
    recent = tmp_path / "fresh.md"
    recent.write_text("# Fresh doc\nbody\n")
    stale = tmp_path / "old.md"
    stale.write_text("# Old doc\nbody\n")
    import os
    week_and_change = 8 * 24 * 3600
    old_time = recent.stat().st_mtime - week_and_change
    os.utime(stale, (old_time, old_time))

    snapshot = wiki.from_directory(tmp_path)
    assert [entity.title for entity in snapshot.entities] == ["Fresh doc"]


def test_ha_fetch_sends_bearer_token_and_feeds_from_states(monkeypatch):
    states = json.loads((FIXTURES / "ha_states.json").read_text())
    fake, calls = _fake_urlopen([states])
    monkeypatch.setattr("urllib.request.urlopen", fake)

    result = home_assistant.fetch("https://homeassistant", "secret-token")

    assert result == states
    assert calls[0].full_url == "https://homeassistant/api/states"
    assert calls[0].get_header("Authorization") == "Bearer secret-token"


def test_unifi_fetch_hits_health_and_sta_and_unwraps_data(monkeypatch):
    fake, calls = _fake_urlopen(
        [
            {"meta": {"rc": "ok"}, "data": [{"subsystem": "wan", "status": "ok"}]},
            {"meta": {"rc": "ok"}, "data": [{"mac": "aa:bb", "hostname": "phone"}]},
        ]
    )
    monkeypatch.setattr("urllib.request.urlopen", fake)

    payload = unifi.fetch("https://192.168.0.1", "api-key", site="default")

    assert payload == {
        "health": [{"subsystem": "wan", "status": "ok"}],
        "clients": [{"mac": "aa:bb", "hostname": "phone"}],
    }
    assert calls[0].full_url == "https://192.168.0.1/proxy/network/api/s/default/stat/health"
    assert calls[1].full_url == "https://192.168.0.1/proxy/network/api/s/default/stat/sta"
    assert calls[0].get_header("X-api-key") == "api-key"
