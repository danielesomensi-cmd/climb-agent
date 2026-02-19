"""API endpoint tests using FastAPI TestClient."""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    """Copy real state to tmp and monkeypatch STATE_PATH so tests are isolated."""
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


# -----------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------

class TestHealth:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# -----------------------------------------------------------------------
# State
# -----------------------------------------------------------------------

class TestState:
    def test_get_state(self):
        r = client.get("/api/state")
        assert r.status_code == 200
        data = r.json()
        assert "schema_version" in data

    def test_put_state_deep_merge(self):
        r = client.put("/api/state", json={"user": {"preferred_name": "Test"}})
        assert r.status_code == 200
        data = r.json()
        assert data["user"]["preferred_name"] == "Test"
        # Original fields preserved
        assert data["user"].get("name") is not None

    def test_delete_state_resets(self):
        r = client.delete("/api/state")
        assert r.status_code == 200
        data = r.json()
        assert data["state"]["schema_version"] == "1.5"
        assert data["state"]["macrocycle"] is None
        assert data["state"]["user"] == {}

    def test_get_after_delete_returns_empty(self):
        client.delete("/api/state")
        r = client.get("/api/state")
        assert r.status_code == 200
        assert r.json()["user"] == {}


# -----------------------------------------------------------------------
# Catalog
# -----------------------------------------------------------------------

class TestCatalog:
    def test_exercises(self):
        r = client.get("/api/catalog/exercises")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] > 0
        assert len(data["exercises"]) == data["count"]

    def test_sessions(self):
        r = client.get("/api/catalog/sessions")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] > 0
        assert all("id" in s for s in data["sessions"])

    def test_sessions_location_and_name_extraction(self):
        """B30/B31: catalog returns correct name, type, location for all session formats."""
        r = client.get("/api/catalog/sessions")
        data = r.json()
        by_id = {s["id"]: s for s in data["sessions"]}

        # New-style session (easy_climbing_deload) should use top-level fields
        deload = by_id["easy_climbing_deload"]
        assert deload["name"] == "Easy Climbing — Deload"
        assert deload["type"] == "climbing"
        assert deload["location"] == "gym"

        # Old-style session (strength_long) should extract from nested context.location
        strength = by_id["strength_long"]
        assert strength["name"] != "strength_long"  # should use the name field
        assert strength["location"] == "gym"  # from context.location


# -----------------------------------------------------------------------
# Onboarding
# -----------------------------------------------------------------------

class TestOnboarding:
    def test_defaults(self):
        r = client.get("/api/onboarding/defaults")
        assert r.status_code == 200
        data = r.json()
        assert "grades" in data
        assert "boulder_grades" in data
        assert "weakness_options" in data
        assert len(data["weakness_options"]) == 8
        assert "equipment_home" in data
        assert "equipment_gym" in data
        assert "test_descriptions" in data
        assert "slots" in data
        assert "weekdays" in data

    def test_complete_happy_path(self):
        """Full onboarding → assessment → macrocycle chain."""
        payload = {
            "profile": {
                "name": "Test User",
                "age": 30,
                "weight_kg": 75.0,
                "height_cm": 178,
            },
            "experience": {
                "climbing_years": 5,
                "structured_training_years": 2,
            },
            "grades": {
                "lead_max_rp": "7b+",
                "lead_max_os": "7a",
            },
            "goal": {
                "goal_type": "lead_grade",
                "discipline": "lead",
                "target_grade": "7c+",
                "target_style": "redpoint",
                "current_grade": "7b+",
                "deadline": "2026-09-30",
            },
            "self_eval": {
                "primary_weakness": "pump_too_early",
                "secondary_weakness": "fingers_give_out",
            },
            "tests": {},
            "limitations": [],
            "equipment": {
                "home_enabled": True,
                "home": ["hangboard", "pullup_bar"],
                "gyms": [{"name": "My Gym", "equipment": ["gym_boulder", "hangboard"]}],
            },
            "availability": {
                "mon": {"evening": {"available": True, "preferred_location": "home"}},
                "wed": {"evening": {"available": True, "preferred_location": "gym"}},
                "fri": {"evening": {"available": True, "preferred_location": "home"}},
                "sat": {"morning": {"available": True, "preferred_location": "gym"}},
            },
            "planning_prefs": {
                "hard_day_cap_per_week": 3,
                "target_training_days_per_week": 4,
            },
            "trips": [],
        }
        r = client.post("/api/onboarding/complete", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "profile" in data
        profile = data["profile"]
        assert "finger_strength" in profile
        assert "pulling_strength" in profile
        assert all(0 <= v <= 100 for v in profile.values())
        assert "macrocycle" in data
        assert data["macrocycle"]["phases"] is not None

    def test_complete_missing_goal_fields(self):
        """Onboarding with minimal goal should still work."""
        payload = {
            "profile": {"name": "Min", "weight_kg": 70, "height_cm": 170, "age": 25},
            "experience": {"climbing_years": 1, "structured_training_years": 0},
            "grades": {"lead_max_rp": "6a", "lead_max_os": "5c"},
            "goal": {
                "goal_type": "lead_grade",
                "discipline": "lead",
                "target_grade": "6c",
                "target_style": "redpoint",
                "current_grade": "6a",
                "deadline": "2026-12-31",
            },
            "self_eval": {"primary_weakness": "technique_errors", "secondary_weakness": "pump_too_early"},
            "tests": {},
            "limitations": [],
            "equipment": {"home": [], "gyms": []},
            "availability": {},
            "planning_prefs": {"hard_day_cap_per_week": 2, "target_training_days_per_week": 3},
            "trips": [],
        }
        r = client.post("/api/onboarding/complete", json=payload)
        assert r.status_code == 200, r.text


# -----------------------------------------------------------------------
# Assessment
# -----------------------------------------------------------------------

class TestAssessment:
    def test_compute_from_state(self):
        """Compute assessment using data already in state."""
        r = client.post("/api/assessment/compute", json={})
        assert r.status_code == 200
        profile = r.json()["profile"]
        assert all(k in profile for k in ["finger_strength", "pulling_strength", "power_endurance", "technique", "endurance", "body_composition"])

    def test_compute_with_explicit_data(self):
        r = client.post("/api/assessment/compute", json={
            "assessment": {
                "body": {"weight_kg": 75, "height_cm": 178},
                "grades": {"lead_max_rp": "7c", "lead_max_os": "7a"},
                "self_eval": {"primary_weakness": "pump_too_early", "secondary_weakness": "cant_hold_hard_moves"},
                "tests": {},
                "experience": {"climbing_years": 5, "structured_training_years": 2},
            },
            "goal": {
                "target_grade": "8a",
                "current_grade": "7c",
                "discipline": "lead",
            },
        })
        assert r.status_code == 200
        assert r.json()["profile"]["finger_strength"] >= 0

    def test_compute_no_goal_errors(self):
        """No goal in state or request → 422."""
        client.delete("/api/state")
        r = client.post("/api/assessment/compute", json={})
        assert r.status_code == 422


# -----------------------------------------------------------------------
# Macrocycle
# -----------------------------------------------------------------------

class TestMacrocycle:
    def _setup_profile(self):
        """Ensure state has assessment profile."""
        client.post("/api/assessment/compute", json={})

    def test_generate(self):
        self._setup_profile()
        r = client.post("/api/macrocycle/generate", json={"total_weeks": 12})
        assert r.status_code == 200
        mc = r.json()["macrocycle"]
        assert "phases" in mc
        assert len(mc["phases"]) >= 3

    def test_generate_no_profile_errors(self):
        client.delete("/api/state")
        r = client.post("/api/macrocycle/generate", json={})
        assert r.status_code == 422

    def test_generate_invalidates_week_cache(self):
        """Generating a new macrocycle should clear current_week_plan."""
        self._setup_profile()
        # Seed a fake cached week plan
        state = json.loads(deps.STATE_PATH.read_text())
        state["current_week_plan"] = {"fake": True}
        deps.STATE_PATH.write_text(json.dumps(state, indent=2))

        r = client.post("/api/macrocycle/generate", json={"total_weeks": 12})
        assert r.status_code == 200

        state_after = json.loads(deps.STATE_PATH.read_text())
        assert state_after.get("current_week_plan") is None


# -----------------------------------------------------------------------
# Week
# -----------------------------------------------------------------------

class TestWeek:
    def _setup_macrocycle(self):
        """Full pipeline: assessment → macrocycle."""
        client.post("/api/assessment/compute", json={})
        client.post("/api/macrocycle/generate", json={"total_weeks": 12})

    def test_get_week_1(self):
        self._setup_macrocycle()
        r = client.get("/api/week/1")
        assert r.status_code == 200
        data = r.json()
        assert "week_plan" in data
        assert "phase_id" in data

    def test_get_week_0_current(self):
        self._setup_macrocycle()
        r = client.get("/api/week/0")
        assert r.status_code == 200

    def test_get_week_no_macrocycle(self):
        client.delete("/api/state")
        r = client.get("/api/week/1")
        assert r.status_code == 422

    def test_get_week_out_of_range(self):
        self._setup_macrocycle()
        r = client.get("/api/week/999")
        assert r.status_code == 404


# -----------------------------------------------------------------------
# Session
# -----------------------------------------------------------------------

class TestSession:
    def test_resolve_known_session(self):
        r = client.post("/api/session/resolve", json={"session_id": "strength_long"})
        assert r.status_code == 200
        assert "resolved" in r.json()

    def test_resolve_unknown_session(self):
        r = client.post("/api/session/resolve", json={"session_id": "nonexistent_session"})
        assert r.status_code == 404


# -----------------------------------------------------------------------
# Replanner
# -----------------------------------------------------------------------

class TestReplanner:
    def _get_week_plan(self):
        """Full pipeline: assessment → macrocycle → week plan."""
        client.post("/api/assessment/compute", json={})
        client.post("/api/macrocycle/generate", json={"total_weeks": 12})
        r = client.get("/api/week/1")
        assert r.status_code == 200
        return r.json()["week_plan"]

    def test_override_no_plan_errors(self):
        r = client.post("/api/replanner/override", json={
            "intent": "rest",
            "location": "home",
            "reference_date": "2026-03-02",
        })
        assert r.status_code == 422

    def test_events_no_plan_errors(self):
        r = client.post("/api/replanner/events", json={
            "events": [{"event_type": "mark_done", "date": "2026-03-02"}],
        })
        assert r.status_code == 422

    def test_events_mark_done_keeps_session(self):
        """API-level: mark_done should retain session with status 'done'."""
        week_plan = self._get_week_plan()
        days = week_plan["weeks"][0]["days"]
        # Find first day with at least one session
        day = next(d for d in days if d.get("sessions"))
        session = day["sessions"][0]
        original_count = len(day["sessions"])

        r = client.post("/api/replanner/events", json={
            "week_plan": week_plan,
            "events": [{
                "event_type": "mark_done",
                "date": day["date"],
                "slot": session["slot"],
                "session_ref": session["session_id"],
            }],
        })
        assert r.status_code == 200
        updated_day = next(
            d for d in r.json()["week_plan"]["weeks"][0]["days"]
            if d["date"] == day["date"]
        )
        assert len(updated_day["sessions"]) == original_count
        done_s = next(s for s in updated_day["sessions"] if s["session_id"] == session["session_id"])
        assert done_s["status"] == "done"

    def test_events_mark_skipped_sets_day_status(self):
        """API-level: mark_skipped should set day status to 'skipped' and replace with recovery."""
        week_plan = self._get_week_plan()
        days = week_plan["weeks"][0]["days"]
        day = next(d for d in days if d.get("sessions"))
        session = day["sessions"][0]

        r = client.post("/api/replanner/events", json={
            "week_plan": week_plan,
            "events": [{
                "event_type": "mark_skipped",
                "date": day["date"],
                "slot": session["slot"],
                "session_ref": session["session_id"],
            }],
        })
        assert r.status_code == 200
        updated_day = next(
            d for d in r.json()["week_plan"]["weeks"][0]["days"]
            if d["date"] == day["date"]
        )
        assert updated_day["status"] == "skipped"
        recovery_s = next(s for s in updated_day["sessions"] if s["slot"] == session["slot"])
        assert recovery_s["session_id"] == "regeneration_easy"

    def test_events_auto_resolves_sessions(self):
        """API-level: events endpoint should auto-resolve recovery sessions."""
        week_plan = self._get_week_plan()
        days = week_plan["weeks"][0]["days"]
        day = next(d for d in days if d.get("sessions"))
        session = day["sessions"][0]

        r = client.post("/api/replanner/events", json={
            "week_plan": week_plan,
            "events": [{
                "event_type": "mark_skipped",
                "date": day["date"],
                "slot": session["slot"],
                "session_ref": session["session_id"],
            }],
        })
        assert r.status_code == 200
        updated_day = next(
            d for d in r.json()["week_plan"]["weeks"][0]["days"]
            if d["date"] == day["date"]
        )
        recovery_s = next(s for s in updated_day["sessions"] if s["slot"] == session["slot"])
        # Auto-resolve should have populated the "resolved" field
        assert "resolved" in recovery_s

    def test_events_persists_plan_to_state(self):
        """mark_done via events should persist plan, so GET /api/week/0 returns done status."""
        week_plan = self._get_week_plan()
        days = week_plan["weeks"][0]["days"]
        day = next(d for d in days if d.get("sessions"))
        session = day["sessions"][0]

        r = client.post("/api/replanner/events", json={
            "week_plan": week_plan,
            "events": [{
                "event_type": "mark_done",
                "date": day["date"],
                "slot": session["slot"],
                "session_ref": session["session_id"],
            }],
        })
        assert r.status_code == 200

        # Verify the persisted state has current_week_plan
        state = json.loads(deps.STATE_PATH.read_text())
        assert state.get("current_week_plan") is not None
        cached_day = next(
            d for d in state["current_week_plan"]["weeks"][0]["days"]
            if d["date"] == day["date"]
        )
        done_s = next(s for s in cached_day["sessions"] if s["session_id"] == session["session_id"])
        assert done_s["status"] == "done"

    def test_override_persists_plan_to_state(self):
        """Override should persist plan to state so GET /api/week/0 returns overridden session."""
        week_plan = self._get_week_plan()
        days = week_plan["weeks"][0]["days"]
        # Find a day to use as reference
        ref_day = days[0]

        r = client.post("/api/replanner/override", json={
            "week_plan": week_plan,
            "intent": "rest",
            "location": "home",
            "reference_date": ref_day["date"],
            "slot": "evening",
        })
        assert r.status_code == 200

        # Verify the persisted state has current_week_plan with the override
        state = json.loads(deps.STATE_PATH.read_text())
        assert state.get("current_week_plan") is not None
        assert state["current_week_plan"].get("weeks") is not None


# -----------------------------------------------------------------------
# Feedback
# -----------------------------------------------------------------------

class TestFeedback:
    def test_feedback_minimal(self):
        r = client.post("/api/feedback", json={
            "log_entry": {
                "date": "2026-03-02",
                "actual": {"exercise_feedback_v1": []},
            },
            "status": "done",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
