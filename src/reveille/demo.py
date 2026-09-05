"""The fixture-backed snapshot set used for demos, tests, and evals.

Deliberately synthetic and secret-free: this is exactly what `reveille brief
--offline` composes over with no `--live-*` flags, and what the public API
(``reveille serve``) always uses. Nothing real -- personal tasks, home
state, network data -- is ever reachable from the deployed demo.
"""

from __future__ import annotations

from pathlib import Path

from .schema import SourceSnapshot
from .sources import home_assistant, unifi

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures"


def demo_snapshots() -> list[SourceSnapshot]:
    return [
        SourceSnapshot.model_validate_json((FIXTURES / "things_snapshot.json").read_text()),
        home_assistant.from_fixture(FIXTURES / "ha_states.json"),
        unifi.from_fixture(FIXTURES / "unifi_payload.json"),
    ]
