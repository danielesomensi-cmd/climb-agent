from __future__ import annotations

from datetime import datetime

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
