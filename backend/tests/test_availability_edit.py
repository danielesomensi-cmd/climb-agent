"""Tests for B20 — Edit Availability (regenerate_preserving_completed)."""

from __future__ import annotations

from copy import deepcopy

from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _build_session_pool, _adjust_domain_weights
from backend.engine.planner_v2 import generate_phase_week
from backend.engine.replanner_v1 import regenerate_preserving_completed


def _availability():
    return {
        "mon": {
            "morning": {"available": True, "locations": ["home"]},
            "lunch": {"available": True, "locations": ["gym"], "gym_id": "work_gym"},
            "evening": {"available": True, "locations": ["gym"], "gym_id": "work_gym"},
        },
        "tue": {
            "morning": {"available": True, "locations": ["gym"], "gym_id": "work_gym"},
            "lunch": {"available": True, "locations": ["home"]},
            "evening": {"available": True, "locations": ["gym"], "gym_id": "work_gym"},
        },
        "wed": {"evening": {"available": True, "locations": ["gym"], "gym_id": "work_gym"}},
        "thu": {"lunch": {"available": True, "locations": ["home"]}},
        "fri": {"evening": {"available": True, "locations": ["gym"], "gym_id": "work_gym"}},
        "sat": {"morning": {"available": True, "locations": ["outdoor", "gym"], "gym_id": "work_gym"}},
        "sun": {"available": False},
    }


def _make_plan(phase_id="base"):
    profile = {
        "finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
        "technique": 50, "endurance": 40, "body_composition": 65,
    }
    base_weights = _BASE_WEIGHTS[phase_id]
    domain_weights = _adjust_domain_weights(base_weights, profile)
    session_pool = _build_session_pool(phase_id)
    return generate_phase_week(
        phase_id=phase_id,
        domain_weights=domain_weights,
        session_pool=session_pool,
        start_date="2026-01-05",
        availability=_availability(),
        allowed_locations=["home", "gym"],
        hard_cap_per_week=3,
        planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
        default_gym_id="work_gym",
        gyms=[{"gym_id": "work_gym", "equipment": ["gym_boulder", "board_kilter"]}],
    )


def test_preserves_done_sessions():
    """A session marked done in the old plan should appear in the result."""
    old_plan = _make_plan()
    new_plan = _make_plan()

    # Mark a session as done in old_plan
    day = old_plan["weeks"][0]["days"][0]
    if day["sessions"]:
        day["sessions"][0]["status"] = "done"

    result = regenerate_preserving_completed(old_plan, new_plan)
    result_day = result["weeks"][0]["days"][0]
    done_sessions = [s for s in result_day["sessions"] if s.get("status") == "done"]
    assert len(done_sessions) >= 1, "Done session should be preserved"


def test_preserves_skipped_sessions():
    """A session marked skipped in the old plan should appear in the result."""
    old_plan = _make_plan()
    new_plan = _make_plan()

    # Mark a session as skipped in old_plan
    day = old_plan["weeks"][0]["days"][0]
    if day["sessions"]:
        day["sessions"][0]["status"] = "skipped"

    result = regenerate_preserving_completed(old_plan, new_plan)
    result_day = result["weeks"][0]["days"][0]
    skipped = [s for s in result_day["sessions"] if s.get("status") == "skipped"]
    assert len(skipped) >= 1, "Skipped session should be preserved"


def test_replaces_slot_conflict():
    """A completed session should replace auto-generated one in the same slot."""
    old_plan = _make_plan()
    new_plan = _make_plan()

    # Mark first session as done in old_plan
    day = old_plan["weeks"][0]["days"][0]
    if not day["sessions"]:
        return
    done_session = day["sessions"][0]
    done_session["status"] = "done"
    done_slot = done_session["slot"]
    done_sid = done_session["session_id"]

    result = regenerate_preserving_completed(old_plan, new_plan)
    result_day = result["weeks"][0]["days"][0]

    # The slot should contain the done session, not the auto-generated one
    slot_sessions = [s for s in result_day["sessions"] if s["slot"] == done_slot]
    assert len(slot_sessions) == 1, "Should have exactly one session per slot"
    assert slot_sessions[0]["status"] == "done"
    assert slot_sessions[0]["session_id"] == done_sid


def test_no_completed_returns_new_unchanged():
    """Without any completed sessions, result should equal new_plan (plus revision bump)."""
    old_plan = _make_plan()
    new_plan = _make_plan()

    result = regenerate_preserving_completed(old_plan, new_plan)

    # The plans should be structurally identical except for plan_revision
    for i, day in enumerate(result["weeks"][0]["days"]):
        new_day = new_plan["weeks"][0]["days"][i]
        assert day["date"] == new_day["date"]
        assert len(day["sessions"]) == len(new_day["sessions"])
        for j, s in enumerate(day["sessions"]):
            assert s["session_id"] == new_day["sessions"][j]["session_id"]

    # plan_revision should be bumped
    new_rev = new_plan.get("plan_revision") or 1
    assert result["plan_revision"] == new_rev + 1
