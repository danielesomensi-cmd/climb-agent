from __future__ import annotations

from datetime import datetime

from catalog.engine.planner_v1 import generate_week_plan
from catalog.engine.replanner_v1 import apply_events


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
    assert slot_session["session_id"] == "deload_recovery"
    assert slot_session["intent"] == "recovery"
    assert _count_hard_days(updated) <= 3
