"""B285 — production auth hardening (SEC-1 … SEC-5).

Before this brief the API was fail-OPEN for unauthenticated traffic in a
production-like configuration:

- SEC-1: ``X-User-ID: <uuid>`` was accepted with no environment check → sending
  any user's UUID granted full read/write/delete on that account (IDOR), and
  unknown UUIDs bootstrapped fresh DB rows (unauthenticated DB fill).
- SEC-2: ``check_subscription(None)`` returned ALLOW_ALL, so anonymous requests
  sailed past ``require_active_subscription`` — including ``/api/coach/chat``,
  where the paid Anthropic call happens before any persistence.
- SEC-5: reads with ``user_id=None`` silently resolved to the shared
  ``__legacy__`` Supabase bucket.

Each test asserts BOTH directions: the attack is rejected in a prod-like
config, and the dev/test path is unchanged (the 12 existing test modules that
send ``X-User-ID`` must keep working).
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from backend.api import deps
from backend.engine import subscription_guard


# ---------------------------------------------------------------------------
# Harness: a tiny app exposing exactly the two dependencies under test.
# ---------------------------------------------------------------------------

def _make_client() -> TestClient:
    app = FastAPI()

    @app.get("/whoami")
    def whoami(user_id=Depends(deps.get_user_id)):
        return {"user_id": user_id}

    @app.get("/gated", dependencies=[Depends(deps.require_active_subscription)])
    def gated():
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


VICTIM_UUID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


@pytest.fixture
def prod_like(monkeypatch):
    """Production-like config: Supabase backend, no ALLOW_LEGACY_HEADER."""
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.delenv("ALLOW_LEGACY_HEADER", raising=False)
    return _make_client()


@pytest.fixture
def dev_like(monkeypatch):
    """Default dev/test config: file backend, Clerk unconfigured."""
    monkeypatch.setenv("STORAGE_BACKEND", "file")
    monkeypatch.delenv("ALLOW_LEGACY_HEADER", raising=False)
    return _make_client()


# ---------------------------------------------------------------------------
# SEC-1 — X-User-ID fallback
# ---------------------------------------------------------------------------

def test_sec1_x_user_id_rejected_in_production(prod_like):
    """Attack direction: impersonating a known UUID must 401, not authenticate."""
    res = prod_like.get("/whoami", headers={"X-User-ID": VICTIM_UUID})
    assert res.status_code == 401
    assert res.json()["detail"]["error"] == "authentication_required"


def test_sec1_no_credentials_rejected_in_production(prod_like):
    """No Authorization and no header → 401, never a None user on __legacy__."""
    res = prod_like.get("/whoami")
    assert res.status_code == 401


def test_sec1_x_user_id_still_works_in_dev(dev_like):
    """Legit direction: the local dev/pytest path is untouched."""
    res = dev_like.get("/whoami", headers={"X-User-ID": VICTIM_UUID})
    assert res.status_code == 200
    assert res.json()["user_id"] == VICTIM_UUID


def test_sec1_anonymous_still_allowed_in_dev(dev_like):
    res = dev_like.get("/whoami")
    assert res.status_code == 200
    assert res.json()["user_id"] is None


def test_sec1_escape_hatch_restores_legacy_behavior(monkeypatch):
    """ALLOW_LEGACY_HEADER=1 is the documented dev opt-in against a Supabase DB."""
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.setenv("ALLOW_LEGACY_HEADER", "1")
    client = _make_client()
    res = client.get("/whoami", headers={"X-User-ID": VICTIM_UUID})
    assert res.status_code == 200
    assert res.json()["user_id"] == VICTIM_UUID


def test_sec1_clerk_configured_alone_enforces_auth(monkeypatch):
    """Clerk configured is enough to enforce, independent of STORAGE_BACKEND."""
    monkeypatch.setenv("STORAGE_BACKEND", "file")
    monkeypatch.delenv("ALLOW_LEGACY_HEADER", raising=False)
    monkeypatch.setattr("backend.api.auth.is_clerk_configured", lambda: True)
    client = _make_client()
    assert client.get("/whoami", headers={"X-User-ID": VICTIM_UUID}).status_code == 401


def test_sec1_malformed_header_still_400_in_dev(dev_like):
    """Pre-existing UUID validation is preserved on the dev path."""
    assert dev_like.get("/whoami", headers={"X-User-ID": "not-a-uuid"}).status_code == 400


# ---------------------------------------------------------------------------
# SEC-2 — subscription guard fail-open for anonymous requests
# ---------------------------------------------------------------------------

def test_sec2_anonymous_denied_when_stripe_and_supabase_enabled(monkeypatch):
    monkeypatch.setattr(subscription_guard, "_stripe_enabled", lambda: True)
    monkeypatch.setattr(subscription_guard, "_supabase_enabled", lambda: True)
    result = subscription_guard.check_subscription(None)
    assert result["can_interact"] is False
    assert result["status"] == "none"


def test_sec2_anonymous_still_allowed_in_dev_config(monkeypatch):
    """Stripe not configured (pytest/dev) → unchanged permissive behavior."""
    monkeypatch.setattr(subscription_guard, "_stripe_enabled", lambda: False)
    assert subscription_guard.check_subscription(None)["can_interact"] is True


def test_sec2_bypass_user_ids_unaffected(monkeypatch):
    """Founder / beta bypass must keep working — it is checked after user_id."""
    monkeypatch.setattr(subscription_guard, "_stripe_enabled", lambda: True)
    monkeypatch.setattr(subscription_guard, "_supabase_enabled", lambda: True)
    monkeypatch.setattr(subscription_guard, "_BYPASS_USER_IDS", {VICTIM_UUID})
    assert subscription_guard.check_subscription(VICTIM_UUID)["can_interact"] is True


def test_sec2_active_subscriber_unaffected(monkeypatch):
    """Paying users (Christie, Cesar, Paolo, Agustin, Arnaud) are not locked out."""
    monkeypatch.setattr(subscription_guard, "_stripe_enabled", lambda: True)
    monkeypatch.setattr(subscription_guard, "_supabase_enabled", lambda: True)
    monkeypatch.setattr(subscription_guard, "_BYPASS_USER_IDS", set())
    monkeypatch.setattr(
        subscription_guard, "get_subscription_row",
        lambda uid: {"status": "active", "has_payment_method": True},
    )
    result = subscription_guard.check_subscription(VICTIM_UUID)
    assert result["can_interact"] is True
    assert result["status"] == "active"


def test_sec2_gated_endpoint_401s_for_anonymous_in_production(prod_like):
    """End-to-end: a gated route (coach/weather pattern) never reaches its body.

    The 401 comes from get_user_id, before require_active_subscription — so no
    paid LLM call can be triggered by anonymous traffic.
    """
    assert prod_like.get("/gated").status_code == 401


# ---------------------------------------------------------------------------
# SEC-5 — __legacy__ bucket
# ---------------------------------------------------------------------------

def test_sec5_supabase_reads_reject_anonymous_user():
    from backend.engine import storage_supabase

    for bad in (None, "", "__legacy__"):
        with pytest.raises(ValueError):
            storage_supabase._effective_uid(bad)


def test_sec5_supabase_reads_accept_real_user():
    from backend.engine import storage_supabase

    assert storage_supabase._effective_uid(VICTIM_UUID) == VICTIM_UUID


# ---------------------------------------------------------------------------
# SEC-3 — admin key comparison
# ---------------------------------------------------------------------------

def test_sec3_admin_key_uses_constant_time_compare(monkeypatch):
    from fastapi import HTTPException
    from starlette.requests import Request

    from backend.api.routers import admin

    monkeypatch.setattr(admin, "ADMIN_SECRET", "s3cret-value")

    def _req(headers):
        raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
        return Request({"type": "http", "headers": raw, "method": "GET", "path": "/"})

    # Correct key passes.
    admin._require_admin(_req({"X-Admin-Key": "s3cret-value"}))

    # Wrong key, missing key, and a correct prefix are all rejected.
    for bad in ({"X-Admin-Key": "wrong"}, {}, {"X-Admin-Key": "s3cret"}):
        with pytest.raises(HTTPException) as exc:
            admin._require_admin(_req(bad))
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# SEC-4 — identifier masking
# ---------------------------------------------------------------------------

def test_sec4_mask_uid_never_leaks_full_identifier():
    from backend.engine.log_utils import mask_uid

    assert VICTIM_UUID not in mask_uid(VICTIM_UUID)
    assert mask_uid(VICTIM_UUID).startswith("3f2504e0")
    assert mask_uid(None) == "-"
    assert mask_uid("short") == "***"
