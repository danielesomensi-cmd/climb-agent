"""B175 — Input validation hardening tests.

Covers:
- D172-02: apply_events safe dict access (move_session, add_outdoor)
- D172-03: ensure_monday error handling (422 on bad date)
- D172-04: stale session warning in week auto-resolve
- D172-06: set_availability (retired in B367 — now refused)
"""
from __future__ import annotations

import pytest

from backend.engine.planner_v1 import generate_week_plan
from backend.engine.replanner_v1 import apply_events
from backend.engine.macrocycle_v1 import (
    _BASE_WEIGHTS,
    _BASE_WEIGHTS_BOULDER,
    _build_session_pool,
    _adjust_domain_weights,
)
from backend.engine.planner_v2 import generate_phase_week


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _availability():
    return {
        "mon": {"evening": {"available": True, "locations": ["gym"], "gym_id": "g1"}},
        "tue": {"evening": {"available": True, "locations": ["gym"], "gym_id": "g1"}},
        "wed": {"evening": {"available": True, "locations": ["gym"], "gym_id": "g1"}},
        "thu": {"evening": {"available": True, "locations": ["gym"], "gym_id": "g1"}},
        "fri": {"evening": {"available": True, "locations": ["gym"], "gym_id": "g1"}},
        "sat": {"morning": {"available": True, "locations": ["gym"], "gym_id": "g1"}},
        "sun": {"available": False},
    }


def _plan():
    return generate_week_plan(
        start_date="2026-01-05",
        mode="balanced",
        availability=_availability(),
        allowed_locations=["gym"],
        hard_cap_per_week=3,
        planning_prefs={"default_gym_id": "g1"},
        default_gym_id="g1",
        gyms=[{"gym_id": "g1", "equipment": ["gym_boulder"]}],
    )


def _phase_plan(discipline="lead"):
    phase_id = "base"
    base_weights = (
        _BASE_WEIGHTS_BOULDER if discipline == "boulder" else _BASE_WEIGHTS
    ).get(phase_id)
    domain_weights = _adjust_domain_weights(base_weights, {})
    session_pool = _build_session_pool(phase_id, discipline=discipline)
    plan = generate_phase_week(
        phase_id=phase_id,
        domain_weights=domain_weights,
        session_pool=session_pool,
        start_date="2026-01-05",
        availability=_availability(),
        allowed_locations=["gym"],
        hard_cap_per_week=3,
        planning_prefs={"default_gym_id": "g1"},
        default_gym_id="g1",
        gyms=[{"gym_id": "g1", "equipment": ["gym_boulder"]}],
    )
    plan["profile_snapshot"] = plan.get("profile_snapshot") or {}
    plan["profile_snapshot"]["discipline"] = discipline
    plan["profile_snapshot"]["phase_id"] = phase_id
    return plan


# ---------------------------------------------------------------------------
# D172-02: apply_events — missing required fields → ValueError (not KeyError)
# ---------------------------------------------------------------------------

class TestApplyEventsMissingFields:
    def test_move_session_missing_from_date_raises_value_error(self):
        plan = _plan()
        with pytest.raises(ValueError, match="from_date"):
            apply_events(plan, [{"event_type": "move_session", "to_date": "2026-01-06", "to_slot": "evening"}])

    def test_move_session_missing_to_date_raises_value_error(self):
        plan = _plan()
        with pytest.raises(ValueError, match="to_date"):
            apply_events(plan, [{"event_type": "move_session", "from_date": "2026-01-05", "to_slot": "evening"}])

    def test_move_session_missing_to_slot_raises_value_error(self):
        plan = _plan()
        with pytest.raises(ValueError, match="to_slot"):
            apply_events(plan, [{"event_type": "move_session", "from_date": "2026-01-05", "to_date": "2026-01-06"}])

    def test_add_outdoor_missing_spot_name_raises_value_error(self):
        plan = _plan()
        with pytest.raises(ValueError, match="spot_name"):
            apply_events(plan, [{"event_type": "add_outdoor", "date": "2026-01-05"}])

    def test_move_session_with_all_required_fields_succeeds(self):
        plan = _plan()
        # Get a valid source day and slot
        source_day = next(d for d in plan["weeks"][0]["days"] if d.get("sessions"))
        source_date = source_day["date"]
        source_slot = source_day["sessions"][0]["slot"]
        dest_day = next(
            d for d in plan["weeks"][0]["days"]
            if d["date"] != source_date
        )
        dest_date = dest_day["date"]
        result = apply_events(plan, [{
            "event_type": "move_session",
            "from_date": source_date,
            "from_slot": source_slot,
            "to_date": dest_date,
            "to_slot": source_slot,
        }])
        assert result is not None

    def test_add_outdoor_with_spot_name_succeeds(self):
        plan = _plan()
        result = apply_events(plan, [{
            "event_type": "add_outdoor",
            "date": "2026-01-05",
            "spot_name": "Arco",
        }])
        day = next(d for d in result["weeks"][0]["days"] if d["date"] == "2026-01-05")
        assert day.get("outdoor_spot_name") == "Arco"


# ---------------------------------------------------------------------------
# D172-03: ensure_monday — malformed dates → HTTPException 422
# ---------------------------------------------------------------------------

class TestEnsureMonday:
    def test_invalid_string_raises_422(self):
        from fastapi import HTTPException
        from backend.api.deps import ensure_monday
        with pytest.raises(HTTPException) as exc_info:
            ensure_monday("not-a-date")
        assert exc_info.value.status_code == 422
        assert "YYYY-MM-DD" in exc_info.value.detail

    def test_invalid_month_raises_422(self):
        from fastapi import HTTPException
        from backend.api.deps import ensure_monday
        with pytest.raises(HTTPException) as exc_info:
            ensure_monday("2026-13-45")
        assert exc_info.value.status_code == 422

    def test_valid_monday_returns_same(self):
        from backend.api.deps import ensure_monday
        # 2026-01-05 is a Monday
        assert ensure_monday("2026-01-05") == "2026-01-05"

    def test_valid_non_monday_rounds_down(self):
        from backend.api.deps import ensure_monday
        # 2026-01-07 (Wednesday) → 2026-01-05 (Monday)
        assert ensure_monday("2026-01-07") == "2026-01-05"

    def test_empty_string_raises_422(self):
        from fastapi import HTTPException
        from backend.api.deps import ensure_monday
        with pytest.raises(HTTPException) as exc_info:
            ensure_monday("")
        assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# D172-04: stale session — week.py logs warning (tested via module logic)
# ---------------------------------------------------------------------------

class TestStaleSessionGuard:
    def test_missing_session_file_sets_resolved_none(self):
        """_auto_resolve: session_id not in catalog → resolved=None (no crash)."""
        from backend.api.routers.week import _auto_resolve
        week_plan = {
            "weeks": [{
                "days": [{
                    "date": "2026-01-05",
                    "sessions": [{
                        "session_id": "nonexistent_session_xyz_b175",
                        "slot": "evening",
                    }]
                }]
            }]
        }
        state = {"context": {}}
        # Should not raise; sets resolved=None on missing session
        _auto_resolve(week_plan, state, user_id="test_user", phase="base")
        sess = week_plan["weeks"][0]["days"][0]["sessions"][0]
        assert sess.get("resolved") is None

    def test_missing_session_file_warning_logged(self, caplog):
        """_auto_resolve: logs a warning when session file is not found."""
        import logging
        from backend.api.routers.week import _auto_resolve
        week_plan = {
            "weeks": [{
                "days": [{
                    "date": "2026-01-05",
                    "sessions": [{
                        "session_id": "nonexistent_session_xyz_b175",
                        "slot": "evening",
                    }]
                }]
            }]
        }
        state = {"context": {}}
        with caplog.at_level(logging.WARNING, logger="backend.api.routers.week"):
            _auto_resolve(week_plan, state, user_id="test_user", phase="base")
        assert any("nonexistent_session_xyz_b175" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# D172-06: set_availability — retired in B367
# ---------------------------------------------------------------------------

class TestSetAvailabilityRetired:
    """D172-06 tested the discipline-aware weights of the set_availability
    regeneration. B367 retired the event (it lost tests and the retest
    snapshot); what remains to test is that it is refused."""

    def test_set_availability_raises(self):
        plan = _plan()
        before = __import__("copy").deepcopy(plan)
        with pytest.raises(ValueError, match="no longer supported"):
            apply_events(
                plan,
                [{"event_type": "set_availability", "availability": {"weekday": "mon", "slot": "evening"}}],
                availability=_availability(),
            )
        assert plan == before
