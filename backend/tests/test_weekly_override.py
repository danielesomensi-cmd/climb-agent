"""Tests for B42 — Weekly Override merge logic + API CRUD."""

from __future__ import annotations

from copy import deepcopy

from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _build_session_pool, _adjust_domain_weights
from backend.engine.planner_v2 import generate_phase_week
from backend.engine.weekly_override import (
    build_merged_view,
    merge_override_into_availability,
)


def _default_availability():
    return {
        "mon": {
            "morning": {"available": True, "preferred_location": "home", "gym_id": None},
            "lunch": {"available": True, "preferred_location": "gym", "gym_id": "work_gym"},
            "evening": {"available": True, "preferred_location": "gym", "gym_id": "work_gym"},
        },
        "tue": {
            "morning": {"available": False, "preferred_location": "home", "gym_id": None},
            "lunch": {"available": True, "preferred_location": "home", "gym_id": None},
            "evening": {"available": True, "preferred_location": "gym", "gym_id": "work_gym"},
        },
        "wed": {
            "evening": {"available": True, "preferred_location": "gym", "gym_id": "work_gym"},
        },
        "thu": {
            "lunch": {"available": True, "preferred_location": "home", "gym_id": None},
        },
        "fri": {
            "evening": {"available": True, "preferred_location": "gym", "gym_id": "work_gym"},
        },
        "sat": {
            "morning": {"available": True, "preferred_location": "gym", "gym_id": "work_gym"},
        },
        "sun": {"available": False},
    }


# ---- Test 1: Merge with partial days ----

def test_merge_partial_days():
    """Override on 2 days, other 5 keep defaults."""
    avail = _default_availability()
    override = {
        "days": {
            "monday": {"available": False, "location": "rest"},
            "wednesday": {"available": True, "location": "outdoor"},
        }
    }
    result = merge_override_into_availability(avail, override)

    # Monday should be unavailable
    assert result["mon"].get("available") is False

    # Wednesday evening should be outdoor
    wed = result["wed"]
    assert wed["evening"]["available"] is True
    assert wed["evening"]["preferred_location"] == "outdoor"
    assert wed["evening"]["locations"] == ["outdoor"]

    # Tuesday should be unchanged
    assert result["tue"]["lunch"]["preferred_location"] == "home"
    assert result["tue"]["evening"]["gym_id"] == "work_gym"


# ---- Test 2: Merge with full week ----

def test_merge_full_week():
    """Override all 7 days."""
    avail = _default_availability()
    override = {
        "days": {
            "monday": {"available": True, "location": "home"},
            "tuesday": {"available": True, "location": "home"},
            "wednesday": {"available": False, "location": "rest"},
            "thursday": {"available": True, "location": "gym", "gym_id": "blocx"},
            "friday": {"available": True, "location": "outdoor"},
            "saturday": {"available": False, "location": "rest"},
            "sunday": {"available": True, "location": "gym", "gym_id": "work_gym"},
        }
    }
    result = merge_override_into_availability(avail, override)

    assert result["wed"].get("available") is False
    assert result["sat"].get("available") is False

    # Thursday should use blocx
    thu = result["thu"]
    thu_available_slots = [s for s in ("morning", "lunch", "evening") if isinstance(thu.get(s), dict) and thu[s].get("available")]
    assert len(thu_available_slots) >= 1
    for s in thu_available_slots:
        assert thu[s]["gym_id"] == "blocx"

    # Friday should be outdoor
    fri = result["fri"]
    fri_slots = [s for s in ("morning", "lunch", "evening") if isinstance(fri.get(s), dict) and fri[s].get("available")]
    for s in fri_slots:
        assert fri[s]["locations"] == ["outdoor"]


# ---- Test 3: No override = defaults unchanged ----

def test_no_override_returns_defaults():
    """Without override, result is a copy of availability."""
    avail = _default_availability()
    result = merge_override_into_availability(avail, None)
    assert result == avail

    result2 = merge_override_into_availability(avail, {})
    assert result2 == avail


# ---- Test 4: Planner respects override gym assignment ----

def test_planner_respects_override_gym():
    """With override changing gym, planner should assign the override gym."""
    avail = _default_availability()
    override = {
        "days": {
            "monday": {"available": True, "location": "gym", "gym_id": "blocx"},
        }
    }
    effective = merge_override_into_availability(avail, override)

    profile = {
        "finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
        "technique": 50, "endurance": 40, "body_composition": 65,
    }
    base_weights = _BASE_WEIGHTS["base"]
    domain_weights = _adjust_domain_weights(base_weights, profile)
    session_pool = _build_session_pool("base")

    plan = generate_phase_week(
        phase_id="base",
        domain_weights=domain_weights,
        session_pool=session_pool,
        start_date="2026-01-05",
        availability=effective,
        hard_cap_per_week=3,
        planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
        default_gym_id="work_gym",
        gyms=[
            {"gym_id": "work_gym", "equipment": ["gym_boulder", "board_kilter", "hangboard", "pullup_bar"]},
            {"gym_id": "blocx", "equipment": ["gym_boulder", "gym_routes", "hangboard", "pullup_bar"]},
        ],
    )

    # Monday sessions with gym location should reference blocx
    monday = plan["weeks"][0]["days"][0]
    for session in monday.get("sessions", []):
        if session.get("location") == "gym":
            assert session["gym_id"] == "blocx", f"Expected blocx, got {session['gym_id']}"


# ---- Test 5: Planner respects availability toggle ----

def test_planner_respects_override_unavailable():
    """Override marking a day unavailable → planner assigns no sessions."""
    avail = _default_availability()
    override = {
        "days": {
            "monday": {"available": False, "location": "rest"},
        }
    }
    effective = merge_override_into_availability(avail, override)

    profile = {
        "finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
        "technique": 50, "endurance": 40, "body_composition": 65,
    }
    base_weights = _BASE_WEIGHTS["base"]
    domain_weights = _adjust_domain_weights(base_weights, profile)
    session_pool = _build_session_pool("base")

    plan = generate_phase_week(
        phase_id="base",
        domain_weights=domain_weights,
        session_pool=session_pool,
        start_date="2026-01-05",
        availability=effective,
        hard_cap_per_week=3,
        planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
        default_gym_id="work_gym",
        gyms=[{"gym_id": "work_gym", "equipment": ["gym_boulder", "board_kilter"]}],
    )

    monday = plan["weeks"][0]["days"][0]
    assert monday["sessions"] == [], f"Monday should have no sessions, got {len(monday['sessions'])}"


# ---- Test 6: Override does not affect other weeks ----

def test_override_only_affects_target_week():
    """Override for week A should not affect week B."""
    avail = _default_availability()
    override_a = {
        "days": {"monday": {"available": False, "location": "rest"}},
    }
    # Merge for week A
    result_a = merge_override_into_availability(avail, override_a)
    # Merge for week B (no override)
    result_b = merge_override_into_availability(avail, None)

    assert result_a["mon"].get("available") is False
    # Week B Monday should still have available slots
    mon_b = result_b["mon"]
    assert any(
        isinstance(mon_b.get(s), dict) and mon_b[s].get("available")
        for s in ("morning", "lunch", "evening")
    )


# ---- Test 7: Override does not modify settings ----

def test_override_does_not_mutate_original():
    """merge_override_into_availability must never mutate the input availability."""
    avail = _default_availability()
    original_avail = deepcopy(avail)
    override = {
        "days": {
            "monday": {"available": False, "location": "rest"},
            "friday": {"available": True, "location": "outdoor"},
        }
    }
    merge_override_into_availability(avail, override)
    assert avail == original_avail, "Original availability was mutated!"


# ---- Test 8: API CRUD (unit-level, tests the data shapes) ----

def test_api_override_payload_shape():
    """WeeklyOverridePayload serializes correctly."""
    from backend.api.routers.weekly_override import DayOverridePayload, WeeklyOverridePayload

    payload = WeeklyOverridePayload(days={
        "monday": DayOverridePayload(available=True, location="gym", gym_id="blocx"),
        "wednesday": DayOverridePayload(available=False, location="rest"),
    })
    dumped = {k: v.model_dump() for k, v in payload.days.items()}
    assert dumped["monday"]["gym_id"] == "blocx"
    assert dumped["wednesday"]["available"] is False


# ---- Test 9: Override with outdoor location ----

def test_override_outdoor_location():
    """Override with outdoor → slots become outdoor."""
    avail = _default_availability()
    override = {
        "days": {
            "saturday": {"available": True, "location": "outdoor"},
        }
    }
    result = merge_override_into_availability(avail, override)
    sat = result["sat"]
    # Saturday morning was available → should now be outdoor
    assert sat["morning"]["locations"] == ["outdoor"]
    assert sat["morning"]["preferred_location"] == "outdoor"
    assert sat["morning"]["gym_id"] is None


# ---- Test 10: Override with rest = unavailable ----

def test_override_rest_means_unavailable():
    """Override with location=rest → day becomes unavailable."""
    avail = _default_availability()
    override = {
        "days": {
            "friday": {"available": True, "location": "rest"},
        }
    }
    result = merge_override_into_availability(avail, override)
    assert result["fri"].get("available") is False


# ---- Test 11: build_merged_view returns is_overridden flag ----

def test_merged_view_is_overridden_flag():
    """build_merged_view marks overridden days correctly."""
    avail = _default_availability()
    override = {
        "days": {
            "tuesday": {"available": True, "location": "outdoor"},
        }
    }
    view = build_merged_view(avail, override)
    assert len(view) == 7

    tue_view = next(d for d in view if d["day"] == "tue")
    assert tue_view["is_overridden"] is True

    mon_view = next(d for d in view if d["day"] == "mon")
    assert mon_view["is_overridden"] is False
