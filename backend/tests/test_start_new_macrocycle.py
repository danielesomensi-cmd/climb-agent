"""Integration tests for POST /api/macrocycle/start-new-cycle (A-NEW-MACRO).

Covers brief acceptance criteria T1-T12 plus history-immutability invariant
(D232 §3 — 33 preserved fields).
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine import storage

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    """Each test gets a fresh copy of the canonical fixture."""
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


def _future_deadline(weeks: int = 16) -> str:
    return (date.today() + timedelta(weeks=weeks)).isoformat()


def _valid_body(**overrides) -> dict:
    body = {
        "goal": {
            "discipline": "lead",
            "target_grade": "8a",
            "target_style": "redpoint",
            "deadline": _future_deadline(16),
        },
    }
    if overrides:
        body["goal"].update(overrides)
    return body


def _ensure_seed_state_has_macrocycle() -> dict:
    """Some fixtures may not include a macrocycle. Seed one if missing."""
    state = client.get("/api/state").json()
    if state.get("macrocycle"):
        return state
    # Seed via the existing onboarding/generate path — but the fixture already
    # has goal + assessment.profile, so we can call /api/macrocycle/generate.
    r = client.post("/api/macrocycle/generate", json={"total_weeks": 12})
    if r.status_code != 200:
        pytest.skip(f"Cannot seed macrocycle: {r.status_code} {r.text}")
    return client.get("/api/state").json()


# ── T1: happy path ─────────────────────────────────────────────────────────


class TestT1HappyPath:
    def test_returns_200_with_new_macrocycle(self):
        _ensure_seed_state_has_macrocycle()
        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r.status_code == 200, r.text
        data = r.json()
        assert "macrocycle" in data
        assert "archived_count" in data
        assert "start_date" in data

    def test_new_macrocycle_has_5_phases(self):
        _ensure_seed_state_has_macrocycle()
        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r.status_code == 200
        phases = r.json()["macrocycle"]["phases"]
        phase_ids = [p["phase_id"] for p in phases]
        assert phase_ids == ["base", "strength_power", "power_endurance", "performance", "deload"]

    def test_state_macrocycle_replaced(self):
        """B-NEWMACRO-STARTDATE-FIX: new_start is next Monday after today,
        independent of the old cycle's end_date."""
        _ensure_seed_state_has_macrocycle()
        old = client.get("/api/state").json()
        old_start = old["macrocycle"]["start_date"]
        today_iso = date.today().isoformat()
        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        new_start = r.json()["start_date"]
        assert new_start > today_iso, (
            f"New start {new_start} must be strictly after today {today_iso}"
        )
        new_start_d = datetime.strptime(new_start, "%Y-%m-%d").date()
        assert new_start_d.weekday() == 0
        assert new_start != old_start

        live = client.get("/api/state").json()
        assert live["macrocycle"]["start_date"] == new_start


# ── T2: archive integrity ─────────────────────────────────────────────────


class TestT2ArchiveIntegrity:
    def test_one_history_entry_after_call(self):
        _ensure_seed_state_has_macrocycle()
        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r.status_code == 200
        assert r.json()["archived_count"] == 1
        state = client.get("/api/state").json()
        assert len(state["macrocycle_history"]) == 1

    def test_history_entry_shape(self):
        _ensure_seed_state_has_macrocycle()
        client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        entry = client.get("/api/state").json()["macrocycle_history"][0]
        assert set(entry.keys()) == {
            "archived_at", "macrocycle", "goal_at_archive",
            "weeks_completed", "total_weeks", "completion_summary",
        }
        # The archived macrocycle is the OLD one (before overwrite).
        # total_weeks of the archived snapshot must match what was there before.
        assert isinstance(entry["completion_summary"]["sessions_done"], int)
        assert isinstance(entry["completion_summary"]["phases_completed"], list)


# ── T3: history immutability (D232 §3) ────────────────────────────────────


# Fields that MUST NOT change after start-new-cycle. Excludes fields the new
# endpoint legitimately touches: macrocycle, goal, assessment.profile,
# initial_tests_requested, current_week_plan, week_plans (partial), _prev_week_plan,
# macrocycle_history.
_PRESERVED_FIELDS = (
    "feedback_log",
    "session_completion_log",
    "outdoor_log",
    "official_maxes",
    "baselines",
    "custom_sessions",
    "weekly_overrides",
    "cooldowns",
    "stimulus_recency",
    "fatigue_proxy",
    "subscription",
    "free_sessions",
    "tests",  # in-app test history
    "trips",
    "limitations",
    "availability",
    "equipment",
    "preferences",
    "planning_prefs",
    "outdoor_spots",
    "quote_history",
    "user",
    "progression_counters",
    "progression_config",
    "test_queue",
    "history_index",
    "other_activities",
    "schema_version",
    "working_loads",  # entries[] are append-only history; multipliers carry over
    # assessment subfields — only profile may change; tests/grades/body/etc preserved
)


class TestT3HistoryImmutability:
    def test_preserved_fields_byte_identical(self):
        _ensure_seed_state_has_macrocycle()
        # Seed the fields likely to be empty in the fixture so the test is
        # meaningful. Use PUT /api/state to set them (deep-merge).
        client.put("/api/state", json={
            "feedback_log": [
                {"date": "2026-03-15", "session_id": "limit_boulder_gym",
                 "rpe": 7, "completed": True},
            ],
            "session_completion_log": [
                {"date": "2026-03-15", "session_id": "limit_boulder_gym",
                 "status": "done", "completed_at": "2026-03-15T12:00:00Z"},
            ],
            "weekly_overrides": {
                "2026-03-09": {"hard_day_cap_per_week": 2},
            },
        })
        before = client.get("/api/state").json()
        before_subset = {k: deepcopy(before.get(k)) for k in _PRESERVED_FIELDS}

        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r.status_code == 200

        after = client.get("/api/state").json()
        for field in _PRESERVED_FIELDS:
            assert after.get(field) == before_subset[field], (
                f"Field {field!r} mutated by start-new-cycle:\n"
                f"  before={before_subset[field]!r}\n  after ={after.get(field)!r}"
            )

    def test_assessment_grades_and_tests_preserved(self):
        """The endpoint recomputes profile but must NOT touch grades/tests/body."""
        _ensure_seed_state_has_macrocycle()
        before = client.get("/api/state").json()
        before_grades = deepcopy(before["assessment"]["grades"])
        before_tests = deepcopy(before["assessment"].get("tests"))
        before_body = deepcopy(before["assessment"].get("body"))

        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r.status_code == 200
        after = client.get("/api/state").json()
        assert after["assessment"]["grades"] == before_grades
        assert after["assessment"].get("tests") == before_tests
        assert after["assessment"].get("body") == before_body


# ── T4: week 1 has tests (Pass 3 via initial_tests_requested) ─────────────


class TestT4Week1HasTests:
    def test_week_1_contains_a_test_session(self):
        _ensure_seed_state_has_macrocycle()
        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r.status_code == 200
        # Force week 1 regeneration (the cache is already cleared, but force=true
        # is defensive against any test-env caching).
        wk = client.get("/api/week/0?force=true").json()
        days = (wk.get("week_plan") or {}).get("weeks", [{}])[0].get("days", [])
        all_session_ids = [
            s.get("session_id", "")
            for d in days
            for s in d.get("sessions", [])
        ]
        test_ids = [sid for sid in all_session_ids if sid.startswith("test_")]
        assert test_ids, (
            f"Week 1 should contain at least one test session, got {all_session_ids}"
        )


# ── T5: initial_tests_requested flag lifecycle ─────────────────────────────


class TestT5InitialTestsRequestedFlag:
    def test_flag_is_true_immediately_after_endpoint(self):
        _ensure_seed_state_has_macrocycle()
        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r.status_code == 200
        state = client.get("/api/state").json()
        assert state.get("initial_tests_requested") is True, (
            "initial_tests_requested must be True right after the endpoint "
            "(set AFTER generate_macrocycle in the atomic flow)."
        )

    def test_flag_persists_across_week_fetch(self):
        """Phase 0 reformulation: Pass 3 reads inject_tests but does NOT pop the
        flag. The flag remains True until the next macrocycle change pops it."""
        _ensure_seed_state_has_macrocycle()
        client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        client.get("/api/week/0?force=true")
        state = client.get("/api/state").json()
        assert state.get("initial_tests_requested") is True


# ── T6: start_date semantics ──────────────────────────────────────────────


class TestT6StartDate:
    def test_start_date_is_monday(self):
        _ensure_seed_state_has_macrocycle()
        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        start_iso = r.json()["start_date"]
        d = datetime.strptime(start_iso, "%Y-%m-%d").date()
        assert d.weekday() == 0, f"Expected Monday, got weekday {d.weekday()}"

    def test_start_date_ignores_ongoing_cycle_end_date(self):
        """B-NEWMACRO-STARTDATE-FIX regression test: an ongoing cycle ending
        in 2099 must NOT push the new start_date to 2099. The new cycle
        always starts the Monday after today, regardless of the current
        cycle's end_date."""
        _ensure_seed_state_has_macrocycle()
        # Patch the macrocycle to end far in 2099.
        client.put("/api/state", json={
            "macrocycle": {"end_date": "2099-06-30", "start_date": "2099-04-06"},
        })
        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r.status_code == 200, r.text
        # Pre-fix this would have been "2099-07-06". Post-fix it is the
        # Monday strictly after today — independent of the 2099 end_date.
        new_start = datetime.strptime(r.json()["start_date"], "%Y-%m-%d").date()
        assert new_start.weekday() == 0
        today = date.today()
        assert new_start > today, "Start must be strictly after today"
        assert (new_start - today).days <= 7, (
            f"Start must be next Monday (≤ 7 days away), got {(new_start - today).days} days"
        )

    def test_start_date_no_current_macrocycle_strict_next_monday(self):
        # Reset state, then build a minimal one without macrocycle.
        client.delete("/api/state")
        client.put("/api/state", json={
            "user": {"preferred_name": "Tester"},
            "goal": {
                "discipline": "lead", "target_grade": "8a",
                "current_grade": "7a", "deadline": _future_deadline(20),
            },
            "assessment": {
                "profile": {
                    "finger_strength": 60, "pulling_strength": 55,
                    "power_endurance": 50, "technique": 65, "endurance": 55,
                },
                "grades": {"lead_max_rp": "7a", "boulder_max_rp": "6C"},
            },
        })
        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r.status_code == 200, r.text
        start = datetime.strptime(r.json()["start_date"], "%Y-%m-%d").date()
        # Strict semantics: result is strictly AFTER today (never today itself).
        assert start > date.today(), "Start date must be strictly after today"
        assert start.weekday() == 0
        assert (start - date.today()).days <= 7


# ── T7: discipline switch ──────────────────────────────────────────────────


class TestT7DisciplineSwitch:
    def test_lead_to_boulder_remaps_target_grade(self):
        _ensure_seed_state_has_macrocycle()
        # Pre-existing goal in fixture is lead-shaped. Switch to boulder.
        body = {
            "goal": {
                "discipline": "boulder",
                "target_grade": "7B",  # Font directly
                "target_style": "redpoint",
                "deadline": _future_deadline(20),
            },
        }
        r = client.post("/api/macrocycle/start-new-cycle", json=body)
        assert r.status_code == 200, r.text
        state = client.get("/api/state").json()
        assert state["goal"]["discipline"] == "boulder"
        assert state["goal"]["target_boulder_grade"] == "7B"
        # Lead-equivalent for assessment: 7B → 7c+
        assert state["goal"]["target_grade"] == "7c+"
        assert state["goal"]["goal_type"] == "boulder_grade"

    def test_boulder_to_lead_clears_boulder_grade(self):
        # Set up a boulder cycle first.
        client.put("/api/state", json={
            "goal": {
                "discipline": "boulder",
                "target_grade": "7c+",
                "target_boulder_grade": "7B",
                "current_grade": "7b",
                "deadline": _future_deadline(20),
            },
        })
        _ensure_seed_state_has_macrocycle()
        # Switch back to lead.
        body = _valid_body(discipline="lead", target_grade="8a")
        r = client.post("/api/macrocycle/start-new-cycle", json=body)
        assert r.status_code == 200, r.text
        state = client.get("/api/state").json()
        assert state["goal"]["discipline"] == "lead"
        assert state["goal"]["target_grade"] == "8a"
        assert state["goal"].get("target_boulder_grade") is None


# ── T8: deadline validation ────────────────────────────────────────────────


class TestT8DeadlineValidation:
    def test_deadline_too_soon_returns_400(self):
        _ensure_seed_state_has_macrocycle()
        body = _valid_body(deadline=(date.today() + timedelta(weeks=4)).isoformat())
        r = client.post("/api/macrocycle/start-new-cycle", json=body)
        assert r.status_code == 400
        assert "Deadline" in r.json()["detail"] or "9 weeks" in r.json()["detail"]

    def test_invalid_deadline_format_returns_400(self):
        _ensure_seed_state_has_macrocycle()
        body = _valid_body(deadline="not-a-date")
        r = client.post("/api/macrocycle/start-new-cycle", json=body)
        assert r.status_code == 400


# ── T9: subscription expired → 402 ─────────────────────────────────────────


class TestT9SubscriptionExpired:
    def test_expired_subscription_returns_402_state_unchanged(self):
        _ensure_seed_state_has_macrocycle()
        before = client.get("/api/state").json()
        expired = {
            "status": "past_due", "is_active": False,
            "trial_days_remaining": None, "can_interact": False,
        }
        with patch(
            "backend.engine.subscription_guard.check_subscription",
            return_value=expired,
        ):
            r = client.post(
                "/api/macrocycle/start-new-cycle",
                json=_valid_body(),
                headers={"X-User-ID": "00000000-0000-4000-8000-000000000001"},
            )
        assert r.status_code == 402
        # State unchanged (no macrocycle replacement, no archive).
        after = client.get("/api/state").json()
        assert after.get("macrocycle", {}).get("start_date") == before.get("macrocycle", {}).get("start_date")
        assert len(after.get("macrocycle_history") or []) == len(before.get("macrocycle_history") or [])


# ── T10: atomicity ─────────────────────────────────────────────────────────


class TestT10Atomicity:
    def test_generate_failure_leaves_state_unchanged(self):
        _ensure_seed_state_has_macrocycle()
        before = client.get("/api/state").json()
        with patch(
            "backend.api.routers.macrocycle.generate_macrocycle",
            side_effect=RuntimeError("simulated engine failure"),
        ):
            r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r.status_code == 422
        after = client.get("/api/state").json()
        # Critical: no half-archive (history list unchanged), no goal mutation.
        assert (after.get("macrocycle_history") or []) == (before.get("macrocycle_history") or [])
        assert after["goal"] == before["goal"]
        assert after["macrocycle"]["start_date"] == before["macrocycle"]["start_date"]


# ── T11: chained restarts ──────────────────────────────────────────────────


class TestT11ChainedRestarts:
    def test_two_consecutive_calls_produce_two_history_entries(self):
        _ensure_seed_state_has_macrocycle()
        r1 = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r1.status_code == 200
        r2 = client.post("/api/macrocycle/start-new-cycle", json=_valid_body(
            target_grade="8a+",
        ))
        assert r2.status_code == 200, r2.text
        state = client.get("/api/state").json()
        assert len(state["macrocycle_history"]) == 2
        # Earlier entry is preserved unchanged.
        first = state["macrocycle_history"][0]
        second = state["macrocycle_history"][1]
        assert first != second
        assert first["macrocycle"]["start_date"] != second["macrocycle"]["start_date"]


# ── T12: invalidate_week_cache ─────────────────────────────────────────────


class TestT12WeekCacheInvalidation:
    def test_past_week_plans_preserved_future_dropped(self):
        """Past entries (key < new_start_date) preserved for history view.
        Future-or-equal entries cleared so the new cycle gets fresh weeks.

        Post B-NEWMACRO-STARTDATE-FIX: new_start_date is the Monday strictly
        after today, regardless of the current macrocycle's window. Test keys
        are anchored to today so the assertions hold whenever the suite runs.
        """
        _ensure_seed_state_has_macrocycle()
        today = date.today()
        # Past key — 4 weeks before today, definitely < new_start.
        past_key = (today - timedelta(weeks=4)).isoformat()
        # Future key — 30 weeks ahead, definitely >= new_start.
        future_key = (today + timedelta(weeks=30)).isoformat()

        client.put("/api/state", json={
            "week_plans": {
                past_key: {"start_date": past_key, "weeks": [{"days": []}]},
                future_key: {"start_date": future_key, "weeks": [{"days": []}]},
            },
        })

        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r.status_code == 200, r.text
        new_start = r.json()["start_date"]
        # Sanity: new_start lies between the two seeded keys.
        assert past_key < new_start <= future_key, (
            f"Test setup invalid: expected past_key={past_key} < "
            f"new_start={new_start} <= future_key={future_key}"
        )

        plans = client.get("/api/state").json().get("week_plans", {})
        # Past entry preserved.
        assert past_key in plans, f"Past entry {past_key} should be kept (< {new_start})"
        # Future entry — the rule is: drop keys >= new_start_date.
        assert future_key not in plans, (
            f"Future entry {future_key} should be dropped (>= {new_start})"
        )

    def test_current_week_plan_legacy_cache_cleared(self):
        _ensure_seed_state_has_macrocycle()
        client.put("/api/state", json={
            "current_week_plan": {"start_date": "2099-01-05", "weeks": []},
        })
        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r.status_code == 200
        state = client.get("/api/state").json()
        assert state.get("current_week_plan") in (None, {}), \
            f"current_week_plan should be cleared, got {state.get('current_week_plan')!r}"
