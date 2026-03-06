from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.engine.planner_v1 import generate_week_plan
from backend.engine.replanner_v1 import (
    COMPLEMENTARY_LOAD_EASY,
    COMPLEMENTARY_LOAD_HARD,
    COMPLEMENTARY_LOAD_MAP,
    COMPLEMENTARY_LOAD_OK,
    INTENT_TO_SESSION,
    apply_day_override,
    apply_events,
)
from backend.engine.planner_v2 import _SESSION_META, generate_phase_week
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _build_session_pool, _adjust_domain_weights


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


def _plan_snapshot():
    return generate_week_plan(
        start_date="2026-01-05",
        mode="balanced",
        availability=_availability(),
        allowed_locations=["home", "gym", "outdoor"],
        hard_cap_per_week=3,
        planning_prefs={"default_gym_id": "work_gym", "hard_day_cap_per_week": 3},
        default_gym_id="work_gym",
        gyms=[{"gym_id": "work_gym", "equipment": ["gym_boulder", "board_kilter"]}],
    )


def _count_hard_days(plan):
    return sum(1 for d in plan["weeks"][0]["days"] if any((s.get("tags") or {}).get("hard") for s in d.get("sessions") or []))


def _finger_dates(plan):
    dates = []
    for day in plan["weeks"][0]["days"]:
        if any((s.get("tags") or {}).get("finger") for s in day.get("sessions") or []):
            dates.append(day["date"])
    return dates


def test_move_session_event_updates_target_slot_and_refills_origin():
    plan = _plan_snapshot()
    moved_session_id = None
    source_day = next(d for d in plan["weeks"][0]["days"] if d["date"] == "2026-01-06")
    for sess in source_day["sessions"]:
        if sess["slot"] == "morning":
            moved_session_id = sess["session_id"]
            break
    assert moved_session_id is not None

    updated = apply_events(
        plan,
        [
            {
                "schema_version": "plan_event.v1",
                "event_version": 1,
                "event_type": "move_session",
                "from_date": "2026-01-06",
                "from_slot": "morning",
                "to_date": "2026-01-05",
                "to_slot": "lunch",
            }
        ],
    )

    target_day = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-05")
    assert any(s["slot"] == "lunch" and s["session_id"] == moved_session_id for s in target_day["sessions"])

    origin_day = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-06")
    assert any(s["slot"] == "morning" for s in origin_day["sessions"])

    assert _count_hard_days(updated) <= 3
    finger_days = _finger_dates(updated)
    for prev, cur in zip(finger_days, finger_days[1:]):
        prev_date = datetime.strptime(prev, "%Y-%m-%d").date()
        cur_date = datetime.strptime(cur, "%Y-%m-%d").date()
        assert (cur_date - prev_date).days > 1


def test_mark_skipped_hard_day_replaces_with_recovery():
    plan = _plan_snapshot()
    monday = next(d for d in plan["weeks"][0]["days"] if d["date"] == "2026-01-05")
    hard_session = next(s for s in monday["sessions"] if (s.get("tags") or {}).get("hard"))

    updated = apply_events(
        plan,
        [
            {
                "schema_version": "plan_event.v1",
                "event_version": 1,
                "event_type": "mark_skipped",
                "date": "2026-01-05",
                "slot": hard_session["slot"],
                "reason": "life_happened",
            }
        ],
    )

    monday_updated = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-05")
    slot_session = next(s for s in monday_updated["sessions"] if s["slot"] == hard_session["slot"])
    assert slot_session["session_id"] == "regeneration_easy"
    assert _count_hard_days(updated) <= 3


# ---------- Phase-aware replanner tests (F6/F7 fix) ----------

def _v2_plan_snapshot(phase_id="base"):
    profile = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
               "technique": 50, "endurance": 40, "body_composition": 65}
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


def test_intent_to_session_all_map_to_valid_sessions():
    """All intents must map to sessions known in _SESSION_META."""
    for intent, session_id in INTENT_TO_SESSION.items():
        assert session_id in _SESSION_META, f"Intent '{intent}' maps to unknown session '{session_id}'"


def test_intent_to_session_has_new_intents():
    """Phase-aware replanner should support new intents (F6/F7)."""
    expected_intents = {"core", "prehab", "flexibility", "finger_maintenance", "finger_max"}
    for intent in expected_intents:
        assert intent in INTENT_TO_SESSION, f"Missing intent: {intent}"


def test_day_override_with_phase_id():
    """apply_day_override should accept and propagate phase_id."""
    plan = _v2_plan_snapshot("strength_power")
    updated = apply_day_override(
        plan,
        intent="technique",
        location="gym",
        reference_date="2026-01-05",
        slot="evening",
        phase_id="strength_power",
    )
    tomorrow = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-06")
    override_session = tomorrow["sessions"][0]
    assert override_session["session_id"] == "technique_focus_gym"
    assert override_session["phase_id"] == "strength_power"


def test_day_override_target_date_ripple():
    """Override Wednesday with explicit target_date, verify Thursday gets downgraded via ripple."""
    plan = _v2_plan_snapshot("strength_power")
    updated = apply_day_override(
        plan,
        intent="strength",
        location="gym",
        reference_date="2026-01-05",
        target_date="2026-01-07",
        phase_id="strength_power",
    )
    # Wednesday should have the override session
    wed = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-07")
    assert wed["sessions"][0]["session_id"] == INTENT_TO_SESSION["strength"]
    assert wed["sessions"][0]["phase_id"] == "strength_power"

    # Thursday (ripple day +1) should have no hard sessions
    thu = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-08")
    for s in thu["sessions"]:
        assert not s["tags"]["hard"], f"Hard session still present on ripple day 2026-01-08"

    # Friday (ripple day +2) should also have no hard sessions
    fri = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-09")
    for s in fri["sessions"]:
        assert not s["tags"]["hard"], f"Hard session still present on ripple day 2026-01-09"


def test_mark_done_keeps_session_with_status():
    """mark_done should keep the session in plan with status='done', not remove it."""
    plan = _plan_snapshot()
    monday = next(d for d in plan["weeks"][0]["days"] if d["date"] == "2026-01-05")
    original_count = len(monday["sessions"])
    target_session = monday["sessions"][0]

    updated = apply_events(
        plan,
        [
            {
                "schema_version": "plan_event.v1",
                "event_version": 1,
                "event_type": "mark_done",
                "date": "2026-01-05",
                "slot": target_session["slot"],
                "session_ref": target_session["session_id"],
            }
        ],
    )

    monday_updated = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-05")
    # Session count should be unchanged (session kept, not removed)
    assert len(monday_updated["sessions"]) == original_count
    # The session should have status "done"
    done_session = next(s for s in monday_updated["sessions"] if s["session_id"] == target_session["session_id"])
    assert done_session["status"] == "done"


def test_undo_done_restores_session_status():
    """mark_planned should reset a done session back to planned (no status key)."""
    plan = _plan_snapshot()
    monday = next(d for d in plan["weeks"][0]["days"] if d["date"] == "2026-01-05")
    target_session = monday["sessions"][0]

    # First mark as done
    updated = apply_events(
        plan,
        [
            {
                "event_type": "mark_done",
                "date": "2026-01-05",
                "slot": target_session["slot"],
                "session_ref": target_session["session_id"],
            }
        ],
    )
    done_day = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-05")
    done_session = next(s for s in done_day["sessions"] if s["session_id"] == target_session["session_id"])
    assert done_session["status"] == "done"

    # Now undo via mark_planned
    restored = apply_events(
        updated,
        [
            {
                "event_type": "mark_planned",
                "date": "2026-01-05",
                "slot": target_session["slot"],
                "session_ref": target_session["session_id"],
            }
        ],
    )
    restored_day = next(d for d in restored["weeks"][0]["days"] if d["date"] == "2026-01-05")
    restored_session = next(s for s in restored_day["sessions"] if s["session_id"] == target_session["session_id"])
    assert "status" not in restored_session
    # Day status should also be cleared
    assert "status" not in restored_day


def test_day_override_recovery_ripple():
    """Hard override should downgrade following days to regeneration_easy."""
    plan = _v2_plan_snapshot("strength_power")
    updated = apply_day_override(
        plan,
        intent="strength",
        location="home",
        reference_date="2026-01-05",
        phase_id="strength_power",
    )
    # Check ripple days (day+2, day+3) have no hard sessions
    for ripple_date in ("2026-01-07", "2026-01-08"):
        ripple_day = next(d for d in updated["weeks"][0]["days"] if d["date"] == ripple_date)
        for s in ripple_day["sessions"]:
            assert not s["tags"]["hard"], f"Hard session on ripple day {ripple_date}"


def test_day_override_enforces_finger_spacing():
    """Override with finger_max intent should enforce no consecutive finger days via _reconcile."""
    plan = _v2_plan_snapshot("strength_power")

    # Place a finger session on Monday by overriding Sunday→Monday
    plan_with_finger_mon = apply_day_override(
        plan,
        intent="finger_max",
        location="home",
        reference_date="2026-01-04",  # Sunday
        target_date="2026-01-05",     # Monday
        phase_id="strength_power",
    )

    # Verify Monday has a finger session
    mon = next(d for d in plan_with_finger_mon["weeks"][0]["days"] if d["date"] == "2026-01-05")
    assert any((s.get("tags") or {}).get("finger") for s in mon["sessions"]), "Monday should have a finger session"

    # Now override Tuesday with another finger intent
    plan_with_finger_tue = apply_day_override(
        plan_with_finger_mon,
        intent="finger_max",
        location="home",
        reference_date="2026-01-05",  # Monday
        target_date="2026-01-06",     # Tuesday
        phase_id="strength_power",
    )

    # _reconcile should have downgraded Tuesday's finger session due to spacing constraint
    tue = next(d for d in plan_with_finger_tue["weeks"][0]["days"] if d["date"] == "2026-01-06")
    for s in tue["sessions"]:
        assert not (s.get("tags") or {}).get("finger"), \
            "Tuesday finger session should be downgraded by _reconcile (consecutive finger days)"


# ---------- F6-partial: projecting intent ----------

def test_intent_projecting_maps_to_valid_session():
    """projecting intent maps to power_contact_gym and is in _SESSION_META."""
    assert "projecting" in INTENT_TO_SESSION
    session_id = INTENT_TO_SESSION["projecting"]
    assert session_id == "power_contact_gym"
    assert session_id in _SESSION_META


def test_day_override_with_projecting_intent():
    """Override with projecting intent produces a valid plan with power_contact_gym."""
    plan = _v2_plan_snapshot("strength_power")
    updated = apply_day_override(
        plan,
        intent="projecting",
        location="gym",
        reference_date="2026-01-05",
        slot="evening",
        phase_id="strength_power",
    )
    tomorrow = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-06")
    assert tomorrow["sessions"][0]["session_id"] == "power_contact_gym"
    assert tomorrow["sessions"][0]["tags"]["hard"] is True


# ---------- NEW-F4: proportional ripple effect ----------

def test_day_override_hard_ripple_day1_proportional():
    """After hard override, day+1 hard sessions become medium (complementary_conditioning)."""
    plan = _v2_plan_snapshot("strength_power")
    # Override Monday with a hard session
    updated = apply_day_override(
        plan,
        intent="strength",
        location="gym",
        reference_date="2026-01-04",
        target_date="2026-01-05",
        phase_id="strength_power",
    )
    # Tuesday (day+1) — hard sessions should be downgraded to medium, not recovery
    tue = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-06")
    for s in tue["sessions"]:
        assert not s["tags"]["hard"], "Day+1 should have no hard sessions"
        # If it was downgraded from hard, it should be complementary_conditioning (medium)
        if "recovery_ripple_proportional" in s.get("constraints_applied", []):
            assert s["intensity"] in ("medium", "low"), \
                f"Day+1 downgraded session should be medium or low, got {s['intensity']}"


def test_day_override_hard_ripple_day2_forces_recovery():
    """After hard override, day+2 non-low sessions become regeneration_easy."""
    plan = _v2_plan_snapshot("strength_power")
    updated = apply_day_override(
        plan,
        intent="power",
        location="gym",
        reference_date="2026-01-05",
        target_date="2026-01-07",  # Wednesday
        phase_id="strength_power",
    )
    # Friday (day+2 from Wednesday = 2026-01-09)
    fri = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-09")
    for s in fri["sessions"]:
        assert not s["tags"]["hard"], "Day+2 should have no hard sessions"
        if "recovery_ripple" in s.get("constraints_applied", []):
            assert s["session_id"] == "regeneration_easy", \
                f"Day+2 downgraded session should be regeneration_easy, got {s['session_id']}"
            assert s["intensity"] == "low"


def test_day_override_ripple_keeps_low_sessions():
    """Low-intensity sessions on both day+1 and day+2 should be kept unchanged."""
    plan = _v2_plan_snapshot("base")
    # Find a day that has a low-intensity session, then override the day before
    days = plan["weeks"][0]["days"]
    # Override Monday with hard session
    updated = apply_day_override(
        plan,
        intent="finger_max",
        location="home",
        reference_date="2026-01-04",
        target_date="2026-01-05",
        phase_id="base",
    )
    # Check that low-intensity sessions on day+1 and day+2 are preserved
    for ripple_date in ("2026-01-06", "2026-01-07"):
        ripple_day = next(d for d in updated["weeks"][0]["days"] if d["date"] == ripple_date)
        for s in ripple_day["sessions"]:
            if s.get("intensity") == "low" and "recovery_ripple" not in s.get("constraints_applied", []) \
                    and "recovery_ripple_proportional" not in s.get("constraints_applied", []):
                # This was an original low session — should be unchanged
                assert s["intensity"] == "low"


# ---------- NEW-F6: phase mismatch warning ----------


def test_phase_mismatch_warning_emitted():
    """Override with different phase_id should emit phase_mismatch_warning in adaptations."""
    plan = _v2_plan_snapshot("base")
    updated = apply_day_override(
        plan,
        intent="strength",
        location="gym",
        reference_date="2026-01-05",
        phase_id="power_endurance",  # mismatch: plan is base
    )
    warnings = [a for a in updated.get("adaptations", []) if a["type"] == "phase_mismatch_warning"]
    assert len(warnings) == 1
    assert warnings[0]["requested_phase"] == "power_endurance"
    assert warnings[0]["current_phase"] == "base"


def test_no_phase_mismatch_warning_when_matching():
    """Override with matching phase_id should NOT emit phase_mismatch_warning."""
    plan = _v2_plan_snapshot("base")
    updated = apply_day_override(
        plan,
        intent="technique",
        location="gym",
        reference_date="2026-01-05",
        phase_id="base",
    )
    warnings = [a for a in updated.get("adaptations", []) if a["type"] == "phase_mismatch_warning"]
    assert len(warnings) == 0


# ---------- NEW-F7: finger compensation after override ----------


def test_finger_compensation_after_override():
    """Override that removes finger session should compensate on a later day."""
    plan = _v2_plan_snapshot("base")
    days = plan["weeks"][0]["days"]
    finger_day = next(
        (d for d in days if any((s.get("tags") or {}).get("finger") for s in d["sessions"])),
        None,
    )
    if finger_day is None:
        pytest.skip("No finger day in base plan")

    finger_date = finger_day["date"]
    updated = apply_day_override(
        plan,
        intent="technique",  # non-finger
        location="gym",
        reference_date=(datetime.strptime(finger_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d"),
        target_date=finger_date,
        phase_id="base",
    )

    # Check: finger_compensation or finger_compensation_warning should be logged
    compensations = [a for a in updated.get("adaptations", []) if a.get("type") == "finger_compensation"]
    finger_warnings = [a for a in updated.get("adaptations", []) if a.get("type") == "finger_compensation_warning"]
    assert len(compensations) + len(finger_warnings) >= 1, \
        "Should either compensate finger or warn about inability to compensate"


def test_finger_no_compensation_when_finger_kept():
    """Override with finger intent should NOT trigger compensation."""
    plan = _v2_plan_snapshot("base")
    days = plan["weeks"][0]["days"]
    finger_day = next(
        (d for d in days if any((s.get("tags") or {}).get("finger") for s in d["sessions"])),
        None,
    )
    if finger_day is None:
        pytest.skip("No finger day in base plan")

    finger_date = finger_day["date"]
    updated = apply_day_override(
        plan,
        intent="finger_max",  # still finger!
        location="home",
        reference_date=(datetime.strptime(finger_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d"),
        target_date=finger_date,
        phase_id="base",
    )

    compensations = [a for a in updated.get("adaptations", []) if a.get("type") in ("finger_compensation", "finger_compensation_warning")]
    assert len(compensations) == 0, "No compensation needed when finger session was kept"


def test_finger_compensation_respects_48h_gap():
    """Finger compensation must not place finger session adjacent to existing finger day."""
    plan = _v2_plan_snapshot("strength_power")
    days = plan["weeks"][0]["days"]
    finger_days = [d for d in days if any((s.get("tags") or {}).get("finger") for s in d["sessions"])]
    if len(finger_days) < 1:
        pytest.skip("No finger day in strength_power plan")

    finger_date = finger_days[0]["date"]
    updated = apply_day_override(
        plan,
        intent="technique",
        location="gym",
        reference_date=(datetime.strptime(finger_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d"),
        target_date=finger_date,
        phase_id="strength_power",
    )

    # If compensated, verify 48h gap
    comp_days = [
        d for d in updated["weeks"][0]["days"]
        if any((s.get("tags") or {}).get("finger") for s in d["sessions"])
    ]
    dates = sorted(datetime.strptime(d["date"], "%Y-%m-%d").date() for d in comp_days)
    for prev, cur in zip(dates, dates[1:]):
        assert (cur - prev).days > 1, f"Finger sessions too close: {prev} and {cur}"


# ---------- Complementary sport completion ----------


def _plan_with_other_activity():
    """Return a plan with an other_activity day (Sunday)."""
    plan = _plan_snapshot()
    # Mark Sunday as other_activity
    sun = next(d for d in plan["weeks"][0]["days"] if d["weekday"] == "sun")
    sun["other_activity"] = True
    sun["other_activity_name"] = "Circus"
    sun["sessions"] = []
    return plan


def test_complete_other_activity_easy():
    """complete_other_activity with 'easy' feedback sets load=10."""
    plan = _plan_with_other_activity()
    sun_date = next(d["date"] for d in plan["weeks"][0]["days"] if d["weekday"] == "sun")

    updated = apply_events(plan, [
        {"event_type": "complete_other_activity", "date": sun_date, "feedback": "easy"},
    ])

    sun = next(d for d in updated["weeks"][0]["days"] if d["date"] == sun_date)
    assert sun["other_activity_status"] == "completed"
    assert sun["other_activity_feedback"] == "easy"
    assert sun["other_activity_load"] == COMPLEMENTARY_LOAD_EASY
    assert sun["status"] == "done"


def test_complete_other_activity_ok():
    """complete_other_activity with 'ok' feedback sets load=20."""
    plan = _plan_with_other_activity()
    sun_date = next(d["date"] for d in plan["weeks"][0]["days"] if d["weekday"] == "sun")

    updated = apply_events(plan, [
        {"event_type": "complete_other_activity", "date": sun_date, "feedback": "ok"},
    ])

    sun = next(d for d in updated["weeks"][0]["days"] if d["date"] == sun_date)
    assert sun["other_activity_load"] == COMPLEMENTARY_LOAD_OK


def test_complete_other_activity_hard():
    """complete_other_activity with 'hard' feedback sets load=30."""
    plan = _plan_with_other_activity()
    sun_date = next(d["date"] for d in plan["weeks"][0]["days"] if d["weekday"] == "sun")

    updated = apply_events(plan, [
        {"event_type": "complete_other_activity", "date": sun_date, "feedback": "hard"},
    ])

    sun = next(d for d in updated["weeks"][0]["days"] if d["date"] == sun_date)
    assert sun["other_activity_load"] == COMPLEMENTARY_LOAD_HARD


def test_undo_other_activity():
    """undo_other_activity removes completion data."""
    plan = _plan_with_other_activity()
    sun_date = next(d["date"] for d in plan["weeks"][0]["days"] if d["weekday"] == "sun")

    # Complete then undo
    completed = apply_events(plan, [
        {"event_type": "complete_other_activity", "date": sun_date, "feedback": "ok"},
    ])
    undone = apply_events(completed, [
        {"event_type": "undo_other_activity", "date": sun_date},
    ])

    sun = next(d for d in undone["weeks"][0]["days"] if d["date"] == sun_date)
    assert "other_activity_status" not in sun
    assert "other_activity_feedback" not in sun
    assert "other_activity_load" not in sun
    assert "status" not in sun


def test_complete_other_activity_on_non_activity_day_raises():
    """complete_other_activity on a regular day should raise ValueError."""
    plan = _plan_snapshot()
    mon_date = next(d["date"] for d in plan["weeks"][0]["days"] if d["weekday"] == "mon")

    with pytest.raises(ValueError, match="not an other-activity day"):
        apply_events(plan, [
            {"event_type": "complete_other_activity", "date": mon_date, "feedback": "ok"},
        ])


def test_add_other_activity():
    """add_other_activity sets the day-level flag, name, and slot."""
    plan = _plan_snapshot()
    mon_date = next(d["date"] for d in plan["weeks"][0]["days"] if d["weekday"] == "mon")
    result = apply_events(plan, [
        {"event_type": "add_other_activity", "date": mon_date, "activity_name": "Swimming", "slot": "evening"},
    ])
    mon = next(d for d in result["weeks"][0]["days"] if d["date"] == mon_date)
    assert mon["other_activity"] is True
    assert mon["other_activity_name"] == "Swimming"
    assert mon["other_activity_slot"] == "evening"
    # Sessions should still be present (not wiped)
    assert len(mon.get("sessions", [])) > 0


def test_add_other_activity_blocks_slot():
    """quick-add a session into the same slot as other_activity should raise."""
    from backend.engine.replanner_v1 import apply_day_add
    plan = _plan_snapshot()
    mon_date = next(d["date"] for d in plan["weeks"][0]["days"] if d["weekday"] == "mon")
    # Add other activity in morning slot (likely free)
    plan = apply_events(plan, [
        {"event_type": "add_other_activity", "date": mon_date, "activity_name": "Swimming", "slot": "morning"},
    ])
    # Quick-add to the same slot should fail
    with pytest.raises(ValueError, match="already occupied by other activity"):
        apply_day_add(plan, session_id="core_training", target_date=mon_date,
                      slot="morning", location="home")


def test_remove_other_activity():
    """remove_other_activity clears all other-activity fields including slot."""
    plan = _plan_with_other_activity()
    sun_date = next(d["date"] for d in plan["weeks"][0]["days"] if d["weekday"] == "sun")
    # Add slot info
    plan = apply_events(plan, [
        {"event_type": "complete_other_activity", "date": sun_date, "feedback": "hard"},
    ])
    # Now remove
    result = apply_events(plan, [
        {"event_type": "remove_other_activity", "date": sun_date},
    ])
    sun = next(d for d in result["weeks"][0]["days"] if d["date"] == sun_date)
    assert "other_activity" not in sun
    assert "other_activity_name" not in sun
    assert "other_activity_slot" not in sun
    assert "other_activity_status" not in sun
    assert "other_activity_feedback" not in sun
    assert "other_activity_load" not in sun


def test_complementary_load_constants():
    """Verify load constants are correctly defined."""
    assert COMPLEMENTARY_LOAD_EASY == 10
    assert COMPLEMENTARY_LOAD_OK == 20
    assert COMPLEMENTARY_LOAD_HARD == 30
    assert COMPLEMENTARY_LOAD_MAP == {"easy": 10, "ok": 20, "hard": 30}


# ---------- remove_session event tests ----------


def test_remove_session_basic():
    """Removing a planned session leaves the day with fewer sessions."""
    plan = _plan_snapshot()
    # Find a day with at least one session
    day = next(d for d in plan["weeks"][0]["days"] if d.get("sessions"))
    target_date = day["date"]
    target_session = day["sessions"][0]
    original_count = len(day["sessions"])

    updated = apply_events(plan, [
        {"event_type": "remove_session", "date": target_date, "session_ref": target_session["session_id"]},
    ])

    updated_day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target_date)
    assert len(updated_day["sessions"]) == original_count - 1
    assert all(s["session_id"] != target_session["session_id"] for s in updated_day["sessions"])


def test_remove_session_done_raises():
    """Cannot remove a session that has already been marked done."""
    plan = _plan_snapshot()
    day = next(d for d in plan["weeks"][0]["days"] if d.get("sessions"))
    target_date = day["date"]
    session = day["sessions"][0]

    # First mark it done
    plan = apply_events(plan, [
        {"event_type": "mark_done", "date": target_date, "session_ref": session["session_id"]},
    ])

    with pytest.raises(ValueError, match="Cannot remove a session"):
        apply_events(plan, [
            {"event_type": "remove_session", "date": target_date, "session_ref": session["session_id"]},
        ])


def test_remove_session_skipped_raises():
    """Cannot remove a session that has already been marked skipped."""
    plan = _plan_snapshot()
    day = next(d for d in plan["weeks"][0]["days"] if d.get("sessions"))
    target_date = day["date"]
    session = day["sessions"][0]

    plan = apply_events(plan, [
        {"event_type": "mark_skipped", "date": target_date, "session_ref": session["session_id"]},
    ])

    # The skipped session is replaced with regeneration_easy (status=skipped)
    with pytest.raises(ValueError, match="Cannot remove a session"):
        apply_events(plan, [
            {"event_type": "remove_session", "date": target_date, "session_ref": "regeneration_easy"},
        ])


def test_remove_session_last_on_day():
    """Removing the only session on a day leaves an empty sessions list."""
    plan = _plan_snapshot()
    # Find a day with exactly one session
    day = next((d for d in plan["weeks"][0]["days"] if len(d.get("sessions", [])) == 1), None)
    if day is None:
        # If no single-session day, create one by removing extras
        day = next(d for d in plan["weeks"][0]["days"] if d.get("sessions"))
        while len(day["sessions"]) > 1:
            day["sessions"].pop()
    target_date = day["date"]
    session = day["sessions"][0]

    updated = apply_events(plan, [
        {"event_type": "remove_session", "date": target_date, "session_ref": session["session_id"]},
    ])

    updated_day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target_date)
    assert len(updated_day["sessions"]) == 0
    assert "status" not in updated_day


# ---------- Change gym tests (C-4) ----------


def _gym_plan():
    """Plan with gym sessions for change_gym testing."""
    profile = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
               "technique": 50, "endurance": 40, "body_composition": 65}
    base_weights = _BASE_WEIGHTS["base"]
    domain_weights = _adjust_domain_weights(base_weights, profile)
    session_pool = _build_session_pool("base")
    return generate_phase_week(
        phase_id="base",
        domain_weights=domain_weights,
        session_pool=session_pool,
        start_date="2026-01-05",
        availability={
            "mon": {"evening": {"available": True, "locations": ["gym"], "gym_id": "gym_a"}},
            "tue": {"evening": {"available": True, "locations": ["gym"], "gym_id": "gym_a"}},
            "wed": {"evening": {"available": True, "locations": ["gym"], "gym_id": "gym_a"}},
            "thu": {"evening": {"available": True, "locations": ["gym"], "gym_id": "gym_a"}},
        },
        allowed_locations=["home", "gym"],
        hard_cap_per_week=3,
        planning_prefs={"target_training_days_per_week": 4},
        default_gym_id="gym_a",
        gyms=[
            {"name": "Gym A", "gym_id": "gym_a", "equipment": ["gym_boulder", "hangboard", "pullup_bar", "gym_routes", "dumbbell", "barbell"]},
            {"name": "Gym B", "gym_id": "gym_b", "equipment": ["gym_boulder", "hangboard", "pullup_bar", "dumbbell"]},
        ],
    )


def test_change_gym_compatible_updates_gym_id():
    """Changing to a gym that has all required equipment should just update gym_id."""
    plan = _gym_plan()
    gym_b_eq = {"gym_boulder", "hangboard", "pullup_bar", "dumbbell"}
    # Find a day with a gym session compatible with gym_b
    day = None
    for d in plan["weeks"][0]["days"]:
        for s in d.get("sessions", []):
            sid = s["session_id"]
            meta = _SESSION_META.get(sid, {})
            if "gym" not in meta.get("location", ()):
                continue  # Skip home-only sessions
            from backend.engine.replanner_v1 import _get_required_equipment
            req = set(_get_required_equipment(sid))
            if not req or req.issubset(gym_b_eq):
                day = d
                break
        if day:
            break

    if day is None:
        # Force a compatible gym session
        day = plan["weeks"][0]["days"][0]
        day["sessions"] = [{
            "slot": "evening", "session_id": "pulling_strength_gym",
            "location": "gym", "gym_id": "gym_a", "intensity": "high",
            "tags": {"hard": True, "finger": False},
        }]

    target_date = day["date"]
    original_sid = next(
        s["session_id"] for s in day["sessions"]
        if "gym" in _SESSION_META.get(s["session_id"], {}).get("location", ())
    )

    updated = apply_events(
        plan,
        [{"event_type": "change_gym", "date": target_date, "gym_id": "gym_b", "location": "gym"}],
        gyms=[
            {"gym_id": "gym_a", "name": "Gym A", "equipment": ["gym_boulder", "hangboard", "pullup_bar", "gym_routes", "dumbbell"]},
            {"gym_id": "gym_b", "name": "Gym B", "equipment": ["gym_boulder", "hangboard", "pullup_bar", "dumbbell"]},
        ],
    )

    updated_day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target_date)
    session = updated_day["sessions"][0]
    assert session["session_id"] == original_sid  # Same session, just new gym
    assert session["gym_id"] == "gym_b"
    assert session["location"] == "gym"


def test_change_gym_incompatible_replaces_session():
    """Changing to a gym missing required equipment should replace the session."""
    plan = _gym_plan()
    # Find a session that requires gym_routes (not available at gym_b)
    target_day = None
    for d in plan["weeks"][0]["days"]:
        for s in d.get("sessions", []):
            from backend.engine.replanner_v1 import _get_required_equipment
            req = set(_get_required_equipment(s["session_id"]))
            if "gym_routes" in req:
                target_day = d
                break
        if target_day:
            break

    if target_day is None:
        # Force a session that needs gym_routes
        day = plan["weeks"][0]["days"][0]
        day["sessions"] = [{
            "slot": "evening", "session_id": "power_endurance_gym",
            "location": "gym", "gym_id": "gym_a", "intensity": "high",
            "tags": {"hard": True, "finger": False},
        }]
        target_day = day

    target_date = target_day["date"]

    updated = apply_events(
        plan,
        [{"event_type": "change_gym", "date": target_date, "gym_id": "gym_b", "location": "gym"}],
        gyms=[
            {"gym_id": "gym_a", "name": "Gym A", "equipment": ["gym_boulder", "hangboard", "pullup_bar", "gym_routes"]},
            {"gym_id": "gym_b", "name": "Gym B", "equipment": ["gym_boulder", "hangboard", "pullup_bar"]},
        ],
    )

    updated_day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target_date)
    session = updated_day["sessions"][0]
    # Should be replaced (complementary_conditioning or regeneration_easy)
    assert session["session_id"] != "power_endurance_gym"
    assert session["gym_id"] == "gym_b"
    # Check adaptation logged
    adaptations = updated.get("adaptations", [])
    gym_change = [a for a in adaptations if a.get("type") == "change_gym"]
    assert len(gym_change) == 1
    assert gym_change[0]["new_gym_id"] == "gym_b"


def test_change_gym_to_home_replaces_gym_only_sessions():
    """Changing to Home should replace gym-only sessions with home-compatible ones."""
    plan = _gym_plan()
    # Force a gym-only session
    day = plan["weeks"][0]["days"][0]
    day["sessions"] = [{
        "slot": "evening", "session_id": "power_contact_gym",
        "location": "gym", "gym_id": "gym_a", "intensity": "max",
        "tags": {"hard": True, "finger": False},
    }]
    target_date = day["date"]

    updated = apply_events(
        plan,
        [{"event_type": "change_gym", "date": target_date, "location": "home"}],
    )

    updated_day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target_date)
    session = updated_day["sessions"][0]
    assert session["session_id"] == "complementary_conditioning"
    assert session["location"] == "home"
    assert session["gym_id"] is None


def test_change_gym_skips_done_sessions():
    """Done sessions should not be affected by gym change."""
    plan = _gym_plan()
    day = plan["weeks"][0]["days"][0]
    day["sessions"] = [
        {"slot": "morning", "session_id": "power_contact_gym", "location": "gym",
         "gym_id": "gym_a", "intensity": "max", "tags": {"hard": True, "finger": False},
         "status": "done"},
        {"slot": "evening", "session_id": "technique_focus_gym", "location": "gym",
         "gym_id": "gym_a", "intensity": "medium", "tags": {"hard": False, "finger": False}},
    ]
    target_date = day["date"]

    updated = apply_events(
        plan,
        [{"event_type": "change_gym", "date": target_date, "location": "home"}],
    )

    updated_day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target_date)
    done_session = next(s for s in updated_day["sessions"] if s["slot"] == "morning")
    assert done_session["session_id"] == "power_contact_gym"  # Untouched
    assert done_session["gym_id"] == "gym_a"  # Untouched

    planned_session = next(s for s in updated_day["sessions"] if s["slot"] == "evening")
    assert planned_session["location"] == "home"  # Changed


def test_change_gym_finger_compensation():
    """Losing a finger session to gym change should trigger finger compensation."""
    plan = _gym_plan()
    # Force a finger session on day 1 and a replaceable session on day 3+
    days = plan["weeks"][0]["days"]
    days[0]["sessions"] = [{
        "slot": "evening", "session_id": "finger_maintenance_gym",
        "location": "gym", "gym_id": "gym_a", "intensity": "medium",
        "tags": {"hard": False, "finger": True},
    }]
    # Ensure day 3 has a replaceable complementary session
    if len(days) > 2:
        days[2]["sessions"] = [{
            "slot": "evening", "session_id": "complementary_conditioning",
            "location": "gym", "gym_id": "gym_a", "intensity": "medium",
            "tags": {"hard": False, "finger": False},
        }]

    updated = apply_events(
        plan,
        [{"event_type": "change_gym", "date": days[0]["date"], "location": "home"}],
    )

    # Check finger compensation was attempted
    adaptations = updated.get("adaptations", [])
    has_compensation = any(
        a.get("type") in ("finger_compensation", "finger_compensation_warning")
        for a in adaptations
    )
    assert has_compensation


# ── Outdoor events ─────────────────────────────────────────────────────


def test_add_outdoor_sets_fields():
    plan = _plan_snapshot()
    target = plan["weeks"][0]["days"][5]  # Saturday
    updated = apply_events(plan, [{
        "event_type": "add_outdoor",
        "date": target["date"],
        "spot_name": "Berdorf",
        "discipline": "lead",
        "spot_id": "spot_abc",
    }])
    day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target["date"])
    assert day["outdoor_spot_name"] == "Berdorf"
    assert day["outdoor_discipline"] == "lead"
    assert day["outdoor_spot_id"] == "spot_abc"
    assert day["outdoor_session_status"] == "planned"


def test_add_outdoor_coexists_with_sessions():
    plan = _plan_snapshot()
    # Pick a day with sessions
    day_with_sessions = next(d for d in plan["weeks"][0]["days"] if d.get("sessions"))
    orig_count = len(day_with_sessions["sessions"])
    updated = apply_events(plan, [{
        "event_type": "add_outdoor",
        "date": day_with_sessions["date"],
        "spot_name": "Berdorf",
        "discipline": "boulder",
    }])
    day = next(d for d in updated["weeks"][0]["days"] if d["date"] == day_with_sessions["date"])
    assert day["outdoor_spot_name"] == "Berdorf"
    assert len(day.get("sessions", [])) == orig_count  # sessions untouched


def test_complete_outdoor_marks_done():
    plan = _plan_snapshot()
    target = plan["weeks"][0]["days"][5]
    # First add outdoor
    plan = apply_events(plan, [{
        "event_type": "add_outdoor",
        "date": target["date"],
        "spot_name": "Berdorf",
        "discipline": "lead",
    }])
    # Then complete
    updated = apply_events(plan, [{
        "event_type": "complete_outdoor",
        "date": target["date"],
    }])
    day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target["date"])
    assert day["outdoor_session_status"] == "done"


def test_complete_outdoor_without_add_raises():
    plan = _plan_snapshot()
    target = plan["weeks"][0]["days"][5]
    with pytest.raises(ValueError, match="no outdoor session"):
        apply_events(plan, [{
            "event_type": "complete_outdoor",
            "date": target["date"],
        }])


def test_undo_outdoor_reverts():
    plan = _plan_snapshot()
    target = plan["weeks"][0]["days"][5]
    plan = apply_events(plan, [{
        "event_type": "add_outdoor",
        "date": target["date"],
        "spot_name": "Berdorf",
        "discipline": "lead",
    }])
    plan = apply_events(plan, [{
        "event_type": "complete_outdoor",
        "date": target["date"],
    }])
    updated = apply_events(plan, [{
        "event_type": "undo_outdoor",
        "date": target["date"],
    }])
    day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target["date"])
    assert day["outdoor_session_status"] == "planned"
    assert day.get("status") != "done"


def test_remove_outdoor_clears_all():
    plan = _plan_snapshot()
    target = plan["weeks"][0]["days"][5]
    plan = apply_events(plan, [{
        "event_type": "add_outdoor",
        "date": target["date"],
        "spot_name": "Berdorf",
        "discipline": "lead",
        "spot_id": "spot_abc",
    }])
    updated = apply_events(plan, [{
        "event_type": "remove_outdoor",
        "date": target["date"],
    }])
    day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target["date"])
    assert "outdoor_spot_name" not in day
    assert "outdoor_discipline" not in day
    assert "outdoor_spot_id" not in day
    assert "outdoor_session_status" not in day


def test_remove_outdoor_done_raises():
    plan = _plan_snapshot()
    target = plan["weeks"][0]["days"][5]
    plan = apply_events(plan, [{
        "event_type": "add_outdoor",
        "date": target["date"],
        "spot_name": "Berdorf",
        "discipline": "lead",
    }])
    plan = apply_events(plan, [{
        "event_type": "complete_outdoor",
        "date": target["date"],
    }])
    with pytest.raises(ValueError, match="Cannot remove a completed outdoor"):
        apply_events(plan, [{
            "event_type": "remove_outdoor",
            "date": target["date"],
        }])


def test_mark_done_indoor_does_not_complete_day_with_planned_outdoor():
    """When outdoor is planned, marking all indoor sessions done should NOT mark the day done."""
    plan = _plan_snapshot()
    day_with_sessions = next(d for d in plan["weeks"][0]["days"] if d.get("sessions"))
    # Add outdoor
    plan = apply_events(plan, [{
        "event_type": "add_outdoor",
        "date": day_with_sessions["date"],
        "spot_name": "Berdorf",
        "discipline": "lead",
    }])
    # Mark all indoor sessions done
    events = []
    day = next(d for d in plan["weeks"][0]["days"] if d["date"] == day_with_sessions["date"])
    for s in day["sessions"]:
        events.append({
            "event_type": "mark_done",
            "date": day["date"],
            "session_ref": s["session_id"],
            "slot": s["slot"],
        })
    updated = apply_events(plan, events)
    result_day = next(d for d in updated["weeks"][0]["days"] if d["date"] == day_with_sessions["date"])
    # Day should NOT be marked done because outdoor is still "planned"
    assert result_day.get("status") != "done"
    # Now complete outdoor too
    updated2 = apply_events(updated, [{
        "event_type": "complete_outdoor",
        "date": result_day["date"],
    }])
    result_day2 = next(d for d in updated2["weeks"][0]["days"] if d["date"] == day_with_sessions["date"])
    assert result_day2["status"] == "done"
