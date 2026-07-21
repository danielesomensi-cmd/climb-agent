"""B293: server-side onboarding wizard draft (GET/PUT /api/onboarding/draft).

The draft survives a forced re-auth mid-wizard; it is wiped by a successful
/complete and never resurrected once a macrocycle exists.
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_state():
    client.delete("/api/state")
    yield


def _draft(name="Dani", deepest_step=3):
    return {
        "data": {"profile": {"name": name, "age": 40, "weight_kg": 66, "height_cm": 172}},
        "deepest_step": deepest_step,
        "saved_at": 1753000000000,
    }


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


def test_draft_absent_by_default():
    r = client.get("/api/onboarding/draft")
    assert r.status_code == 200
    assert r.json()["draft"] is None


def test_draft_roundtrip():
    r = client.put("/api/onboarding/draft", json=_draft())
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = client.get("/api/onboarding/draft")
    draft = r.json()["draft"]
    assert draft["deepest_step"] == 3
    assert draft["data"]["profile"]["name"] == "Dani"
    assert draft["saved_at"] == 1753000000000


def test_draft_replaced_wholesale_not_merged():
    first = _draft()
    first["data"]["trips"] = [{"start_date": "2026-08-01"}]
    client.put("/api/onboarding/draft", json=first)

    second = _draft(name="Other", deepest_step=5)
    client.put("/api/onboarding/draft", json=second)

    draft = client.get("/api/onboarding/draft").json()["draft"]
    assert draft["data"]["profile"]["name"] == "Other"
    assert draft["deepest_step"] == 5
    # A stale section from the first draft must NOT survive a replace.
    assert "trips" not in draft["data"]


def test_successful_complete_wipes_draft():
    client.put("/api/onboarding/draft", json=_draft())
    r = client.post("/api/onboarding/complete", json=_complete_payload())
    assert r.status_code == 200

    assert client.get("/api/onboarding/draft").json()["draft"] is None
    state = client.get("/api/state").json()
    assert "onboarding_draft" not in state


def test_draft_ignored_after_completion():
    r = client.post("/api/onboarding/complete", json=_complete_payload())
    assert r.status_code == 200

    r = client.put("/api/onboarding/draft", json=_draft())
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"
    assert client.get("/api/onboarding/draft").json()["draft"] is None


def test_draft_size_cap():
    fat = _draft()
    fat["data"]["blob"] = "x" * 200_000
    r = client.put("/api/onboarding/draft", json=fat)
    assert r.status_code == 422
