"""A234 (A-DAILYTIP) — daily feature-discovery tips.

Covers: catalog integrity (unique ids, required fields, CTA routes exist),
deterministic per-user rotation (no repeat within pool-size days, full pool
coverage), dismissal bookkeeping (idempotent, per-day, trimmed), and the two
API endpoints.
"""

from __future__ import annotations

import shutil
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.engine.tips_engine import (
    _MAX_SEEN_HISTORY,
    _load_tips,
    get_daily_tip,
    is_dismissed,
    record_dismissal,
    tip_exists,
)

client = TestClient(app)

_TEST_USER_IDS = (
    "00000000-0000-4000-a000-000000000340",
    "00000000-0000-4000-a000-000000000341",
)


@pytest.fixture(autouse=True)
def _cleanup_test_users():
    yield
    from backend.api.deps import USERS_DIR

    for uid in _TEST_USER_IDS:
        shutil.rmtree(USERS_DIR / uid, ignore_errors=True)


# Frontend routes that exist as pages — cta_url must point to one of these.
_VALID_CTA_ROUTES = {
    "/today", "/week", "/plan", "/settings", "/coach", "/mobility",
    "/free-session", "/session-builder", "/body-part-picker", "/outdoor",
    "/reports/weekly", "/tabata", "/whats-next", "/guide",
}


class TestCatalog:
    def test_pool_non_empty_and_ids_unique(self):
        tips = _load_tips()
        assert len(tips) >= 20
        ids = [t["id"] for t in tips]
        assert len(ids) == len(set(ids))

    def test_required_fields(self):
        for tip in _load_tips():
            assert tip["id"].startswith("tip_")
            assert tip["category"] == "feature_discovery"
            assert isinstance(tip["text"], str) and 20 <= len(tip["text"]) <= 300
            assert isinstance(tip.get("tags"), list)

    def test_cta_consistency_and_valid_routes(self):
        for tip in _load_tips():
            label, url = tip.get("cta_label"), tip.get("cta_url")
            # label and url are either both set or both null
            assert (label is None) == (url is None), tip["id"]
            if url is not None:
                assert url in _VALID_CTA_ROUTES, f"{tip['id']} → unknown route {url}"


class TestSelection:
    def test_deterministic_same_user_same_date(self):
        d = date(2026, 7, 19)
        assert get_daily_tip("user-a", d) == get_daily_tip("user-a", d)

    def test_full_pool_coverage_no_repeat_within_cycle(self):
        """Over pool-size consecutive days each tip appears exactly once."""
        pool = _load_tips()
        start = date(2026, 7, 1)
        served = [
            get_daily_tip("user-a", start + timedelta(days=i))["id"]
            for i in range(len(pool))
        ]
        assert sorted(served) == sorted(t["id"] for t in pool)

    def test_users_get_different_permutations(self):
        """At least one of a handful of users differs from user-a on day 0
        (deterministic — md5 permutations diverge)."""
        d = date(2026, 7, 19)
        base = get_daily_tip("user-a", d)["id"]
        others = [get_daily_tip(f"user-{i}", d)["id"] for i in range(2, 10)]
        assert any(o != base for o in others)

    def test_tip_exists(self):
        assert tip_exists(_load_tips()[0]["id"])
        assert not tip_exists("tip_nonexistent")


class TestDismissal:
    def test_record_and_check_same_day(self):
        state: dict = {}
        d = date(2026, 7, 19)
        assert not is_dismissed(state, "tip_coach", d)
        record_dismissal(state, "tip_coach", d)
        assert is_dismissed(state, "tip_coach", d)
        # Different day → not dismissed
        assert not is_dismissed(state, "tip_coach", d + timedelta(days=1))

    def test_idempotent(self):
        state: dict = {}
        d = date(2026, 7, 19)
        record_dismissal(state, "tip_coach", d)
        record_dismissal(state, "tip_coach", d)
        assert len(state["tips_seen"]) == 1

    def test_history_trimmed(self):
        state: dict = {}
        d = date(2026, 1, 1)
        for i in range(_MAX_SEEN_HISTORY + 30):
            record_dismissal(state, f"tip_{i}", d)
        assert len(state["tips_seen"]) == _MAX_SEEN_HISTORY
        # Most recent entries survive
        assert state["tips_seen"][-1]["id"] == f"tip_{_MAX_SEEN_HISTORY + 29}"


class TestApi:
    def test_get_daily_tip(self):
        r = client.get(
            "/api/tips/daily?date=2026-07-19",
            headers={"X-User-ID": _TEST_USER_IDS[0]},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["tip"]["id"].startswith("tip_")
        assert body["dismissed_today"] is False

    def test_dismiss_flow(self):
        uid = _TEST_USER_IDS[1]
        headers = {"X-User-ID": uid}
        tip = client.get("/api/tips/daily?date=2026-07-19", headers=headers).json()["tip"]

        r = client.post(f"/api/tips/{tip['id']}/dismiss?date=2026-07-19", headers=headers)
        assert r.status_code == 200
        assert r.json()["ok"] is True

        again = client.get("/api/tips/daily?date=2026-07-19", headers=headers).json()
        assert again["dismissed_today"] is True
        # Next day → same rotation logic, fresh dismissal state
        tomorrow = client.get("/api/tips/daily?date=2026-07-20", headers=headers).json()
        assert tomorrow["dismissed_today"] is False

    def test_dismiss_unknown_tip_404(self):
        r = client.post(
            "/api/tips/tip_nonexistent/dismiss",
            headers={"X-User-ID": _TEST_USER_IDS[0]},
        )
        assert r.status_code == 404

    def test_invalid_date_422(self):
        r = client.get(
            "/api/tips/daily?date=not-a-date",
            headers={"X-User-ID": _TEST_USER_IDS[0]},
        )
        assert r.status_code == 422
