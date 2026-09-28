"""B354: moving a session leaves the vacated slot empty.

Before B354 `move_session` refilled the origin slot with regeneration_easy (or
complementary_conditioning next to a hard session). Daniele moved his max hang
test from Wednesday to Monday morning and found an unrequested recovery session
left on Wednesday evening — the week looked rearranged behind his back.
"""

from backend.engine.replanner_v1 import apply_events


def _plan(days):
    return {
        "start_date": "2026-09-14",
        "weeks": [{"days": days}],
        "adaptations": [],
        "profile_snapshot": {"phase_id": "base", "hard_cap_per_week": 3},
    }


def _day(date, sessions):
    return {"date": date, "sessions": sessions}


def _session(sid, slot="evening", *, hard=False, finger=False, test=False):
    tags = {"hard": hard, "finger": finger}
    if test:
        tags["test"] = True
    return {"session_id": sid, "slot": slot, "status": "planned", "location": "home",
            "intensity": "high" if hard else "low", "tags": tags}


def _days_of(plan):
    return {d["date"]: d for d in plan["weeks"][0]["days"]}


def _move(plan, from_date, from_slot, to_date, to_slot):
    return apply_events(plan, [{
        "event_type": "move_session", "from_date": from_date, "from_slot": from_slot,
        "to_date": to_date, "to_slot": to_slot,
    }])


def test_moving_the_only_session_leaves_the_origin_day_as_rest():
    plan = _plan([
        _day("2026-09-14", []),
        _day("2026-09-16", [_session("test_max_hang_7s", hard=True, finger=True, test=True)]),
    ])
    plan["weeks"][0]["days"][1]["status"] = "planned"

    days = _days_of(_move(plan, "2026-09-16", "evening", "2026-09-14", "morning"))

    assert days["2026-09-16"]["sessions"] == []
    assert "status" not in days["2026-09-16"]
    assert [s["session_id"] for s in days["2026-09-14"]["sessions"]] == ["test_max_hang_7s"]


def test_no_refill_next_to_a_hard_session_either():
    """The old code picked complementary_conditioning when the day kept a hard session."""
    plan = _plan([
        _day("2026-09-15", [
            _session("strength_long", "lunch", hard=True, finger=True),
            _session("technique_focus_gym", "evening"),
        ]),
        _day("2026-09-19", []),
    ])

    days = _days_of(_move(plan, "2026-09-15", "evening", "2026-09-19", "evening"))

    assert [s["session_id"] for s in days["2026-09-15"]["sessions"]] == ["strength_long"]
    assert not any(s.get("session_id") == "complementary_conditioning"
                   for d in days.values() for s in d["sessions"])


def test_moved_test_keeps_its_identity_and_tags():
    plan = _plan([
        _day("2026-09-17", [_session("test_max_weighted_pullup", "lunch", hard=True, test=True)]),
        _day("2026-09-18", []),
    ])

    days = _days_of(_move(plan, "2026-09-17", "lunch", "2026-09-18", "lunch"))

    moved = days["2026-09-18"]["sessions"][0]
    assert moved["session_id"] == "test_max_weighted_pullup"
    assert moved["tags"] == {"hard": True, "finger": False, "test": True}


def test_finger_gap_still_enforced_after_a_move():
    """Removing the refill must not remove the guard: _reconcile still runs."""
    plan = _plan([
        _day("2026-09-14", [_session("strength_long", hard=True, finger=True)]),
        _day("2026-09-15", []),
        _day("2026-09-17", [_session("power_contact_gym", hard=True, finger=True)]),
    ])

    days = _days_of(_move(plan, "2026-09-17", "evening", "2026-09-15", "evening"))

    tue = days["2026-09-15"]["sessions"][0]
    assert tue["session_id"] == "regeneration_easy"
    assert "finger_spacing_downshift" in tue.get("constraints_applied", [])
    assert days["2026-09-17"]["sessions"] == []
