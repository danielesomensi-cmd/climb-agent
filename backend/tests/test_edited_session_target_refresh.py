"""A291 — DECISIONS Grades line: "_user_edited future sessions keep their
exercises; only targets refresh".

A pencil-edited session is never re-resolved (B153b), so before this its grade
targets froze at whatever the old arithmetic produced (6C instead of 6C+ for an
OS 7a+). refresh_edited_session_targets recomputes only the grade-target
fields, only on future pending sessions.
"""

from __future__ import annotations

from copy import deepcopy

from backend.api.routers import replanner as replanner_router
from backend.api.routers import week as week_router
from backend.engine.target_refresh import refresh_edited_session_targets

TODAY = "2026-10-05"


def _state(grades):
    return {
        "schema_version": "1.5",
        "assessment": {"grades": grades},
        "equipment": {"gyms": [{"gym_id": "g1", "equipment": ["gym_boulder", "gym_routes"]}]},
        "working_loads": {"entries": []},
        "bodyweight_kg": 75,
    }


def _edited_session(status="planned", source=None, stale_grade="6C"):
    inst = {
        "exercise_id": "route_intervals",
        "prescription": {"grade_ref": "lead_max_os", "grade_offset": -1, "sets": 4},
        "suggested": {
            "suggested_grade": stale_grade,
            "grade_ref": "lead_max_os",
            "grade_offset": -1,
            "suggested_external_load_kg": 12.5,  # a non-grade field: must not move
        },
    }
    if source:
        inst["source"] = source
    return {
        "session_id": "route_endurance_gym",
        "location": "gym",
        "gym_id": "g1",
        "status": status,
        "_user_edited": True,
        "resolved": {"resolved_session": {"exercise_instances": [inst]}},
    }


def _inst(session):
    return session["resolved"]["resolved_session"]["exercise_instances"][0]


def test_future_edited_session_gets_current_ladder():
    s = _edited_session()
    assert refresh_edited_session_targets(s, "2026-10-08", _state({"lead_max_os": "7a+"}), today=TODAY)
    sugg = _inst(s)["suggested"]
    assert sugg["suggested_grade"] == "6C+"
    assert sugg["grade_scale"] == "french"
    # exercises and non-grade fields untouched
    assert _inst(s)["exercise_id"] == "route_intervals"
    assert _inst(s)["prescription"]["sets"] == 4
    assert sugg["suggested_external_load_kg"] == 12.5


def test_today_counts_as_future():
    s = _edited_session()
    assert refresh_edited_session_targets(s, TODAY, _state({"lead_max_os": "7a+"}), today=TODAY)
    assert _inst(s)["suggested"]["suggested_grade"] == "6C+"


def test_unknown_grade_drops_the_stale_target():
    s = _edited_session()
    assert refresh_edited_session_targets(s, "2026-10-08", _state({"lead_max_os": "V9"}), today=TODAY)
    sugg = _inst(s)["suggested"]
    assert "suggested_grade" not in sugg
    assert sugg["suggested_external_load_kg"] == 12.5


def test_done_and_skipped_sessions_are_immutable():
    for status in ("done", "skipped"):
        s = _edited_session(status=status)
        before = deepcopy(s)
        assert not refresh_edited_session_targets(s, "2026-10-08", _state({"lead_max_os": "7a+"}), today=TODAY)
        assert s == before


def test_past_pending_session_is_immutable():
    s = _edited_session()
    before = deepcopy(s)
    assert not refresh_edited_session_targets(s, "2026-10-01", _state({"lead_max_os": "7a+"}), today=TODAY)
    assert s == before


def test_not_edited_session_is_ignored():
    s = _edited_session()
    s.pop("_user_edited")
    before = deepcopy(s)
    assert not refresh_edited_session_targets(s, "2026-10-08", _state({"lead_max_os": "7a+"}), today=TODAY)
    assert s == before


def test_user_added_instance_is_left_alone():
    s = _edited_session(source="user_added")
    before = deepcopy(s)
    assert not refresh_edited_session_targets(s, "2026-10-08", _state({"lead_max_os": "7a+"}), today=TODAY)
    assert s == before


def test_unknown_catalog_session_is_left_alone():
    s = _edited_session()
    s["session_id"] = "does_not_exist"
    before = deepcopy(s)
    assert not refresh_edited_session_targets(s, "2026-10-08", _state({"lead_max_os": "7a+"}), today=TODAY)
    assert s == before


def _plan(session, date):
    return {"weeks": [{"days": [{"date": date, "sessions": [session]}]}]}


def test_week_and_replanner_auto_resolve_refresh_without_reresolving(monkeypatch):
    """Both _auto_resolve loops keep skipping resolution of an edited session
    but refresh its grade targets."""
    def _boom(*a, **k):
        raise AssertionError("edited session must not be re-resolved")

    far_future = "2099-01-05"
    for module in (week_router, replanner_router):
        monkeypatch.setattr(module, "resolve_session", _boom)
        s = _edited_session()
        plan = _plan(s, far_future)
        module._auto_resolve(plan, _state({"lead_max_os": "7a+"}))
        inst = _inst(plan["weeks"][0]["days"][0]["sessions"][0])
        assert inst["exercise_id"] == "route_intervals"
        assert inst["suggested"]["suggested_grade"] == "6C+"
