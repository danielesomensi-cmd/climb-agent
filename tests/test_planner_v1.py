import re
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


from catalog.engine.planner_v1 import generate_week_plan
from catalog.engine.replanner_v1 import apply_day_override


def _availability():
    return {
        "mon": {"evening": {"available": True, "locations": ["gym"]}},
        "tue": {"evening": {"available": True, "locations": ["gym", "home"]}},
        "wed": {"evening": {"available": True, "locations": ["gym"]}},
        "thu": {"morning": {"available": True, "locations": ["home"]}},
        "fri": {"evening": {"available": True, "locations": ["gym"]}},
        "sat": {"morning": {"available": True, "locations": ["outdoor", "gym"]}},
        "sun": {"available": False},
    }


def test_planner_is_deterministic():
    kwargs = dict(
        start_date="2026-01-05",
        mode="balanced",
        availability=_availability(),
        allowed_locations=["home", "gym", "outdoor"],
        default_gym_id="work_gym",
    )
    plan_a = generate_week_plan(**kwargs)
    plan_b = generate_week_plan(**kwargs)
    assert plan_a["weeks"][0]["days"] == plan_b["weeks"][0]["days"]


def test_planner_respects_hard_and_finger_constraints():
    plan = generate_week_plan(
        start_date="2026-01-05",
        mode="strength",
        availability=_availability(),
        allowed_locations=["home", "gym", "outdoor"],
        hard_cap_per_week=3,
        default_gym_id="work_gym",
    )
    days = plan["weeks"][0]["days"]
    hard_days = []
    finger_days = []

    for day in days:
        has_hard = any(s["tags"]["hard"] for s in day["sessions"])
        has_finger = any(s["tags"]["finger"] for s in day["sessions"])
        if has_hard:
            hard_days.append(day["date"])
        if has_finger:
            finger_days.append(day["date"])

    assert len(hard_days) <= 3
    for prev, cur in zip(finger_days, finger_days[1:]):
        prev_date = datetime.strptime(prev, "%Y-%m-%d").date()
        cur_date = datetime.strptime(cur, "%Y-%m-%d").date()
        assert (cur_date - prev_date).days > 1


def test_replanner_override_updates_tomorrow_and_ripple():
    plan = generate_week_plan(
        start_date="2026-01-05",
        mode="balanced",
        availability=_availability(),
        allowed_locations=["home", "gym", "outdoor"],
        default_gym_id="work_gym",
    )
    updated = apply_day_override(
        plan,
        intent="strength",
        location="gym",
        reference_date="2026-01-05",
    )

    tomorrow = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-06")
    assert tomorrow["sessions"][0]["session_id"] == "strength_long"

    day2 = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-07")
    day3 = next(d for d in updated["weeks"][0]["days"] if d["date"] == "2026-01-08")
    for day in (day2, day3):
        assert all(not s["tags"]["hard"] for s in day["sessions"])


def test_plan_week_uses_user_state_availability_and_default_gym_id(tmp_path: Path):
    user_state = {
        "availability": {
            "mon": {
                "lunch": {
                    "available": True,
                    "locations": ["gym", "home"],
                    "preferred_location": "gym",
                    "gym_id": "work_gym",
                },
                "evening": {"available": False},
                "morning": {"available": False},
            }
        },
        "planning_prefs": {"hard_day_cap_per_week": 3, "default_gym_id": "blocx"},
        "equipment": {"gyms": [{"gym_id": "work_gym"}, {"gym_id": "blocx"}]},
    }
    us_path = tmp_path / "user_state.json"
    out_path = tmp_path / "plan.json"
    us_path.write_text(json.dumps(user_state), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/plan_week.py",
            "--start-date",
            "2026-01-05",
            "--mode",
            "balanced",
            "--user-state",
            str(us_path),
            "--out",
            str(out_path),
        ],
        check=True,
    )

    plan = json.loads(out_path.read_text(encoding="utf-8"))
    monday = next(day for day in plan["weeks"][0]["days"] if day["date"] == "2026-01-05")
    assert monday["sessions"][0]["slot"] == "lunch"
    assert monday["sessions"][0]["location"] == "gym"
    assert monday["sessions"][0]["gym_id"] == "work_gym"


def test_no_planned_gym_session_has_null_gym_id_and_no_gym_prefixed_session_id():
    plan = generate_week_plan(
        start_date="2026-01-05",
        mode="balanced",
        availability=_availability(),
        allowed_locations=["home", "gym", "outdoor"],
        default_gym_id="work_gym",
    )

    for day in plan["weeks"][0]["days"]:
        for session in day["sessions"]:
            if session["location"] == "gym":
                assert session.get("gym_id") is not None
            assert not re.match(r"^(blocx|bkl|arlon|coque)_", session["session_id"])


def test_test_queue_inserts_test_max_hang_session_with_constraints():
    plan = generate_week_plan(
        start_date="2026-01-05",
        mode="balanced",
        availability=_availability(),
        allowed_locations=["home", "gym", "outdoor"],
        hard_cap_per_week=3,
        default_gym_id="work_gym",
        test_queue=[
            {
                "test_id": "max_hang_5s_total_load",
                "recommended_by_date": "2026-01-08",
                "reason": "two_recent_hard_feedback_on_max_hang_5s",
                "created_at": "2026-01-06",
            }
        ],
    )

    days = plan["weeks"][0]["days"]
    inserted = [
        (day["date"], session)
        for day in days
        for session in day["sessions"]
        if session["session_id"] == "test_max_hang_5s"
    ]
    assert len(inserted) == 1
    test_date, test_session = inserted[0]
    assert test_session["slot"] == "morning"
    assert test_session["tags"]["test"] is True
    assert test_session["test_id"] == "max_hang_5s_total_load"

    hard_days = [day for day in days if any(s["tags"]["hard"] for s in day["sessions"])]
    assert len(hard_days) <= 3

    finger_days = [day["date"] for day in days if any(s["tags"]["finger"] for s in day["sessions"])]
    for prev, cur in zip(finger_days, finger_days[1:]):
        prev_date = datetime.strptime(prev, "%Y-%m-%d").date()
        cur_date = datetime.strptime(cur, "%Y-%m-%d").date()
        assert (cur_date - prev_date).days > 1


def test_availability_slot_gym_id_override_is_always_used():
    availability = {
        "mon": {"evening": {"available": True, "locations": ["gym"], "gym_id": "tiny_gym"}},
        "tue": {"evening": {"available": False}},
        "wed": {"evening": {"available": False}},
        "thu": {"morning": {"available": False}},
        "fri": {"evening": {"available": False}},
        "sat": {"morning": {"available": False}},
        "sun": {"available": False},
    }
    plan = generate_week_plan(
        start_date="2026-01-05",
        mode="balanced",
        availability=availability,
        allowed_locations=["home", "gym", "outdoor"],
        default_gym_id="coque",
        gyms=[
            {"gym_id": "tiny_gym", "equipment": ["weight"], "priority": 9},
            {"gym_id": "coque", "equipment": ["gym_routes", "gym_boulder"], "priority": 1},
        ],
    )
    monday = next(day for day in plan["weeks"][0]["days"] if day["date"] == "2026-01-05")
    evening_sessions = [s for s in monday["sessions"] if s["location"] == "gym" and s["slot"] == "evening"]
    assert evening_sessions
    assert all(s["gym_id"] == "tiny_gym" for s in evening_sessions)


def test_session_requiring_gym_routes_skips_gyms_without_routes():
    availability = _availability()
    availability["wed"] = {"evening": {"available": True, "locations": ["gym"]}}
    plan = generate_week_plan(
        start_date="2026-01-05",
        mode="balanced",
        availability=availability,
        allowed_locations=["home", "gym", "outdoor"],
        gyms=[
            {"gym_id": "bkl", "equipment": ["gym_boulder", "spraywall"], "priority": 1},
            {"gym_id": "coque", "equipment": ["gym_routes", "gym_boulder"], "priority": 2},
            {"gym_id": "blocx", "equipment": ["gym_boulder"], "priority": 3},
        ],
    )
    sessions = [
        s
        for day in plan["weeks"][0]["days"]
        for s in day["sessions"]
        if s["session_id"] == "gym_power_endurance"
    ]
    assert sessions
    assert all(s["gym_id"] == "coque" for s in sessions)


def test_gym_selection_tie_breaks_by_gym_id_on_equal_priority():
    availability = _availability()
    availability["mon"]["evening"].pop("gym_id", None)
    plan = generate_week_plan(
        start_date="2026-01-05",
        mode="balanced",
        availability=availability,
        allowed_locations=["home", "gym", "outdoor"],
        gyms=[
            {"gym_id": "zeta", "equipment": ["gym_boulder"], "priority": 1},
            {"gym_id": "alpha", "equipment": ["gym_boulder"], "priority": 1},
            {"gym_id": "coque", "equipment": ["gym_routes", "gym_boulder"], "priority": 2},
        ],
    )
    boulder = [
        s
        for day in plan["weeks"][0]["days"]
        for s in day["sessions"]
        if s["session_id"] == "gym_power_bouldering"
    ][0]
    assert boulder["gym_id"] == "alpha"
