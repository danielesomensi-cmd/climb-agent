"""Tests for merge_prev_week_sessions — merge after cache invalidation.

B369: the weekday fallback is gone (a stashed plan of another week is
discarded — P5) and ``invalidate_week_cache`` marks weeks stale instead of
deleting them and stashing ``_prev_week_plan``.
"""

from __future__ import annotations

from copy import deepcopy

from datetime import date, timedelta

from backend.api.deps import STALE_KEY, invalidate_week_cache
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

    def test_done_session_of_another_week_is_never_copied(self):
        """B369/P5: a stashed plan of another week is discarded — its done
        session must not reappear on the same weekday of this week."""
        prev = _make_week_plan("2026-02-16", {
            0: [_session("strength_long", status="done")],
        })
        new = _make_week_plan("2026-02-23", {
            0: [_session("endurance_aerobic_gym")],
        })
        result = merge_prev_week_sessions(prev, new)
        assert result == new

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

    def test_quick_add_of_another_week_is_not_copied(self):
        """B369/P5: nothing from another week is weekday-copied."""
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
        assert ids == {"yoga_recovery"}


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


def _this_monday() -> str:
    t = date.today()
    return (t - timedelta(days=t.weekday())).isoformat()


class TestInvalidateWeekCache:

    def test_marks_current_week_stale_and_keeps_it(self):
        """B369: the plan stays where it is, flagged stale — nothing stashed."""
        plan = _make_week_plan(_this_monday(), {0: [_session("x", status="done")]})
        state = {"current_week_plan": plan, "week_plans": {_this_monday(): deepcopy(plan)}}
        invalidate_week_cache(state)
        assert state["current_week_plan"][STALE_KEY] is True
        assert state["week_plans"][_this_monday()][STALE_KEY] is True
        assert state["week_plans"][_this_monday()]["weeks"] == plan["weeks"]
        assert "_prev_week_plan" not in state

    def test_idempotent(self):
        plan = _make_week_plan(_this_monday(), {0: [_session("x", status="done")]})
        state = {"week_plans": {_this_monday(): plan}}
        invalidate_week_cache(state)
        once = deepcopy(state)
        invalidate_week_cache(state)
        assert state == once

    def test_past_week_never_flagged(self):
        past = (date.fromisoformat(_this_monday()) - timedelta(days=7)).isoformat()
        plan = _make_week_plan(past, {0: [_session("x", status="done")]})
        state = {"week_plans": {past: deepcopy(plan)}, "current_week_plan": None}
        invalidate_week_cache(state)
        assert state["week_plans"][past] == plan

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

        # Step 1: macrocycle regen invalidates cache — B369: the plan stays,
        # it is what the regeneration merges from.
        invalidate_week_cache(state)
        assert state["current_week_plan"] is old_plan

        # Step 2: week router generates fresh plan
        new_plan = _make_week_plan("2026-02-23", {
            0: [_session("endurance_aerobic_gym")],
            1: [_session("technique_focus_gym")],
            2: [_session("power_endurance_gym")],
        })

        # Step 3: merge from the cached plan
        result = merge_prev_week_sessions(state["current_week_plan"], new_plan)

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
        result = merge_prev_week_sessions(state["current_week_plan"], new_plan)

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
        result = merge_prev_week_sessions(state["current_week_plan"], new_plan)

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
        """Outdoor fields survive merge_prev_week_sessions."""
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

    def test_other_activities_list_preserved_regen(self):
        """B276: the new multi-activity list survives regeneration untouched."""
        old = _make_week_plan("2026-02-23")
        old["weeks"][0]["days"][1]["other_activities"] = [
            {"slot": "lunch", "name": "Chest", "status": "completed",
             "feedback": "ok", "load": 20, "duration_minutes": 45},
            {"slot": "evening", "name": "HIIT", "status": "completed",
             "feedback": "hard", "load": 30},
        ]

        new = _make_week_plan("2026-02-23")
        result = regenerate_preserving_completed(old, new)
        tue = result["weeks"][0]["days"][1]
        assert tue["other_activities"] == [
            {"slot": "lunch", "name": "Chest", "status": "completed",
             "feedback": "ok", "load": 20, "duration_minutes": 45},
            {"slot": "evening", "name": "HIIT", "status": "completed",
             "feedback": "hard", "load": 30},
        ]

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
        assert state["current_week_plan"] is not None
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


# ---- Part F: B164 — planned_load preservation --------------------------------


class TestPlannedLoadPreservation:
    """B164: planned_load must survive regeneration and merge."""

    def test_merge_preserves_planned_load(self):
        """merge_prev_week_sessions restores planned_load from prev plan."""
        prev = _make_week_plan("2026-02-23")
        prev["weekly_load_summary"] = {"planned_load": 395, "total_load": 395}
        new = _make_week_plan("2026-02-23")
        new["weekly_load_summary"] = {"planned_load": 165, "total_load": 165}

        # B369 review: only a regeneration that skipped days of the week.
        result = merge_prev_week_sessions(prev, new, preserve_before="2026-02-25")
        assert result["weekly_load_summary"]["planned_load"] == 395

    def test_merge_falls_back_to_total_load(self):
        """Pre-B164 plans without planned_load: falls back to total_load."""
        prev = _make_week_plan("2026-02-23")
        prev["weekly_load_summary"] = {"total_load": 350}  # no planned_load
        new = _make_week_plan("2026-02-23")
        new["weekly_load_summary"] = {"planned_load": 100, "total_load": 100}

        result = merge_prev_week_sessions(prev, new, preserve_before="2026-02-25")
        assert result["weekly_load_summary"]["planned_load"] == 350

    def test_whole_week_regeneration_keeps_fresh_planned_load(self):
        """B369 review: a stale future week regenerated whole (no
        preserve_before, or preserve_before on its Monday) keeps the fresh
        summary — the new structure's load, not the old one's."""
        prev = _make_week_plan("2026-02-23")
        prev["weekly_load_summary"] = {"planned_load": 520, "total_load": 520}
        new = _make_week_plan("2026-02-23")
        new["weekly_load_summary"] = {"planned_load": 310, "total_load": 310}
        for pb in (None, "2026-02-23", "2026-02-20"):
            result = merge_prev_week_sessions(prev, new, preserve_before=pb)
            assert result["weekly_load_summary"] == {"planned_load": 310, "total_load": 310}

    def test_regen_preserves_planned_load(self):
        """regenerate_preserving_completed restores planned_load from old plan."""
        from backend.engine.replanner_v1 import regenerate_preserving_completed

        old = _make_week_plan("2026-02-23", {
            0: [_session("strength_long", status="done", estimated_load_score=85)],
        })
        old["weekly_load_summary"] = {"planned_load": 395, "total_load": 395}

        new = _make_week_plan("2026-02-23", {
            0: [_session("endurance_aerobic_gym", estimated_load_score=40)],
        })
        new["weekly_load_summary"] = {"planned_load": 165, "total_load": 165}

        result = regenerate_preserving_completed(old, new, preserve_before="2026-02-25")
        assert result["weekly_load_summary"]["planned_load"] == 395

    def test_quick_add_does_not_change_planned_load(self):
        """Quick-add must NOT modify planned_load."""
        from backend.engine.replanner_v1 import apply_day_add

        plan = _make_week_plan("2026-02-23")
        plan["weekly_load_summary"] = {"planned_load": 300, "total_load": 300}
        plan["profile_snapshot"] = {"phase_id": "base"}

        result, _, _ = apply_day_add(
            plan, session_id="finger_strength_home",
            target_date="2026-02-23", slot="evening", location="home",
        )
        assert result["weekly_load_summary"]["planned_load"] == 300

    def test_override_does_not_change_planned_load(self):
        """Override must NOT modify planned_load."""
        from backend.engine.replanner_v1 import apply_day_override

        plan = _make_week_plan("2026-02-23", {
            0: [_session("strength_long", slot="evening", estimated_load_score=85)],
        })
        plan["weekly_load_summary"] = {"planned_load": 300, "total_load": 300}
        plan["profile_snapshot"] = {"phase_id": "base"}

        result = apply_day_override(
            plan, intent="rest", target_date="2026-02-23",
            location="home", reference_date="2026-02-23",
        )
        assert result["weekly_load_summary"]["planned_load"] == 300
