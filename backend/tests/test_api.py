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

    def test_delete_state_clears_outdoor_logs(self, tmp_path, monkeypatch):
        """DELETE /api/state must remove outdoor JSONL log files."""
        from backend.api.routers import state as state_mod
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "outdoor_sessions_2026.jsonl").write_text('{"test": true}\n')
        (log_dir / "outdoor_sessions_2025.jsonl").write_text('{"old": true}\n')
        monkeypatch.setattr(state_mod, "DATA_DIR", tmp_path)
        r = client.delete("/api/state")
        assert r.status_code == 200
        remaining = list(log_dir.glob("outdoor_sessions_*.jsonl"))
        assert remaining == [], f"Outdoor logs should be cleared after reset: {remaining}"


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
# Week navigation
# -----------------------------------------------------------------------

class TestWeekNavigation:
    """Test navigating between weeks preserves data and returns consistent results."""

    def _setup_full(self):
        """Full pipeline: assessment → macrocycle. Returns macrocycle."""
        client.post("/api/assessment/compute", json={})
        r = client.post("/api/macrocycle/generate", json={"total_weeks": 12})
        return r.json()["macrocycle"]

    def test_week_1_then_2_then_1_is_deterministic(self):
        """Fetching week 1, then week 2, then week 1 again returns same plan."""
        self._setup_full()
        r1a = client.get("/api/week/1")
        assert r1a.status_code == 200
        plan_1a = r1a.json()["week_plan"]

        r2 = client.get("/api/week/2")
        assert r2.status_code == 200

        r1b = client.get("/api/week/1")
        assert r1b.status_code == 200
        plan_1b = r1b.json()["week_plan"]

        # Same start_date
        assert plan_1a["start_date"] == plan_1b["start_date"]
        # Same number of days and sessions
        days_a = plan_1a["weeks"][0]["days"]
        days_b = plan_1b["weeks"][0]["days"]
        assert len(days_a) == len(days_b)
        for da, db in zip(days_a, days_b):
            assert da["date"] == db["date"]
            sids_a = [s["session_id"] for s in da.get("sessions", [])]
            sids_b = [s["session_id"] for s in db.get("sessions", [])]
            assert sids_a == sids_b

    def test_done_session_survives_navigation(self):
        """Mark a session done on current week, navigate away, come back — done persists."""
        self._setup_full()
        # Fetch current week and mark first session done
        r0 = client.get("/api/week/0")
        assert r0.status_code == 200
        wp = r0.json()["week_plan"]
        week_num = r0.json()["week_num"]

        days = wp["weeks"][0]["days"]
        day_with_session = next((d for d in days if d.get("sessions")), None)
        if day_with_session is None:
            return  # No sessions to test (skip gracefully)

        session = day_with_session["sessions"][0]
        r_done = client.post("/api/replanner/events", json={
            "week_plan": wp,
            "events": [{
                "event_type": "mark_done",
                "date": day_with_session["date"],
                "slot": session["slot"],
                "session_ref": session["session_id"],
            }],
        })
        assert r_done.status_code == 200

        # Navigate away to a different week
        other_week = week_num + 1 if week_num < 12 else week_num - 1
        r_other = client.get(f"/api/week/{other_week}")
        assert r_other.status_code == 200

        # Navigate back to current week (use explicit week_num, not 0)
        r_back = client.get(f"/api/week/{week_num}")
        assert r_back.status_code == 200
        back_plan = r_back.json()["week_plan"]

        # Find the day and verify done status persisted
        back_day = next(
            d for d in back_plan["weeks"][0]["days"]
            if d["date"] == day_with_session["date"]
        )
        done_s = next(
            (s for s in back_day["sessions"]
             if s["session_id"] == session["session_id"]),
            None,
        )
        assert done_s is not None, "Session disappeared after navigation"
        assert done_s["status"] == "done", f"Status was '{done_s['status']}' instead of 'done'"

    def test_all_weeks_return_valid_plans(self):
        """Navigate through all weeks sequentially — all should return valid plans."""
        mc = self._setup_full()
        total = sum(p.get("duration_weeks", 1) for p in mc["phases"])
        for wn in range(1, total + 1):
            r = client.get(f"/api/week/{wn}")
            assert r.status_code == 200, f"Week {wn} failed: {r.text}"
            wp = r.json()["week_plan"]
            assert wp.get("weeks"), f"Week {wn} has no weeks block"
            assert wp["weeks"][0].get("days"), f"Week {wn} has no days"

    def test_modify_non_current_week_does_not_clobber_cache(self):
        """Modifying a non-current week must NOT overwrite current week cache."""
        mc = self._setup_full()
        total = sum(p.get("duration_weeks", 1) for p in mc["phases"])

        # Get current week and mark a session done
        r0 = client.get("/api/week/0")
        assert r0.status_code == 200
        wp = r0.json()["week_plan"]
        current_wn = r0.json()["week_num"]

        days = wp["weeks"][0]["days"]
        day_with_session = next((d for d in days if d.get("sessions")), None)
        if day_with_session is None:
            return
        session = day_with_session["sessions"][0]

        # Mark done on current week
        r_done = client.post("/api/replanner/events", json={
            "week_plan": wp,
            "events": [{
                "event_type": "mark_done",
                "date": day_with_session["date"],
                "slot": session["slot"],
                "session_ref": session["session_id"],
            }],
        })
        assert r_done.status_code == 200

        # Now fetch a DIFFERENT week and modify it (add outdoor)
        other_wn = current_wn + 1 if current_wn < total else current_wn - 1
        r_other = client.get(f"/api/week/{other_wn}")
        assert r_other.status_code == 200
        other_wp = r_other.json()["week_plan"]
        other_day = other_wp["weeks"][0]["days"][0]

        client.post("/api/replanner/events", json={
            "week_plan": other_wp,
            "events": [{
                "event_type": "add_outdoor",
                "date": other_day["date"],
                "spot_name": "Test",
                "discipline": "lead",
            }],
        })

        # Navigate back to current week — done session must still be there
        r_back = client.get(f"/api/week/{current_wn}")
        assert r_back.status_code == 200
        back_plan = r_back.json()["week_plan"]
        back_day = next(
            d for d in back_plan["weeks"][0]["days"]
            if d["date"] == day_with_session["date"]
        )
        done_s = next(
            (s for s in back_day["sessions"]
             if s["session_id"] == session["session_id"]),
            None,
        )
        assert done_s is not None, "Session disappeared after modifying another week"
        assert done_s["status"] == "done", (
            f"Done status was clobbered: got '{done_s['status']}'"
        )

    def test_start_week_then_navigate(self):
        """After start-week offset, current week and adjacent weeks are all valid."""
        # Use onboarding flow to get a macrocycle
        payload = {
            "profile": {"name": "Nav", "age": 28, "weight_kg": 70, "height_cm": 175},
            "experience": {"climbing_years": 3, "structured_training_years": 1},
            "grades": {"lead_max_rp": "7a", "lead_max_os": "6b"},
            "goal": {
                "goal_type": "lead_grade", "discipline": "lead",
                "target_grade": "7b+", "target_style": "redpoint",
                "current_grade": "7a", "deadline": "2026-12-31",
            },
            "self_eval": {"primary_weakness": "pump_too_early", "secondary_weakness": "fingers_give_out"},
            "tests": {}, "limitations": [],
            "equipment": {"home": ["hangboard"], "gyms": [{"name": "G", "equipment": ["gym_boulder"]}]},
            "availability": {
                "mon": {"evening": {"available": True, "preferred_location": "gym"}},
                "wed": {"evening": {"available": True, "preferred_location": "gym"}},
                "sat": {"morning": {"available": True, "preferred_location": "gym"}},
            },
            "planning_prefs": {"hard_day_cap_per_week": 3, "target_training_days_per_week": 3},
            "trips": [],
        }
        r = client.post("/api/onboarding/complete", json=payload)
        assert r.status_code == 200

        # Apply start-week offset
        r_sw = client.post("/api/onboarding/start-week", json={"offset_weeks": 2})
        assert r_sw.status_code == 200
        assert r_sw.json()["offset_applied"] == 2

        # Current week should be offset by start-week adjustment
        r0 = client.get("/api/week/0")
        assert r0.status_code == 200
        assert r0.json()["week_num"] >= 2  # At least week 2 after offset=2

        # Navigate to week 1 and 2 (past weeks)
        for wn in [1, 2]:
            r = client.get(f"/api/week/{wn}")
            assert r.status_code == 200, f"Week {wn} after start-week failed"
            assert r.json()["week_plan"]["weeks"][0]["days"]

        # Navigate forward to week 4
        r4 = client.get("/api/week/4")
        assert r4.status_code == 200

        # Back to current
        r0b = client.get("/api/week/0")
        assert r0b.status_code == 200
        assert r0b.json()["week_plan"]["start_date"] == r0.json()["week_plan"]["start_date"]


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


# -----------------------------------------------------------------------
# Start-week (onboarding)
# -----------------------------------------------------------------------

class TestStartWeek:
    """POST /api/onboarding/start-week — shift macrocycle start_date."""

    _ONBOARDING_PAYLOAD = {
        "profile": {"name": "SW", "age": 28, "weight_kg": 70, "height_cm": 175},
        "experience": {"climbing_years": 3, "structured_training_years": 1},
        "grades": {"lead_max_rp": "7a", "lead_max_os": "6b"},
        "goal": {
            "goal_type": "lead_grade", "discipline": "lead",
            "target_grade": "7b+", "target_style": "redpoint",
            "current_grade": "7a", "deadline": "2026-12-31",
        },
        "self_eval": {"primary_weakness": "pump_too_early", "secondary_weakness": "fingers_give_out"},
        "tests": {}, "limitations": [],
        "equipment": {"home": ["hangboard"], "gyms": [{"name": "G", "equipment": ["gym_boulder"]}]},
        "availability": {
            "mon": {"evening": {"available": True, "preferred_location": "gym"}},
            "wed": {"evening": {"available": True, "preferred_location": "gym"}},
            "sat": {"morning": {"available": True, "preferred_location": "gym"}},
        },
        "planning_prefs": {"hard_day_cap_per_week": 3, "target_training_days_per_week": 3},
        "trips": [],
    }

    def _setup(self):
        r = client.post("/api/onboarding/complete", json=self._ONBOARDING_PAYLOAD)
        assert r.status_code == 200, r.text
        return r.json()["macrocycle"]

    def test_start_week_no_offset(self):
        mc = self._setup()
        original_start = mc["start_date"]
        r = client.post("/api/onboarding/start-week", json={"offset_weeks": 0})
        assert r.status_code == 200
        data = r.json()
        assert data["offset_applied"] == 0
        assert data["start_date"] == original_start

    def test_start_week_shifts_start_date(self):
        mc = self._setup()
        original_start = mc["start_date"]
        r = client.post("/api/onboarding/start-week", json={"offset_weeks": 2})
        assert r.status_code == 200
        data = r.json()
        assert data["offset_applied"] == 2
        # Should be 14 days earlier
        from datetime import datetime, timedelta
        expected = (datetime.strptime(original_start, "%Y-%m-%d") - timedelta(days=14)).strftime("%Y-%m-%d")
        assert data["start_date"] == expected

    def test_start_week_clamps_to_first_phase(self):
        mc = self._setup()
        first_dur = mc["phases"][0]["duration_weeks"]
        r = client.post("/api/onboarding/start-week", json={"offset_weeks": 99})
        assert r.status_code == 200
        data = r.json()
        assert data["offset_applied"] == first_dur - 1

    def test_start_week_no_macrocycle(self):
        client.delete("/api/state")
        r = client.post("/api/onboarding/start-week", json={"offset_weeks": 1})
        assert r.status_code == 422


# --------------------------------------------------------------------------- #
# B37: Add exercise to session
# --------------------------------------------------------------------------- #


class TestAddExercise:
    """Tests for POST /api/session/add-exercise."""

    @staticmethod
    def _mock_week_plan():
        """Build a minimal week plan with a resolved session."""
        return {
            "start_date": "2026-01-05",
            "weeks": [{
                "days": [
                    {
                        "date": "2026-01-05",
                        "weekday": "monday",
                        "sessions": [{
                            "slot": "evening",
                            "session_id": "finger_strength_gym",
                            "location": "gym",
                            "intensity": "high",
                            "tags": {"hard": True, "finger": True},
                            "resolved": {
                                "session_load_score": 10,
                                "resolved_session": {
                                    "exercise_instances": [
                                        {
                                            "exercise_id": "max_hang_20mm",
                                            "exercise_name": "Max Hang 20mm",
                                            "prescription": {"sets": 5, "reps": 1, "duration_s": 10},
                                            "source": "resolver",
                                        },
                                    ],
                                },
                            },
                        }],
                    },
                    {
                        "date": "2026-01-06",
                        "weekday": "tuesday",
                        "sessions": [],
                    },
                ],
            }],
        }

    def test_add_exercise_to_resolved_session(self):
        """B37: Adding an exercise appends it to the session."""
        wp = self._mock_week_plan()
        r = client.post("/api/session/add-exercise", json={
            "date": "2026-01-05",
            "session_index": 0,
            "exercise_id": "dead_hang_easy",
            "week_plan": wp,
        })
        assert r.status_code == 200
        updated = r.json()["week_plan"]
        day = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-05")
        instances = day["sessions"][0]["resolved"]["resolved_session"]["exercise_instances"]
        assert len(instances) == 2
        assert instances[-1]["exercise_id"] == "dead_hang_easy"
        assert instances[-1]["source"] == "user_added"

    def test_add_exercise_updates_load_score(self):
        """B37: Load score recalculates after adding exercise."""
        wp = self._mock_week_plan()
        r = client.post("/api/session/add-exercise", json={
            "date": "2026-01-05",
            "session_index": 0,
            "exercise_id": "dead_hang_easy",
            "week_plan": wp,
        })
        assert r.status_code == 200
        updated = r.json()["week_plan"]
        day = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-05")
        new_score = day["sessions"][0]["resolved"].get("session_load_score", 0)
        assert isinstance(new_score, (int, float))

    def test_add_exercise_not_found(self):
        """B37: Unknown exercise_id returns 404."""
        wp = self._mock_week_plan()
        r = client.post("/api/session/add-exercise", json={
            "date": "2026-01-05",
            "session_index": 0,
            "exercise_id": "nonexistent_exercise_xyz",
            "week_plan": wp,
        })
        assert r.status_code == 404

    def test_add_exercise_session_index_out_of_range(self):
        """B37: Out-of-range session_index returns 422."""
        wp = self._mock_week_plan()
        r = client.post("/api/session/add-exercise", json={
            "date": "2026-01-05",
            "session_index": 99,
            "exercise_id": "dead_hang_easy",
            "week_plan": wp,
        })
        assert r.status_code == 422

    def test_add_exercise_with_prescription_override(self):
        """B37: Custom prescription is applied to added exercise."""
        wp = self._mock_week_plan()
        r = client.post("/api/session/add-exercise", json={
            "date": "2026-01-05",
            "session_index": 0,
            "exercise_id": "dead_hang_easy",
            "prescription_override": {"sets": 5, "reps": 3, "load_kg": 20},
            "week_plan": wp,
        })
        assert r.status_code == 200
        updated = r.json()["week_plan"]
        day = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-05")
        added = day["sessions"][0]["resolved"]["resolved_session"]["exercise_instances"][-1]
        assert added["prescription"]["sets"] == 5
        assert added["prescription"]["reps"] == 3
        assert added["prescription"]["load_kg"] == 20
