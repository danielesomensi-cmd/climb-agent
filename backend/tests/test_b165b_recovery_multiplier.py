"""B165b: replanner recovery_multiplier spacing tests + age threshold tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from backend.engine.replanner_v1 import (
    _enforce_no_consecutive_finger,
    _recovery_gap,
    apply_day_add,
    apply_day_override,
    apply_events,
    suggest_sessions,
)
from backend.engine.planner_v2 import _SESSION_META, generate_phase_week
from backend.engine.macrocycle_v1 import _build_session_pool
from backend.api.routers.onboarding import _recovery_multiplier_for_age


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _availability():
    """7-day availability with gym+home."""
    avail = {}
    for wd in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
        avail[wd] = {
            "evening": {"available": True, "locations": ["gym", "home"], "gym_id": "gym1"},
        }
    return avail


def _make_plan(start_date="2026-01-05", recovery_multiplier=1.0, phase="strength_power"):
    """Generate a real plan with a specific recovery_multiplier."""
    weights = {"finger_strength": 0.3, "pulling_strength": 0.2, "power_endurance": 0.2, "technique": 0.15, "endurance": 0.15}
    pool = _build_session_pool(phase, "lead")
    plan = generate_phase_week(
        start_date=start_date,
        phase_id=phase,
        session_pool=pool,
        domain_weights=weights,
        availability=_availability(),
        allowed_locations=["gym", "home"],
        gyms=[{"gym_id": "gym1", "name": "Gym 1", "equipment": ["hangboard", "campus_board"]}],
        home_equipment=["hangboard", "resistance_bands", "pull_up_bar"],
        planning_prefs={
            "target_training_days_per_week": 5,
            "hard_day_cap_per_week": 3,
            "recovery_multiplier": recovery_multiplier,
        },
    )
    return plan


def _make_minimal_plan(days_data, recovery_multiplier=1.0):
    """Create a minimal plan structure for unit-testing helpers."""
    days = []
    base = datetime(2026, 1, 5)  # Monday
    for i, sessions in enumerate(days_data):
        d = base + timedelta(days=i)
        days.append({
            "date": d.strftime("%Y-%m-%d"),
            "weekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][i],
            "sessions": sessions,
        })
    return {
        "profile_snapshot": {"phase_id": "base", "recovery_multiplier": recovery_multiplier},
        "weeks": [{"days": days}],
    }


def _finger_session(slot="evening"):
    return {
        "session_id": "finger_strength_home",
        "slot": slot,
        "intensity": "max",
        "tags": {"hard": True, "finger": True},
        "status": "planned",
        "location": "home",
    }


def _recovery_session(slot="evening"):
    return {
        "session_id": "regeneration_easy",
        "slot": slot,
        "intensity": "low",
        "tags": {"hard": False, "finger": False},
        "status": "planned",
        "location": "home",
    }


# ---------------------------------------------------------------------------
# Tests: _recovery_gap helper
# ---------------------------------------------------------------------------


class TestRecoveryGap:
    def test_default_gap_is_1(self):
        plan = {"profile_snapshot": {}}
        assert _recovery_gap(plan) == 1

    def test_multiplier_1_0_gap_is_1(self):
        plan = {"profile_snapshot": {"recovery_multiplier": 1.0}}
        assert _recovery_gap(plan) == 1

    def test_multiplier_1_25_gap_is_2(self):
        plan = {"profile_snapshot": {"recovery_multiplier": 1.25}}
        assert _recovery_gap(plan) == 2

    def test_multiplier_1_5_gap_is_2(self):
        plan = {"profile_snapshot": {"recovery_multiplier": 1.5}}
        assert _recovery_gap(plan) == 2

    def test_no_profile_snapshot_gap_is_1(self):
        plan = {}
        assert _recovery_gap(plan) == 1


# ---------------------------------------------------------------------------
# Tests: _enforce_no_consecutive_finger respects multiplier
# ---------------------------------------------------------------------------


class TestEnforceFingerSpacing:
    def test_default_allows_2_day_gap(self):
        """With multiplier=1.0, finger on Mon and Wed (2-day gap) is OK."""
        plan = _make_minimal_plan([
            [_finger_session()],  # Mon
            [_recovery_session()],  # Tue
            [_finger_session()],  # Wed — 2 days after Mon, OK
            [], [], [], [],
        ], recovery_multiplier=1.0)
        _enforce_no_consecutive_finger(plan)
        wed = plan["weeks"][0]["days"][2]
        assert any((s.get("tags") or {}).get("finger") for s in wed["sessions"]), \
            "Wed finger should survive with 2-day gap at mult=1.0"

    def test_default_downgrades_consecutive(self):
        """With multiplier=1.0, finger on Mon and Tue (1-day gap) is downgraded."""
        plan = _make_minimal_plan([
            [_finger_session()],  # Mon
            [_finger_session()],  # Tue — 1 day gap, should be downgraded
            [], [], [], [], [],
        ], recovery_multiplier=1.0)
        _enforce_no_consecutive_finger(plan)
        tue = plan["weeks"][0]["days"][1]
        for s in tue["sessions"]:
            assert not (s.get("tags") or {}).get("finger"), \
                "Tue finger should be downgraded at mult=1.0 (1-day gap)"

    def test_high_multiplier_downgrades_2_day_gap(self):
        """With multiplier=1.5 (gap=2), finger on Mon and Wed (2-day gap) is downgraded."""
        plan = _make_minimal_plan([
            [_finger_session()],  # Mon
            [_recovery_session()],  # Tue
            [_finger_session()],  # Wed — 2 days after Mon, but gap=2 means <=2 is too close
            [], [], [], [],
        ], recovery_multiplier=1.5)
        _enforce_no_consecutive_finger(plan)
        wed = plan["weeks"][0]["days"][2]
        for s in wed["sessions"]:
            assert not (s.get("tags") or {}).get("finger"), \
                "Wed finger should be downgraded at mult=1.5 (2-day gap <= gap of 2)"

    def test_high_multiplier_allows_3_day_gap(self):
        """With multiplier=1.5 (gap=2), finger on Mon and Thu (3-day gap) is OK."""
        plan = _make_minimal_plan([
            [_finger_session()],  # Mon
            [_recovery_session()],  # Tue
            [_recovery_session()],  # Wed
            [_finger_session()],  # Thu — 3 days after Mon, > gap of 2
            [], [], [],
        ], recovery_multiplier=1.5)
        _enforce_no_consecutive_finger(plan)
        thu = plan["weeks"][0]["days"][3]
        assert any((s.get("tags") or {}).get("finger") for s in thu["sessions"]), \
            "Thu finger should survive with 3-day gap at mult=1.5"


# ---------------------------------------------------------------------------
# Tests: planner writes recovery_multiplier to profile_snapshot
# ---------------------------------------------------------------------------


class TestPlannerWritesMultiplier:
    def test_plan_has_recovery_multiplier(self):
        plan = _make_plan(recovery_multiplier=1.25)
        assert plan["profile_snapshot"]["recovery_multiplier"] == 1.25

    def test_plan_default_multiplier(self):
        plan = _make_plan(recovery_multiplier=1.0)
        assert plan["profile_snapshot"]["recovery_multiplier"] == 1.0


# ---------------------------------------------------------------------------
# Tests: quick-add and override don't break planned_load but respect spacing
# ---------------------------------------------------------------------------


class TestQuickAddRespectsMultiplier:
    def test_suggest_penalizes_finger_within_gap(self):
        """suggest_sessions should penalize finger when within recovery gap."""
        plan = _make_plan(recovery_multiplier=1.5)
        # Find a day with a finger session
        finger_date = None
        for day in plan["weeks"][0]["days"]:
            if any((s.get("tags") or {}).get("finger") for s in day.get("sessions", [])):
                finger_date = day["date"]
                break
        if finger_date is None:
            pytest.skip("Plan has no finger session to test adjacency")

        # Suggest for the next day
        from datetime import datetime as dt, timedelta as td
        next_date = (dt.fromisoformat(finger_date) + td(days=1)).isoformat()[:10]
        suggestions = suggest_sessions(plan, next_date, "home")
        # finger sessions should be scored very low (penalized)
        for s in suggestions:
            meta = _SESSION_META.get(s.get("session_id", ""), {})
            if meta.get("finger"):
                assert False, f"Finger session {s['session_id']} should not be suggested adjacent to finger day"


# ---------------------------------------------------------------------------
# Tests: age threshold (Change 2)
# ---------------------------------------------------------------------------


class TestAgeThreshold:
    def test_age_under_50_returns_1_0(self):
        assert _recovery_multiplier_for_age(25) == 1.0
        assert _recovery_multiplier_for_age(45) == 1.0
        assert _recovery_multiplier_for_age(49) == 1.0

    def test_age_50_returns_1_25(self):
        assert _recovery_multiplier_for_age(50) == 1.25
        assert _recovery_multiplier_for_age(55) == 1.25
        assert _recovery_multiplier_for_age(59) == 1.25

    def test_age_60_plus_returns_1_5(self):
        assert _recovery_multiplier_for_age(60) == 1.5
        assert _recovery_multiplier_for_age(70) == 1.5

    def test_age_none_returns_1_0(self):
        assert _recovery_multiplier_for_age(None) == 1.0


# ---------------------------------------------------------------------------
# Tests: backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_plan_without_profile_snapshot_uses_default_gap(self):
        """Pre-B165b plans without recovery_multiplier should use gap=1."""
        plan = _make_minimal_plan([
            [_finger_session()],
            [_finger_session()],  # 1-day gap — should be downgraded with default gap=1
            [], [], [], [], [],
        ])
        # Remove recovery_multiplier to simulate old plan
        del plan["profile_snapshot"]["recovery_multiplier"]
        _enforce_no_consecutive_finger(plan)
        tue = plan["weeks"][0]["days"][1]
        for s in tue["sessions"]:
            assert not (s.get("tags") or {}).get("finger"), \
                "Should fall back to gap=1 and downgrade consecutive finger"
