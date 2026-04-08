"""B196-CORS: verify CORS allows production, localhost dev, and Vercel preview
branches via the allow_origin_regex pattern, while rejecting unrelated origins.

The OPTIONS preflight is what fails in the browser when CORS is misconfigured,
so each test sends OPTIONS with `Origin` + `Access-Control-Request-Method`
headers and asserts the echoed `Access-Control-Allow-Origin` header.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def _preflight(origin: str):
    return client.options(
        "/api/onboarding/defaults",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_cors_allows_production_origin():
    res = _preflight("https://climb-agent.vercel.app")
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "https://climb-agent.vercel.app"


def test_cors_allows_localhost_dev():
    res = _preflight("http://localhost:3000")
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_allows_vercel_preview_branch():
    """Preview deployment URL for a brief/B196-* branch."""
    origin = "https://climb-agent-git-brief-b196-sw-versioning-danieles-projects.vercel.app"
    res = _preflight(origin)
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == origin


def test_cors_allows_vercel_preview_hash():
    """Per-deployment hash URL (no branch, just commit hash)."""
    origin = "https://climb-agent-abc123def456-danieles-projects.vercel.app"
    res = _preflight(origin)
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == origin


def test_cors_rejects_unrelated_vercel_site():
    """Other Vercel apps must NOT get CORS access — regex requires
    `climb-agent` prefix to prevent allow_origin_regex from being a
    blanket *.vercel.app permit."""
    res = _preflight("https://malicious-app.vercel.app")
    # Starlette returns 400 (or omits Allow-Origin header) for non-matching origins
    assert res.headers.get("access-control-allow-origin") != "https://malicious-app.vercel.app"


def test_cors_rejects_origin_with_climb_agent_as_subdomain_suffix():
    """Defense against `climb-agent.vercel.app.evil.com`-style escapes:
    the regex anchors `.vercel.app` literally, so trailing TLDs cannot match."""
    res = _preflight("https://climb-agent.vercel.app.evil.com")
    assert res.headers.get("access-control-allow-origin") != "https://climb-agent.vercel.app.evil.com"
