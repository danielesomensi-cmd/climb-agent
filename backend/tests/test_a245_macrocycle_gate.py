"""A245 E-2 (B10, B15) — POST /api/macrocycle/generate hardening.

B10: every other state mutation was subscription-gated; this one was not, so a
user with an expired trial could still regenerate their whole macrocycle while
being blocked everywhere else.

B15: `total_weeks` had no bounds, and a generation failure returned the engine's
own exception text to the user.
"""

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine import storage

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_STATE = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    """Each test gets its own state file.

    Without this the API calls below write into the REAL
    ``backend/data/user_state.json`` — caught while reviewing the E-6 diff,
    which showed that file dirty. Same class of leak as B-TEST-COACH-ISOLATION.
    """
    tmp_state = tmp_path / "user_state.json"
    if FIXTURE_STATE.exists():
        shutil.copy2(FIXTURE_STATE, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state

USER = "00000000-0000-4000-8000-0000000002a4"
EXPIRED = {
    "status": "past_due",
    "is_active": False,
    "trial_days_remaining": None,
    "can_interact": False,
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _headers():
    return {"X-User-ID": USER}


class TestSubscriptionGate:
    def test_expired_subscription_cannot_regenerate_the_macrocycle(self, client):
        with patch(
            "backend.engine.subscription_guard.check_subscription",
            return_value=EXPIRED,
        ):
            r = client.post("/api/macrocycle/generate", json={}, headers=_headers())
        assert r.status_code == 402
        assert r.json()["detail"]["error"] == "subscription_required"

    def test_gate_does_not_fire_for_an_entitled_user(self, client):
        """The gate must not be the reason an entitled user fails."""
        active = {**EXPIRED, "status": "active", "is_active": True, "can_interact": True}
        with patch(
            "backend.engine.subscription_guard.check_subscription",
            return_value=active,
        ):
            r = client.post("/api/macrocycle/generate", json={}, headers=_headers())
        assert r.status_code != 402


class TestTotalWeeksBounds:
    @pytest.mark.parametrize("weeks", [0, 1, 7, 17, 52, 1000, -5])
    def test_out_of_range_is_rejected_at_the_edge(self, client, weeks):
        r = client.post(
            "/api/macrocycle/generate",
            json={"total_weeks": weeks},
            headers=_headers(),
        )
        # 422 from pydantic validation — never reaches the engine.
        assert r.status_code == 422

    @pytest.mark.parametrize("weeks", [8, 12, 16])
    def test_in_range_is_accepted_by_validation(self, client, weeks):
        r = client.post(
            "/api/macrocycle/generate",
            json={"total_weeks": weeks},
            headers=_headers(),
        )
        # May still fail for engine reasons (no profile in this fixture); the
        # point is that validation is not what rejected it.
        if r.status_code == 422:
            detail = r.json()["detail"]
            assert not isinstance(detail, list), f"pydantic rejected {weeks}"


class TestErrorLeakage:
    def test_engine_failure_does_not_leak_internals_to_the_user(self, client):
        # The endpoint short-circuits on a missing goal/profile before it ever
        # calls the engine, so seed just enough to reach the generation step.
        client.put(
            "/api/state",
            json={
                "goal": {
                    "goal_type": "lead_grade",
                    "discipline": "lead",
                    "target_grade": "7a",
                    "current_grade": "6c",
                    "deadline": "2027-06-01",
                    "total_weeks": 12,
                },
                "assessment": {"profile": {
                    "finger_strength": 50, "pulling_strength": 50,
                    "power_endurance": 50, "technique": 50, "endurance": 50,
                }},
            },
            headers=_headers(),
        )
        with patch(
            "backend.api.routers.macrocycle.generate_macrocycle",
            side_effect=ValueError("phases[3].weeks None not in _GRADE_INDEX at offset 0x1f"),
        ):
            r = client.post("/api/macrocycle/generate", json={}, headers=_headers())
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert isinstance(detail, str)
        for leaked in ("_GRADE_INDEX", "phases[3]", "0x1f", "ValueError"):
            assert leaked not in detail
        # And it still tells the user what to do.
        assert "try again" in detail.lower()
