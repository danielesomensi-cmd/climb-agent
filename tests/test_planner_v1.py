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


def test_power_boulder_session_requires_supported_gym_equipment():
    availability = _availability()
    availability["tue"]["evening"]["gym_id"] = "tiny_gym"
    plan = generate_week_plan(
        start_date="2026-01-05",
        mode="balanced",
        availability=availability,
        allowed_locations=["home", "gym", "outdoor"],
        default_gym_id="tiny_gym",
        gyms=[
            {"gym_id": "tiny_gym", "equipment": ["barbell"]},
            {"gym_id": "work_gym", "equipment": ["gym_boulder"]},
        ],
    )

    for day in plan["weeks"][0]["days"]:
        for session in day["sessions"]:
            if session["session_id"] == "gym_power_bouldering":
                assert session["location"] == "gym"
                assert session["gym_id"] == "work_gym"
