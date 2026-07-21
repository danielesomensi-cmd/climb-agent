"""A250: free trial auto-start at onboarding completion.

- `start_trial_if_new` provisions a LOCAL trial row (no Stripe objects).
- `check_subscription` enforces trial_end lazily for local rows only.
- Checkout treats a local trial as convertible (no B212 short-circuit),
  carries over the remaining trial days, and never demotes the row to
  pending_checkout on abandon.
- /api/onboarding/complete calls the auto-start and survives its failure.
"""

from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.engine import subscription_guard as guard

client = TestClient(app)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _local_trial_row(days_left: float = 10.0) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "user_id": "u-1",
        "status": "trialing",
        "stripe_subscription_id": None,
        "stripe_customer_id": None,
        "trial_start": _iso(now - timedelta(days=guard.TRIAL_DAYS - days_left)),
        "trial_end": _iso(now + timedelta(days=days_left)),
        "has_payment_method": False,
    }


# ---------------------------------------------------------------------------
# is_local_trial
# ---------------------------------------------------------------------------

def test_is_local_trial_truth_table():
    assert guard.is_local_trial(_local_trial_row()) is True
    assert guard.is_local_trial(None) is False
    stripe_managed = {**_local_trial_row(), "stripe_subscription_id": "sub_123"}
    assert guard.is_local_trial(stripe_managed) is False
    assert guard.is_local_trial({"status": "active"}) is False


# ---------------------------------------------------------------------------
# check_subscription lazy expiry
# ---------------------------------------------------------------------------

@pytest.fixture
def _prod_guard(monkeypatch):
    monkeypatch.setattr(guard, "_stripe_enabled", lambda: True)
    monkeypatch.setattr(guard, "_supabase_enabled", lambda: True)


def test_local_trial_running_is_active(_prod_guard, monkeypatch):
    monkeypatch.setattr(guard, "get_subscription_row", lambda uid: _local_trial_row(10))
    res = guard.check_subscription("u-1")
    assert res["is_active"] is True
    assert res["can_interact"] is True
    assert res["status"] == "trialing"
    assert res["trial_days_remaining"] in (9, 10)


def test_local_trial_expired_is_denied(_prod_guard, monkeypatch):
    monkeypatch.setattr(guard, "get_subscription_row", lambda uid: _local_trial_row(-1))
    res = guard.check_subscription("u-1")
    assert res["status"] == "expired"
    assert res["can_interact"] is False
    assert res["trial_days_remaining"] == 0


def test_local_trial_unparseable_end_is_denied(_prod_guard, monkeypatch):
    row = {**_local_trial_row(), "trial_end": "not-a-date"}
    monkeypatch.setattr(guard, "get_subscription_row", lambda uid: row)
    assert guard.check_subscription("u-1")["can_interact"] is False


def test_stripe_managed_trial_past_end_stays_active(_prod_guard, monkeypatch):
    """Webhook-owned rows are exempt from lazy expiry: a lagging webhook on a
    trial→active conversion must not lock a paying user out."""
    row = {**_local_trial_row(-1), "stripe_subscription_id": "sub_123"}
    monkeypatch.setattr(guard, "get_subscription_row", lambda uid: row)
    assert guard.check_subscription("u-1")["is_active"] is True


# ---------------------------------------------------------------------------
# start_trial_if_new
# ---------------------------------------------------------------------------

def test_start_trial_noop_when_not_configured():
    """Default test env (file backend, no Stripe) → no-op."""
    assert guard.start_trial_if_new("u-1") is False


def test_start_trial_noop_when_row_exists(_prod_guard, monkeypatch):
    monkeypatch.setattr(guard, "get_subscription_row", lambda uid: {"status": "canceled"})
    called = []
    monkeypatch.setattr(guard, "upsert_subscription", lambda uid, f: called.append(f))
    assert guard.start_trial_if_new("u-1") is False
    assert called == []


def test_start_trial_creates_local_row(_prod_guard, monkeypatch):
    monkeypatch.setattr(guard, "get_subscription_row", lambda uid: None)
    captured = {}
    monkeypatch.setattr(guard, "upsert_subscription", lambda uid, f: captured.update({uid: f}))
    assert guard.start_trial_if_new("u-9") is True
    fields = captured["u-9"]
    assert fields["status"] == "trialing"
    assert fields["has_payment_method"] is False
    end = guard._parse_ts(fields["trial_end"])
    days = (end - datetime.now(timezone.utc)).days
    assert days in (guard.TRIAL_DAYS - 1, guard.TRIAL_DAYS)


# ---------------------------------------------------------------------------
# Checkout: local trial is convertible
# ---------------------------------------------------------------------------

class _FakeSessions:
    def __init__(self, store):
        self._store = store

    def create(self, params):
        self._store["params"] = params
        return mock.Mock(url="https://checkout.stripe.test/cs_fake")


class _FakeStripeClient:
    def __init__(self, store):
        self.checkout = mock.Mock(sessions=_FakeSessions(store))


@pytest.fixture
def _checkout_env(monkeypatch):
    from backend.api.routers import subscription as sub
    store: dict = {}
    monkeypatch.setattr(sub, "_STRIPE_PRICE_ID_STANDARD", "price_std")
    monkeypatch.setattr(sub, "_ALLOWED_PRICE_IDS", {"price_std"})
    monkeypatch.setattr(sub, "_stripe_client", lambda: _FakeStripeClient(store))
    store["upserts"] = []
    monkeypatch.setattr(sub, "upsert_subscription", lambda uid, f: store["upserts"].append(f))
    return store


_HDR = {"X-User-ID": "00000000-0000-4000-a000-0000000000aa"}


def test_checkout_local_trial_not_short_circuited(_checkout_env, monkeypatch):
    from backend.api.routers import subscription as sub
    row = _local_trial_row(10)
    monkeypatch.setattr(sub, "get_subscription_row", lambda uid: row)
    r = client.post("/api/subscription/checkout", json={}, headers=_HDR)
    assert r.status_code == 200
    assert "checkout_url" in r.json()
    # remaining days carried into the Stripe subscription, no double trial
    sd = _checkout_env["params"]["subscription_data"]
    assert "trial_period_days" not in sd
    carried = datetime.fromtimestamp(sd["trial_end"], tz=timezone.utc)
    assert abs((carried - guard._parse_ts(row["trial_end"])).total_seconds()) < 2
    # abandoning checkout must not demote the running trial
    assert _checkout_env["upserts"] == []


def test_checkout_local_trial_nearly_over_gets_no_trial(_checkout_env, monkeypatch):
    from backend.api.routers import subscription as sub
    monkeypatch.setattr(sub, "get_subscription_row", lambda uid: _local_trial_row(1))
    r = client.post("/api/subscription/checkout", json={}, headers=_HDR)
    assert r.status_code == 200
    sd = _checkout_env["params"]["subscription_data"]
    assert "trial_end" not in sd and "trial_period_days" not in sd


def test_checkout_stripe_trial_still_short_circuits(_checkout_env, monkeypatch):
    from backend.api.routers import subscription as sub
    row = {**_local_trial_row(10), "stripe_subscription_id": "sub_live"}
    monkeypatch.setattr(sub, "get_subscription_row", lambda uid: row)
    r = client.post("/api/subscription/checkout", json={}, headers=_HDR)
    assert r.status_code == 200
    assert r.json().get("already_active") is True


def test_checkout_fresh_user_keeps_full_trial(_checkout_env, monkeypatch):
    from backend.api.routers import subscription as sub
    monkeypatch.setattr(sub, "get_subscription_row", lambda uid: None)
    r = client.post("/api/subscription/checkout", json={}, headers=_HDR)
    assert r.status_code == 200
    sd = _checkout_env["params"]["subscription_data"]
    assert sd["trial_period_days"] == 15
    # non-trial users still get the pending_checkout marker
    assert _checkout_env["upserts"] == [{"status": "pending_checkout"}]


# ---------------------------------------------------------------------------
# Onboarding complete integration
# ---------------------------------------------------------------------------

def _complete_payload():
    return {
        "profile": {"name": "Test", "age": 28, "weight_kg": 70, "height_cm": 175},
        "experience": {"climbing_years": 4, "structured_training_years": 1},
        "grades": {"lead_max_rp": "7a", "lead_max_os": "6b+", "boulder_max_rp": "", "boulder_max_os": ""},
        "goal": {
            "goal_type": "lead_grade",
            "discipline": "lead",
            "target_grade": "7b",
            "target_style": "redpoint",
            "current_grade": "",
            "deadline": "2026-12-01",
        },
        "self_eval": {"primary_weakness": "fingers_give_out", "secondary_weakness": "pumped_fast"},
        "tests": {},
        "limitations": [],
        "equipment": {"home_enabled": True, "home": ["hangboard_20mm"], "gyms": []},
        "availability": {
            "mon": {"evening": {"available": True, "preferred_location": "home"}},
            "wed": {"evening": {"available": True, "preferred_location": "home"}},
            "fri": {"evening": {"available": True, "preferred_location": "home"}},
        },
        "planning_prefs": {"target_training_days_per_week": 3, "hard_day_cap_per_week": 2},
        "preferences": {"finger_training_device": "hangboard"},
        "trips": [],
        "outdoor_spots": [],
    }


def test_complete_calls_trial_autostart(monkeypatch):
    client.delete("/api/state")
    called = []
    monkeypatch.setattr(guard, "start_trial_if_new", lambda uid: called.append(uid) or True)
    r = client.post("/api/onboarding/complete", json=_complete_payload(), headers=_HDR)
    assert r.status_code == 200
    assert called == [_HDR["X-User-ID"]]


def test_complete_survives_trial_autostart_failure(monkeypatch):
    client.delete("/api/state")

    def _boom(uid):
        raise RuntimeError("supabase down")

    monkeypatch.setattr(guard, "start_trial_if_new", _boom)
    r = client.post("/api/onboarding/complete", json=_complete_payload(), headers=_HDR)
    assert r.status_code == 200
    assert r.json().get("macrocycle")


# ---------------------------------------------------------------------------
# Portal: local trial → checkout con carta obbligatoria
# ---------------------------------------------------------------------------

def test_portal_local_trial_serves_card_checkout(_checkout_env, monkeypatch):
    from backend.api.routers import subscription as sub
    row = _local_trial_row(10)
    monkeypatch.setattr(sub, "get_subscription_row", lambda uid: row)
    r = client.post("/api/subscription/portal", headers=_HDR)
    assert r.status_code == 200
    assert r.json()["portal_url"].startswith("https://checkout.stripe.test/")
    params = _checkout_env["params"]
    assert params["payment_method_collection"] == "always"
    sd = params["subscription_data"]
    carried = datetime.fromtimestamp(sd["trial_end"], tz=timezone.utc)
    assert abs((carried - guard._parse_ts(row["trial_end"])).total_seconds()) < 2


def test_portal_no_row_still_404(_checkout_env, monkeypatch):
    from backend.api.routers import subscription as sub
    monkeypatch.setattr(sub, "get_subscription_row", lambda uid: None)
    r = client.post("/api/subscription/portal", headers=_HDR)
    assert r.status_code == 404
