"""The demo API composes over fixtures only -- no network, no API key,
no path to a live source adapter."""

from fastapi.testclient import TestClient

from reveille.api import app
from reveille.schema import Briefing

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_briefing_generates_on_first_request():
    response = client.get("/api/briefing")
    assert response.status_code == 200
    briefing = Briefing.model_validate(response.json())
    assert briefing.executive_summary
    assert briefing.sections


def test_post_run_regenerates_with_a_fresh_timestamp():
    first = client.get("/api/briefing").json()
    second = client.post("/api/run").json()
    assert second["generated_at"] >= first["generated_at"]
    # same deterministic fixtures every time -- content is stable, only the
    # timestamp moves
    assert second["executive_summary"] == first["executive_summary"]


def test_cors_allows_the_public_site_origin():
    response = client.options(
        "/api/briefing",
        headers={
            "Origin": "https://bdavis.ai",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["access-control-allow-origin"] == "https://bdavis.ai"
