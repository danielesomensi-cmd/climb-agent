"""A233 — First-touch attribution persisted at onboarding.

Covers the server-side sanitizer and the persistence path in
POST /api/onboarding/complete: whitelist keys, length cap, absent-when-empty,
and the server-stamped onboarded_at.
"""

from __future__ import annotations

import shutil

import pytest

from backend.api.routers.onboarding import (
    _ATTRIBUTION_MAX_LEN,
    _sanitize_attribution,
)

_TEST_USER_IDS = (
    "00000000-0000-4000-a000-000000000233",
    "00000000-0000-4000-a000-000000000234",
    "00000000-0000-4000-a000-000000000235",
)


@pytest.fixture(autouse=True)
def _cleanup_test_users():
    yield
    from backend.api.deps import USERS_DIR
    for uid in _TEST_USER_IDS:
        shutil.rmtree(USERS_DIR / uid, ignore_errors=True)


class TestSanitizer:
    def test_whitelisted_keys_kept(self):
        raw = {
            "utm_source": "reddit",
            "utm_campaign": "sideproject",
            "referrer": "https://www.reddit.com/r/SideProject/",
            "landing_page": "/demo",
            "first_touch_at": "2026-07-13T10:00:00Z",
        }
        out = _sanitize_attribution(raw)
        assert out == raw

    def test_unknown_keys_dropped(self):
        out = _sanitize_attribution({
            "utm_source": "flyer",
            "evil": "<script>",
            "user_id": "spoofed",
            "onboarded_at": "client-supplied",  # server-stamped, never client
        })
        assert out == {"utm_source": "flyer"}

    def test_values_truncated_to_cap(self):
        out = _sanitize_attribution({"referrer": "x" * 500})
        assert len(out["referrer"]) == _ATTRIBUTION_MAX_LEN

    def test_non_string_values_dropped(self):
        out = _sanitize_attribution({
            "utm_source": 123,
            "utm_medium": None,
            "utm_campaign": ["a"],
            "landing_page": "/",
        })
        assert out == {"landing_page": "/"}

    def test_empty_and_none_input(self):
        assert _sanitize_attribution(None) == {}
        assert _sanitize_attribution({}) == {}
        assert _sanitize_attribution({"utm_source": "   "}) == {}


class TestOnboardingPersistence:
    """End-to-end through POST /api/onboarding/complete (file backend)."""

    def _minimal_payload(self) -> dict:
        return {
            "profile": {"name": "attr-test", "age": 30, "weight_kg": 70, "height_cm": 175},
            "experience": {"climbing_years": 5, "structured_training_years": 1},
            "grades": {"lead_max_rp": "7a", "lead_max_os": "6b+"},
            "goal": {
                "discipline": "lead",
                "target_grade": "7b",
                "current_grade": "7a",
                "target_style": "all_round",
                "goal_type": "lead_grade",
                "deadline": "",
            },
            "self_eval": {"primary_weakness": "pump_too_early", "secondary_weakness": "technique_errors"},
            "tests": {},
            "limitations": [],
            "equipment": {
                "home_enabled": True,
                "home": ["hangboard", "pullup_bar"],
                "gyms": [{"name": "TestGym", "equipment": ["gym_routes", "gym_boulder", "hangboard"]}],
            },
            "availability": {
                day: {"evening": {"available": True, "preferred_location": "gym"}}
                for day in ("monday", "wednesday", "friday")
            },
            "planning_prefs": {"target_training_days_per_week": 3, "hard_day_cap_per_week": 2},
            "preferences": {"finger_training_device": "hangboard"},
            "trips": [],
            "outdoor_spots": [],
        }

    def _post_complete(self, client, payload, user_id):
        return client.post(
            "/api/onboarding/complete",
            json=payload,
            headers={"X-User-ID": user_id},
        )

    def test_attribution_saved_sanitized(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from backend.api.main import app
        from backend.api.deps import load_state

        user_id = "00000000-0000-4000-a000-000000000233"
        payload = self._minimal_payload()
        payload["attribution"] = {
            "utm_source": "reddit",
            "utm_campaign": "sideproject",
            "landing_page": "/demo",
            "junk_key": "dropme",
        }

        with TestClient(app) as client:
            resp = self._post_complete(client, payload, user_id)
        assert resp.status_code == 200, resp.text

        state = load_state(user_id)
        attr = state.get("attribution")
        assert attr is not None
        assert attr["utm_source"] == "reddit"
        assert attr["utm_campaign"] == "sideproject"
        assert attr["landing_page"] == "/demo"
        assert "junk_key" not in attr
        # server-stamped timestamp present
        assert attr.get("onboarded_at")

    def test_no_attribution_leaves_state_clean(self):
        from fastapi.testclient import TestClient
        from backend.api.main import app
        from backend.api.deps import load_state

        user_id = "00000000-0000-4000-a000-000000000234"
        payload = self._minimal_payload()

        with TestClient(app) as client:
            resp = self._post_complete(client, payload, user_id)
        assert resp.status_code == 200, resp.text

        state = load_state(user_id)
        assert "attribution" not in state

    def test_empty_attribution_dict_leaves_state_clean(self):
        from fastapi.testclient import TestClient
        from backend.api.main import app
        from backend.api.deps import load_state

        user_id = "00000000-0000-4000-a000-000000000235"
        payload = self._minimal_payload()
        payload["attribution"] = {}

        with TestClient(app) as client:
            resp = self._post_complete(client, payload, user_id)
        assert resp.status_code == 200, resp.text

        state = load_state(user_id)
        assert "attribution" not in state
