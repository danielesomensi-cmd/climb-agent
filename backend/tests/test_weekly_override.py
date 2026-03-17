"""Tests for B42 — Weekly Override merge logic + API CRUD."""

from __future__ import annotations

from copy import deepcopy

from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _build_session_pool, _adjust_domain_weights
from backend.engine.planner_v2 import generate_phase_week
from backend.engine.weekly_override import (
    build_merged_view,
    build_slot_view,
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
        "technique": 50, "endurance": 40,
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
        "technique": 50, "endurance": 40,
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
    from backend.api.routers.weekly_override import DayOverridePayload, SlotOverridePayload, WeeklyOverridePayload

    payload = WeeklyOverridePayload(days={
        "monday": DayOverridePayload(
            available=True,
            slots={"evening": SlotOverridePayload(available=True, location="gym", gym_id="blocx")},
        ),
        "wednesday": DayOverridePayload(available=False),
    })
    dumped = {k: v.model_dump() for k, v in payload.days.items()}
    assert dumped["monday"]["slots"]["evening"]["gym_id"] == "blocx"
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


# ---- Bug A: build_slot_view should return default_slots even for rest-overridden days ----

def test_bug_a_rest_day_preserves_default_slots():
    """Bug A/B: When a day is rest (via override or default), the GET response
    must include ``default_slots`` with the original slot data so the frontend
    can restore availability when un-toggling Rest.

    EXPECTED TO FAIL until fix is applied — build_slot_view currently returns
    ``slots: []`` for rest days and no ``default_slots`` field.
    """
    avail = _default_availability()
    # Override Monday to rest
    override = {"days": {"monday": {"available": False}}}
    view = build_slot_view(avail, override)
    mon = next(d for d in view if d["day"] == "mon")

    # Day should be marked unavailable
    assert mon["available"] is False

    # MUST have default_slots with the original Monday slots (3 slots)
    assert "default_slots" in mon, "Missing default_slots field for rest day"
    assert len(mon["default_slots"]) == 3
    # Verify default_slots contain the original data
    morning = next(s for s in mon["default_slots"] if s["slot"] == "morning")
    assert morning["available"] is True
    assert morning["location"] == "home"


# ---- Bug B: default_slots also needed for days that are rest by default ----

def test_bug_b_default_rest_day_has_default_slots():
    """Bug B: Sunday is rest by default (``{available: False}``). The view must
    still provide ``default_slots`` (empty is ok since there are no slots defined)
    so the frontend never crashes on missing field.
    """
    avail = _default_availability()
    view = build_slot_view(avail, None)
    sun = next(d for d in view if d["day"] == "sun")
    assert sun["available"] is False
    assert "default_slots" in sun, "Missing default_slots for default-rest day"


# ---- Bug C: Slot-level override with gym_id should round-trip through build_slot_view ----

def test_bug_c_slot_override_gym_id_roundtrip():
    """Bug C: When an override sets a specific slot to gym with a gym_id,
    build_slot_view must reflect that gym_id. The frontend crashed when
    selecting gym because the gym_id wasn't properly propagated.
    """
    avail = _default_availability()
    # Slot-level override: Monday evening → gym at blocx
    override = {
        "days": {
            "monday": {
                "available": True,
                "slots": {
                    "evening": {"available": True, "location": "gym", "gym_id": "blocx"},
                },
            },
        },
    }
    view = build_slot_view(avail, override)
    mon = next(d for d in view if d["day"] == "mon")

    assert mon["available"] is True
    evening = next(s for s in mon["slots"] if s["slot"] == "evening")
    assert evening["available"] is True
    assert evening["location"] == "gym"
    assert evening["gym_id"] == "blocx"

    # Non-overridden slots should keep original values
    morning = next(s for s in mon["slots"] if s["slot"] == "morning")
    assert morning["available"] is True
    assert morning["location"] == "home"


# ---- Bug D: Slot-level override must preserve non-overridden slots ----

def test_bug_d_slot_level_preserves_others():
    """Bug D: When override changes only morning slot, lunch and evening must
    keep their original availability and location from the default settings.
    """
    avail = _default_availability()
    # Override only Tuesday morning to available+gym
    override = {
        "days": {
            "tuesday": {
                "available": True,
                "slots": {
                    "morning": {"available": True, "location": "gym", "gym_id": "work_gym"},
                },
            },
        },
    }
    view = build_slot_view(avail, override)
    tue = next(d for d in view if d["day"] == "tue")

    # Morning should be overridden
    morning = next(s for s in tue["slots"] if s["slot"] == "morning")
    assert morning["available"] is True
    assert morning["location"] == "gym"
    assert morning["gym_id"] == "work_gym"

    # Lunch should keep original (available, home)
    lunch = next(s for s in tue["slots"] if s["slot"] == "lunch")
    assert lunch["available"] is True
    assert lunch["location"] == "home"

    # Evening should keep original (available, gym, work_gym)
    evening = next(s for s in tue["slots"] if s["slot"] == "evening")
    assert evening["available"] is True
    assert evening["location"] == "gym"
    assert evening["gym_id"] == "work_gym"


# ---- Bug E: All-rest override → planner produces zero sessions ----

def test_bug_e_all_rest_produces_no_sessions():
    """Bug E: Override all 7 days to rest → planner must produce 0 sessions
    across the entire week.
    """
    avail = _default_availability()
    override = {
        "days": {
            "monday": {"available": False},
            "tuesday": {"available": False},
            "wednesday": {"available": False},
            "thursday": {"available": False},
            "friday": {"available": False},
            "saturday": {"available": False},
            "sunday": {"available": False},
        },
    }
    effective = merge_override_into_availability(avail, override)

    # Verify all 7 days are unavailable
    for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
        day_data = effective.get(wd, {})
        assert day_data.get("available") is False, f"{wd} should be unavailable"

    profile = {
        "finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
        "technique": 50, "endurance": 40,
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
        gyms=[{"gym_id": "work_gym", "equipment": ["gym_boulder", "board_kilter", "hangboard"]}],
    )

    total_sessions = sum(
        len(day.get("sessions", []))
        for day in plan["weeks"][0]["days"]
    )
    assert total_sessions == 0, f"Expected 0 sessions with all-rest, got {total_sessions}"


# ---- Bug G: Rest-by-default days must have 3 default_slots for restoration ----

def test_bug_g_rest_default_day_has_three_default_slots():
    """Bug G: Days that are rest by default (e.g. sun with {available: False})
    must return 3 default_slots so the frontend can activate them.
    A day absent from availability entirely should also get 3 default_slots
    with available=False as a fallback for the UI.
    """
    avail = _default_availability()
    # sun is {available: False} — rest by default
    view = build_slot_view(avail, None)
    sun = next(d for d in view if d["day"] == "sun")
    assert sun["available"] is False
    assert len(sun["default_slots"]) == 3, (
        f"Expected 3 default_slots for rest-by-default day, got {len(sun['default_slots'])}"
    )
    slot_names = {s["slot"] for s in sun["default_slots"]}
    assert slot_names == {"morning", "lunch", "evening"}


# ---- Bug H: All days must always have 3 slots (morning, lunch, evening) ----

def test_bug_h_all_days_have_three_slots():
    """Bug H: Even if a day only has 'evening' configured in availability,
    build_slot_view must return all 3 slots (morning, lunch, evening).
    Missing slots should be returned as available=False so the user can
    toggle them on in the weekly check-in.
    """
    # Availability with only evening on every day (like user's real data)
    avail = {
        "mon": {"evening": {"available": True, "preferred_location": "gym"}},
        "tue": {"evening": {"available": True, "preferred_location": "gym"}},
        "wed": {"evening": {"available": True, "preferred_location": "gym"}},
        "thu": {"evening": {"available": True, "preferred_location": "home"}},
        "fri": {"evening": {"available": True, "preferred_location": "home"}},
        "sat": {"evening": {"available": True, "preferred_location": "home"}},
        "sun": {"available": False},
    }
    view = build_slot_view(avail, None)

    for day_entry in view:
        if day_entry["day"] == "sun":
            continue  # rest day — slots=[] is ok, covered by default_slots
        assert len(day_entry["slots"]) == 3, (
            f"{day_entry['day']}: expected 3 slots, got {len(day_entry['slots'])}"
        )
        slot_names = {s["slot"] for s in day_entry["slots"]}
        assert slot_names == {"morning", "lunch", "evening"}, (
            f"{day_entry['day']}: missing slots, got {slot_names}"
        )

    # Monday: morning and lunch should be available=False (not configured)
    mon = next(d for d in view if d["day"] == "mon")
    morning = next(s for s in mon["slots"] if s["slot"] == "morning")
    assert morning["available"] is False
    lunch = next(s for s in mon["slots"] if s["slot"] == "lunch")
    assert lunch["available"] is False
    evening = next(s for s in mon["slots"] if s["slot"] == "evening")
    assert evening["available"] is True
