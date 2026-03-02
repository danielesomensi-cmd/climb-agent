"""Tests for merge_prev_week_sessions — weekday-based merge after cache invalidation."""

from __future__ import annotations

from copy import deepcopy

from backend.api.deps import invalidate_week_cache
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


# ---- invalidate_week_cache stashing -----------------------------------------


class TestInvalidateWeekCache:

    def test_stashes_old_plan(self):
        """Old plan is saved to _prev_week_plan before clearing cache."""
        plan = _make_week_plan("2026-02-23", {0: [_session("x", status="done")]})
        state = {"current_week_plan": plan}
        invalidate_week_cache(state)
        assert state["current_week_plan"] is None
        assert state["_prev_week_plan"] is plan

    def test_no_overwrite_on_second_call(self):
        """Second invalidation doesn't overwrite stash (current_week_plan is None)."""
        plan = _make_week_plan("2026-02-23", {0: [_session("x", status="done")]})
        state = {"current_week_plan": plan}
        invalidate_week_cache(state)
        # Second call: current_week_plan is None, so _prev_week_plan untouched
        invalidate_week_cache(state)
        assert state["_prev_week_plan"] is plan

    def test_no_stash_when_no_plan(self):
        """No stash created if there was no plan to begin with."""
        state = {"current_week_plan": None}
        invalidate_week_cache(state)
        assert "_prev_week_plan" not in state


# ---- Integration: full incremental-regen flow --------------------------------


class TestIncrementalRegenFlow:
    """Simulate the full flow: plan with done/manual sessions → invalidate
    (macrocycle regen) → generate new plan → merge → verify preservation."""

    def test_done_sessions_survive_incremental_regen(self):
        old_plan = _make_week_plan("2026-02-23", {
            0: [_session("strength_long", status="done")],
            1: [_session("power_contact_gym", status="done")],
            2: [_session("technique_focus_gym")],
        })
        state = {"current_week_plan": old_plan, "feedback_log": [
            {"date": "2026-02-23", "session_id": "strength_long", "difficulty": "ok"},
        ]}

        # Step 1: macrocycle regen invalidates cache
        invalidate_week_cache(state)
        assert state["current_week_plan"] is None

        # Step 2: week router generates fresh plan
        new_plan = _make_week_plan("2026-02-23", {
            0: [_session("endurance_aerobic_gym")],
            1: [_session("technique_focus_gym")],
            2: [_session("power_endurance_gym")],
        })

        # Step 3: merge from stash
        result = merge_prev_week_sessions(state["_prev_week_plan"], new_plan)

        # Done sessions preserved with original session_id and status
        mon = result["weeks"][0]["days"][0]
        assert mon["sessions"][0]["session_id"] == "strength_long"
        assert mon["sessions"][0]["status"] == "done"

        tue = result["weeks"][0]["days"][1]
        assert tue["sessions"][0]["session_id"] == "power_contact_gym"
        assert tue["sessions"][0]["status"] == "done"

        # Non-done session was replaced by new plan
        wed = result["weeks"][0]["days"][2]
        assert wed["sessions"][0]["session_id"] == "power_endurance_gym"
        assert wed["sessions"][0].get("status") is None

    def test_quick_add_survives_incremental_regen(self):
        old_plan = _make_week_plan("2026-02-23", {
            0: [_session("strength_long")],
            1: [
                _session("technique_focus_gym"),
                _session("core_conditioning_standalone", slot="morning",
                         constraints_applied=["quick_add"]),
            ],
        })
        state = {"current_week_plan": old_plan}
        invalidate_week_cache(state)

        new_plan = _make_week_plan("2026-02-23", {
            0: [_session("endurance_aerobic_gym")],
            1: [_session("power_contact_gym")],
        })
        result = merge_prev_week_sessions(state["_prev_week_plan"], new_plan)

        # Quick-add session survives (appended in free morning slot)
        tue = result["weeks"][0]["days"][1]
        ids = {s["session_id"] for s in tue["sessions"]}
        assert "core_conditioning_standalone" in ids

        # Non-quick-add session was replaced
        assert "technique_focus_gym" not in ids

    def test_mixed_done_and_quick_add_survive(self):
        """Both done and quick-add sessions on different days survive."""
        old_plan = _make_week_plan("2026-02-23", {
            0: [_session("strength_long", status="done")],
            2: [_session("prehab_maintenance", slot="morning",
                         constraints_applied=["quick_add"])],
            4: [_session("power_contact_gym", status="skipped")],
        })
        state = {"current_week_plan": old_plan}
        invalidate_week_cache(state)

        new_plan = _make_week_plan("2026-02-23", {
            0: [_session("endurance_aerobic_gym")],
            2: [_session("technique_focus_gym")],
            4: [_session("power_endurance_gym")],
        })
        result = merge_prev_week_sessions(state["_prev_week_plan"], new_plan)

        # Monday: done preserved
        assert result["weeks"][0]["days"][0]["sessions"][0]["status"] == "done"
        # Wednesday: quick-add preserved (appended, different slot)
        wed_ids = {s["session_id"] for s in result["weeks"][0]["days"][2]["sessions"]}
        assert "prehab_maintenance" in wed_ids
        # Friday: skipped preserved
        assert result["weeks"][0]["days"][4]["sessions"][0]["status"] == "skipped"


# ---- Part B2: outdoor & other_activity fields survive regen ------------------

from backend.engine.replanner_v1 import regenerate_preserving_completed


class TestOutdoorFieldsPreserved:
    """Day-level outdoor and other_activity fields must survive regeneration."""

    def test_outdoor_fields_preserved_merge(self):
        """Outdoor fields survive merge_prev_week_sessions (weekday match)."""
        prev = _make_week_plan("2026-02-23", {
            2: [_session("technique_focus_gym", status="done")],
        })
        # Add outdoor fields to Wednesday
        prev["weeks"][0]["days"][2]["outdoor_spot_name"] = "Fontainebleau"
        prev["weeks"][0]["days"][2]["outdoor_spot_id"] = "spot-123"
        prev["weeks"][0]["days"][2]["outdoor_discipline"] = "boulder"
        prev["weeks"][0]["days"][2]["outdoor_session_status"] = "done"

        new = _make_week_plan("2026-02-23", {
            2: [_session("power_contact_gym")],
        })
        result = merge_prev_week_sessions(prev, new)
        wed = result["weeks"][0]["days"][2]
        assert wed["outdoor_spot_name"] == "Fontainebleau"
        assert wed["outdoor_spot_id"] == "spot-123"
        assert wed["outdoor_discipline"] == "boulder"
        assert wed["outdoor_session_status"] == "done"

    def test_outdoor_fields_preserved_regen(self):
        """Outdoor fields survive regenerate_preserving_completed (exact date)."""
        old = _make_week_plan("2026-02-23", {
            0: [_session("strength_long", status="done")],
        })
        old["weeks"][0]["days"][0]["outdoor_spot_name"] = "Kalymnos"
        old["weeks"][0]["days"][0]["outdoor_session_status"] = "done"
        old["weeks"][0]["days"][0]["outdoor_discipline"] = "lead"

        new = _make_week_plan("2026-02-23", {
            0: [_session("endurance_aerobic_gym")],
        })
        result = regenerate_preserving_completed(old, new)
        mon = result["weeks"][0]["days"][0]
        assert mon["outdoor_spot_name"] == "Kalymnos"
        assert mon["outdoor_session_status"] == "done"
        assert mon["outdoor_discipline"] == "lead"

    def test_other_activity_fields_preserved_merge(self):
        """other_activity_* fields survive merge."""
        prev = _make_week_plan("2026-02-23")
        prev["weeks"][0]["days"][3]["other_activity_status"] = "completed"
        prev["weeks"][0]["days"][3]["other_activity_feedback"] = "ok"
        prev["weeks"][0]["days"][3]["other_activity_load"] = 20

        new = _make_week_plan("2026-02-23")
        result = merge_prev_week_sessions(prev, new)
        thu = result["weeks"][0]["days"][3]
        assert thu["other_activity_status"] == "completed"
        assert thu["other_activity_feedback"] == "ok"
        assert thu["other_activity_load"] == 20

    def test_other_activity_fields_preserved_regen(self):
        """other_activity_* fields survive regenerate_preserving_completed."""
        old = _make_week_plan("2026-02-23")
        old["weeks"][0]["days"][1]["other_activity_status"] = "completed"
        old["weeks"][0]["days"][1]["other_activity_feedback"] = "hard"
        old["weeks"][0]["days"][1]["other_activity_load"] = 30

        new = _make_week_plan("2026-02-23")
        result = regenerate_preserving_completed(old, new)
        tue = result["weeks"][0]["days"][1]
        assert tue["other_activity_status"] == "completed"
        assert tue["other_activity_feedback"] == "hard"
        assert tue["other_activity_load"] == 30

    def test_outdoor_without_done_sessions_preserved(self):
        """Outdoor fields preserved even if no done sessions on that day."""
        prev = _make_week_plan("2026-02-23")
        # Only outdoor fields, no done sessions
        prev["weeks"][0]["days"][4]["outdoor_spot_name"] = "Arco"
        prev["weeks"][0]["days"][4]["outdoor_session_status"] = "planned"
        prev["weeks"][0]["days"][4]["outdoor_discipline"] = "lead"

        new = _make_week_plan("2026-02-23", {
            4: [_session("endurance_aerobic_gym")],
        })
        result = merge_prev_week_sessions(prev, new)
        fri = result["weeks"][0]["days"][4]
        assert fri["outdoor_spot_name"] == "Arco"
        assert fri["outdoor_session_status"] == "planned"

    def test_outdoor_fields_not_on_clean_days(self):
        """Days without outdoor fields in old plan stay clean in new plan."""
        prev = _make_week_plan("2026-02-23")
        prev["weeks"][0]["days"][0]["outdoor_spot_name"] = "Berdorf"
        prev["weeks"][0]["days"][0]["outdoor_session_status"] = "done"

        new = _make_week_plan("2026-02-23")
        result = merge_prev_week_sessions(prev, new)
        # Monday has outdoor
        assert result["weeks"][0]["days"][0].get("outdoor_spot_name") == "Berdorf"
        # Tuesday stays clean
        assert "outdoor_spot_name" not in result["weeks"][0]["days"][1]


# ---- Part C: session_log / feedback_log independent of plan ------------------


class TestFeedbackLogIndependent:

    def test_feedback_log_survives_cache_invalidation(self):
        """feedback_log in state is NOT cleared by invalidate_week_cache."""
        state = {
            "current_week_plan": _make_week_plan("2026-02-23"),
            "feedback_log": [
                {"date": "2026-02-23", "session_id": "strength_long", "difficulty": "ok"},
                {"date": "2026-02-24", "session_id": "technique_focus_gym", "difficulty": "hard"},
            ],
        }
        invalidate_week_cache(state)
        assert state["current_week_plan"] is None
        assert len(state["feedback_log"]) == 2
        assert state["feedback_log"][0]["session_id"] == "strength_long"

    def test_working_loads_survive_cache_invalidation(self):
        """working_loads in state are NOT cleared by invalidate_week_cache."""
        state = {
            "current_week_plan": _make_week_plan("2026-02-23"),
            "working_loads": {"entries": [{"exercise_id": "max_hang_5s", "load": 90}]},
        }
        invalidate_week_cache(state)
        assert len(state["working_loads"]["entries"]) == 1
