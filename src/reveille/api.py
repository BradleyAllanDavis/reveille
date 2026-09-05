"""The public demo API: GET the last briefing, POST to regenerate it.

Deliberately narrow -- two endpoints, no auth, no persistence beyond a single
in-process value. It only ever composes over ``demo.demo_snapshots()`` (the
same synthetic fixtures ``reveille brief --offline`` uses), so there is no
path from this process to real personal data: no live Things/HA/UniFi
credentials are read, and nothing here accepts input that reaches a source
adapter. Safe to expose publicly.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .coordinator import compose_offline
from .demo import demo_snapshots
from .schema import Briefing

app = FastAPI(title="reveille demo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bdavis.ai", "http://localhost:4321"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_last_briefing: Briefing | None = None


def _run() -> Briefing:
    global _last_briefing
    _last_briefing = compose_offline(demo_snapshots())
    return _last_briefing


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/briefing")
def get_briefing() -> Briefing:
    """The most recent briefing, generating one on first request."""
    return _last_briefing or _run()


@app.post("/api/run")
def run_briefing() -> Briefing:
    """Regenerate the briefing now (deterministic composer, no API key)."""
    return _run()
