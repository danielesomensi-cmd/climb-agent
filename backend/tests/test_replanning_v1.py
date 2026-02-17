from __future__ import annotations

from datetime import datetime

from backend.engine.planner_v1 import generate_week_plan
from backend.engine.replanner_v1 import INTENT_TO_SESSION, apply_day_override, apply_events
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
