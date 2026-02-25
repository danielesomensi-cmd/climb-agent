"""Tests for merge_prev_week_sessions — weekday-based merge after cache invalidation."""

from __future__ import annotations

from copy import deepcopy

from backend.engine.replanner_v1 import merge_prev_week_sessions


def _make_week_plan(start_date: str, sessions_by_day: dict | None = None) -> dict:
    """Build a minimal week plan with 7 days starting from *start_date*.

    *sessions_by_day* maps weekday index (0=Mon) to a list of session dicts.
    """
    from datetime import datetime, timedelta

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    days = []
    for i in range(7):
        d = start + timedelta(days=i)
        day_sessions = (sessions_by_day or {}).get(i, [])
        days.append({"date": d.isoformat(), "sessions": deepcopy(day_sessions)})
    return {
        "start_date": start_date,
        "weeks": [{"days": days}],
        "plan_revision": 1,
    }


def _session(session_id: str, slot: str = "evening", **kwargs) -> dict:
    """Helper to build a session entry."""
    s = {"session_id": session_id, "slot": slot, "intensity": "medium"}
    s.update(kwargs)
    return s


# ---- Part A: completed sessions survive regen --------------------------------


class TestCompletedSessionsSurvive:

    def test_done_session_preserved_same_dates(self):
        """Done session on Monday preserved when dates match."""
        prev = _make_week_plan("2026-02-23", {
            0: [_session("strength_long", status="done")],
            1: [_session("power_contact_gym", status="done")],
        })
        new = _make_week_plan("2026-02-23", {
            0: [_session("endurance_aerobic_gym")],
            1: [_session("technique_focus_gym")],
        })
        result = merge_prev_week_sessions(prev, new)
        mon = result["weeks"][0]["days"][0]
        assert mon["sessions"][0]["status"] == "done"
        assert mon["sessions"][0]["session_id"] == "strength_long"
        tue = result["weeks"][0]["days"][1]
        assert tue["sessions"][0]["status"] == "done"
        assert tue["sessions"][0]["session_id"] == "power_contact_gym"

    def test_done_session_preserved_different_dates(self):
        """Done session preserved even when start_date differs (weekday match)."""
        # Prev plan: week of Feb 16 (Mon)
        prev = _make_week_plan("2026-02-16", {
            0: [_session("strength_long", status="done")],
        })
        # New plan: week of Feb 23 (Mon) — different dates, same weekday
        new = _make_week_plan("2026-02-23", {
            0: [_session("endurance_aerobic_gym")],
        })
        result = merge_prev_week_sessions(prev, new)
        mon = result["weeks"][0]["days"][0]
        assert mon["sessions"][0]["status"] == "done"
        assert mon["sessions"][0]["session_id"] == "strength_long"

    def test_skipped_session_preserved(self):
        """Skipped sessions are also preserved."""
        prev = _make_week_plan("2026-02-23", {
            2: [_session("technique_focus_gym", status="skipped")],
        })
        new = _make_week_plan("2026-02-23", {
            2: [_session("power_contact_gym")],
        })
        result = merge_prev_week_sessions(prev, new)
        wed = result["weeks"][0]["days"][2]
        assert wed["sessions"][0]["status"] == "skipped"

    def test_planned_sessions_not_preserved(self):
        """Regular planned sessions (no status) are NOT preserved — replaced by new plan."""
        prev = _make_week_plan("2026-02-23", {
            0: [_session("old_session_x")],
        })
        new = _make_week_plan("2026-02-23", {
            0: [_session("new_session_y")],
        })
        result = merge_prev_week_sessions(prev, new)
        mon = result["weeks"][0]["days"][0]
        assert mon["sessions"][0]["session_id"] == "new_session_y"


# ---- Part B: manual (quick-add) sessions survive regen -----------------------


class TestManualSessionsSurvive:

    def test_quick_add_session_preserved(self):
        """Session with constraints_applied=['quick_add'] survives regen."""
        prev = _make_week_plan("2026-02-23", {
            1: [
                _session("power_contact_gym"),
                _session("core_conditioning_standalone", slot="lunch",
                         constraints_applied=["quick_add"]),
            ],
        })
        new = _make_week_plan("2026-02-23", {
            1: [_session("technique_focus_gym")],
        })
        result = merge_prev_week_sessions(prev, new)
        tue = result["weeks"][0]["days"][1]
        session_ids = [s["session_id"] for s in tue["sessions"]]
        assert "core_conditioning_standalone" in session_ids

    def test_quick_add_different_slot_appended(self):
        """Quick-add in a free slot is appended, not replacing existing."""
        prev = _make_week_plan("2026-02-23", {
            0: [_session("core_conditioning_standalone", slot="morning",
                         constraints_applied=["quick_add"])],
        })
        new = _make_week_plan("2026-02-23", {
            0: [_session("strength_long", slot="evening")],
        })
        result = merge_prev_week_sessions(prev, new)
        mon = result["weeks"][0]["days"][0]
        assert len(mon["sessions"]) == 2
        ids = {s["session_id"] for s in mon["sessions"]}
        assert ids == {"strength_long", "core_conditioning_standalone"}

    def test_quick_add_different_dates(self):
        """Quick-add preserved even when start_date differs."""
        prev = _make_week_plan("2026-02-16", {
            3: [_session("prehab_maintenance", slot="lunch",
                         constraints_applied=["quick_add"])],
        })
        new = _make_week_plan("2026-02-23", {
            3: [_session("yoga_recovery", slot="evening")],
        })
        result = merge_prev_week_sessions(prev, new)
        thu = result["weeks"][0]["days"][3]
        ids = {s["session_id"] for s in thu["sessions"]}
        assert "prehab_maintenance" in ids


# ---- Edge cases --------------------------------------------------------------


class TestMergeEdgeCases:

    def test_no_preservable_returns_new_unchanged(self):
        """Without preservable sessions, result equals new plan (+ revision bump)."""
        prev = _make_week_plan("2026-02-23", {
            0: [_session("old_session")],
        })
        new = _make_week_plan("2026-02-23", {
            0: [_session("new_session")],
        })
        result = merge_prev_week_sessions(prev, new)
        mon = result["weeks"][0]["days"][0]
        assert mon["sessions"][0]["session_id"] == "new_session"

    def test_plan_revision_bumped(self):
        """Merge bumps the plan_revision."""
        prev = _make_week_plan("2026-02-23", {
            0: [_session("x", status="done")],
        })
        new = _make_week_plan("2026-02-23", {0: [_session("y")]})
        new["plan_revision"] = 3
        result = merge_prev_week_sessions(prev, new)
        assert result["plan_revision"] == 4

    def test_mixed_done_and_quick_add(self):
        """Both done and quick-add sessions on same day are preserved."""
        prev = _make_week_plan("2026-02-23", {
            0: [
                _session("strength_long", slot="evening", status="done"),
                _session("core_conditioning_standalone", slot="morning",
                         constraints_applied=["quick_add"]),
            ],
        })
        new = _make_week_plan("2026-02-23", {
            0: [_session("endurance_aerobic_gym", slot="evening")],
        })
        result = merge_prev_week_sessions(prev, new)
        mon = result["weeks"][0]["days"][0]
        ids = {s["session_id"] for s in mon["sessions"]}
        assert "strength_long" in ids
        assert "core_conditioning_standalone" in ids
        # The auto-generated session should have been replaced by the done one
        assert "endurance_aerobic_gym" not in ids

    def test_empty_prev_plan(self):
        """Empty prev plan days don't crash."""
        prev = _make_week_plan("2026-02-23")
        new = _make_week_plan("2026-02-23", {0: [_session("x")]})
        result = merge_prev_week_sessions(prev, new)
        assert result["weeks"][0]["days"][0]["sessions"][0]["session_id"] == "x"
