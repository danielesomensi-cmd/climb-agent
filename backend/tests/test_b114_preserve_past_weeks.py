"""Tests for B-114: preserve past weeks in invalidate_week_cache + preserve_before guard."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import patch

from backend.api.deps import invalidate_week_cache
from backend.engine.replanner_v1 import merge_prev_week_sessions, regenerate_preserving_completed


def _make_week_plan(start_date: str, sessions_by_day: dict | None = None, **extra_day_fields) -> dict:
    """Build a minimal week plan with 7 days starting from *start_date*."""
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    days = []
    for i in range(7):
        d = start + timedelta(days=i)
        day_sessions = (sessions_by_day or {}).get(i, [])
        day = {"date": d.isoformat(), "sessions": deepcopy(day_sessions)}
        # Apply extra day-level fields by day index
        for k, v in (extra_day_fields.get(i) or {}).items():
            day[k] = v
        days.append(day)
    return {
        "start_date": start_date,
        "weeks": [{"days": days}],
        "plan_revision": 1,
    }


def _session(session_id: str, slot: str = "evening", **kwargs) -> dict:
    s = {"session_id": session_id, "slot": slot, "intensity": "medium"}
    s.update(kwargs)
    return s


# ---- invalidate_week_cache: past weeks preserved ----------------------------


class TestInvalidatePreservesPastWeeks:

    @patch("backend.api.deps.datetime")
    def test_past_weeks_preserved(self, mock_dt):
        """week_plans with start_date < today are kept."""
        mock_dt.now.return_value = datetime(2026, 3, 9, 12, 0, 0)
        mock_dt.strptime = datetime.strptime

        past_plan = _make_week_plan("2026-03-02", {
            0: [_session("strength_long", status="done")],
        })
        current_plan = _make_week_plan("2026-03-09", {
            0: [_session("endurance_aerobic_gym")],
        })
        state = {
            "current_week_plan": current_plan,
            "week_plans": {
                "2026-03-02": past_plan,
                "2026-03-09": current_plan,
            },
        }
        invalidate_week_cache(state)

        assert "2026-03-02" in state["week_plans"]
        assert state["week_plans"]["2026-03-02"] is past_plan
        assert state["week_plans"]["2026-03-02"]["weeks"][0]["days"][0]["sessions"][0]["status"] == "done"

    @patch("backend.api.deps.datetime")
    def test_current_week_removed(self, mock_dt):
        """week_plans with start_date >= today are removed."""
        mock_dt.now.return_value = datetime(2026, 3, 9, 12, 0, 0)
        mock_dt.strptime = datetime.strptime

        state = {
            "current_week_plan": _make_week_plan("2026-03-09"),
            "week_plans": {
                "2026-03-02": _make_week_plan("2026-03-02"),
                "2026-03-09": _make_week_plan("2026-03-09"),
            },
        }
        invalidate_week_cache(state)

        assert "2026-03-09" not in state["week_plans"]

    @patch("backend.api.deps.datetime")
    def test_future_week_removed(self, mock_dt):
        """week_plans with start_date > today are also removed."""
        mock_dt.now.return_value = datetime(2026, 3, 9, 12, 0, 0)
        mock_dt.strptime = datetime.strptime

        state = {
            "current_week_plan": _make_week_plan("2026-03-09"),
            "week_plans": {
                "2026-03-02": _make_week_plan("2026-03-02"),
                "2026-03-09": _make_week_plan("2026-03-09"),
                "2026-03-16": _make_week_plan("2026-03-16"),
            },
        }
        invalidate_week_cache(state)

        assert "2026-03-02" in state["week_plans"]
        assert "2026-03-09" not in state["week_plans"]
        assert "2026-03-16" not in state["week_plans"]

    @patch("backend.api.deps.datetime")
    def test_multiple_past_weeks_preserved(self, mock_dt):
        """Multiple past weeks are all preserved."""
        mock_dt.now.return_value = datetime(2026, 3, 16, 12, 0, 0)
        mock_dt.strptime = datetime.strptime

        state = {
            "current_week_plan": _make_week_plan("2026-03-16"),
            "week_plans": {
                "2026-02-23": _make_week_plan("2026-02-23"),
                "2026-03-02": _make_week_plan("2026-03-02"),
                "2026-03-09": _make_week_plan("2026-03-09"),
                "2026-03-16": _make_week_plan("2026-03-16"),
            },
        }
        invalidate_week_cache(state)

        assert "2026-02-23" in state["week_plans"]
        assert "2026-03-02" in state["week_plans"]
        assert "2026-03-09" in state["week_plans"]
        assert "2026-03-16" not in state["week_plans"]


# ---- merge_prev_week_sessions with preserve_before --------------------------


class TestMergePreserveBefore:

    def test_days_before_preserve_copied_wholesale(self):
        """Days before preserve_before are copied entirely from prev_plan."""
        prev = _make_week_plan("2026-03-09", {
            0: [_session("strength_long", status="done")],
            1: [_session("technique_focus_gym", status="done")],
            2: [_session("power_contact_gym")],  # planned, not done
        })
        prev["weeks"][0]["days"][0]["status"] = "done"
        prev["weeks"][0]["days"][1]["status"] = "done"

        new = _make_week_plan("2026-03-09", {
            0: [_session("endurance_aerobic_gym")],
            1: [_session("yoga_recovery")],
            2: [_session("prehab_maintenance")],
        })

        # preserve_before = Wed 03-11 → Mon and Tue copied wholesale
        result = merge_prev_week_sessions(prev, new, preserve_before="2026-03-11")

        mon = result["weeks"][0]["days"][0]
        assert mon["sessions"][0]["session_id"] == "strength_long"
        assert mon["sessions"][0]["status"] == "done"
        assert mon["status"] == "done"

        tue = result["weeks"][0]["days"][1]
        assert tue["sessions"][0]["session_id"] == "technique_focus_gym"
        assert tue["sessions"][0]["status"] == "done"
        assert tue["status"] == "done"

        # Wed is >= preserve_before, so gets new plan (power_contact_gym was not preservable)
        wed = result["weeks"][0]["days"][2]
        assert wed["sessions"][0]["session_id"] == "prehab_maintenance"

    def test_today_with_completed_session_copied_wholesale(self):
        """Day == preserve_before with a completed session is copied wholesale (Bug 2)."""
        prev = _make_week_plan("2026-03-09", {
            0: [_session("strength_long", status="done")],
        })
        prev["weeks"][0]["days"][0]["status"] = "done"

        new = _make_week_plan("2026-03-09", {
            0: [_session("endurance_aerobic_gym")],
        })

        # preserve_before = Mon 03-09 (same as today with done session)
        result = merge_prev_week_sessions(prev, new, preserve_before="2026-03-09")

        mon = result["weeks"][0]["days"][0]
        assert mon["sessions"][0]["session_id"] == "strength_long"
        assert mon["sessions"][0]["status"] == "done"

    def test_today_with_outdoor_done_copied_wholesale(self):
        """Day == preserve_before with outdoor_session_status=done is copied wholesale."""
        prev = _make_week_plan("2026-03-09")
        prev["weeks"][0]["days"][0]["outdoor_session_status"] = "done"
        prev["weeks"][0]["days"][0]["outdoor_spot_name"] = "Berdorf"
        prev["weeks"][0]["days"][0]["outdoor_discipline"] = "lead"

        new = _make_week_plan("2026-03-09", {
            0: [_session("endurance_aerobic_gym")],
        })

        result = merge_prev_week_sessions(prev, new, preserve_before="2026-03-09")

        mon = result["weeks"][0]["days"][0]
        assert mon["outdoor_session_status"] == "done"
        assert mon["outdoor_spot_name"] == "Berdorf"
        assert mon["outdoor_discipline"] == "lead"

    def test_today_without_done_regenerated_normally(self):
        """Day == preserve_before without done sessions gets new plan."""
        prev = _make_week_plan("2026-03-09", {
            0: [_session("strength_long")],  # planned, not done
        })

        new = _make_week_plan("2026-03-09", {
            0: [_session("endurance_aerobic_gym")],
        })

        result = merge_prev_week_sessions(prev, new, preserve_before="2026-03-09")

        mon = result["weeks"][0]["days"][0]
        assert mon["sessions"][0]["session_id"] == "endurance_aerobic_gym"

    def test_no_preserve_before_merges_normally(self):
        """Without preserve_before, merge works like before (preservable sessions only)."""
        prev = _make_week_plan("2026-03-09", {
            0: [_session("strength_long", status="done")],
            1: [_session("technique_focus_gym")],  # not done
        })

        new = _make_week_plan("2026-03-09", {
            0: [_session("endurance_aerobic_gym")],
            1: [_session("yoga_recovery")],
        })

        result = merge_prev_week_sessions(prev, new)

        # Done session preserved
        mon = result["weeks"][0]["days"][0]
        assert mon["sessions"][0]["session_id"] == "strength_long"
        assert mon["sessions"][0]["status"] == "done"

        # Planned session replaced
        tue = result["weeks"][0]["days"][1]
        assert tue["sessions"][0]["session_id"] == "yoga_recovery"


# ---- regenerate_preserving_completed with preserve_before --------------------


class TestRegenPreserveBefore:

    def test_past_days_copied_wholesale(self):
        """Days before preserve_before copied entirely from old_plan."""
        old = _make_week_plan("2026-03-09", {
            0: [_session("strength_long", status="done")],
            1: [_session("technique_focus_gym")],  # planned
        })
        old["weeks"][0]["days"][0]["status"] = "done"

        new = _make_week_plan("2026-03-09", {
            0: [_session("endurance_aerobic_gym")],
            1: [_session("yoga_recovery")],
        })

        result = regenerate_preserving_completed(old, new, preserve_before="2026-03-11")

        mon = result["weeks"][0]["days"][0]
        assert mon["sessions"][0]["session_id"] == "strength_long"
        assert mon["status"] == "done"

        # Tue is also < preserve_before, copied wholesale (even though planned)
        tue = result["weeks"][0]["days"][1]
        assert tue["sessions"][0]["session_id"] == "technique_focus_gym"

    def test_today_with_done_copied_wholesale(self):
        """Day == preserve_before with done session is copied wholesale."""
        old = _make_week_plan("2026-03-09", {
            0: [_session("strength_long", status="done")],
        })

        new = _make_week_plan("2026-03-09", {
            0: [_session("endurance_aerobic_gym")],
        })

        result = regenerate_preserving_completed(old, new, preserve_before="2026-03-09")

        mon = result["weeks"][0]["days"][0]
        assert mon["sessions"][0]["session_id"] == "strength_long"
        assert mon["sessions"][0]["status"] == "done"


# ---- Full flow: past week with done sessions survives regenerate -------------


class TestFullRegenFlowB114:

    @patch("backend.api.deps.datetime")
    def test_past_week_done_sessions_survive_full_regen(self, mock_dt):
        """Simulate: past week with done sessions → invalidate → merge → verify."""
        mock_dt.now.return_value = datetime(2026, 3, 9, 12, 0, 0)
        mock_dt.strptime = datetime.strptime

        past_plan = _make_week_plan("2026-03-02", {
            0: [_session("boulder_circuit_gym", status="done")],
            1: [_session("complementary_conditioning", status="done")],
            3: [_session("endurance_aerobic_gym", status="done")],
        })
        past_plan["weeks"][0]["days"][0]["status"] = "done"
        past_plan["weeks"][0]["days"][1]["status"] = "done"
        past_plan["weeks"][0]["days"][3]["status"] = "done"

        current_plan = _make_week_plan("2026-03-09", {
            0: [_session("technique_focus_gym")],
        })

        state = {
            "current_week_plan": current_plan,
            "week_plans": {
                "2026-03-02": past_plan,
                "2026-03-09": current_plan,
            },
        }

        # Step 1: invalidate (simulates macrocycle regen)
        invalidate_week_cache(state)

        # Past week is preserved
        assert "2026-03-02" in state["week_plans"]
        wp_past = state["week_plans"]["2026-03-02"]
        assert wp_past["weeks"][0]["days"][0]["sessions"][0]["status"] == "done"
        assert wp_past["weeks"][0]["days"][1]["sessions"][0]["status"] == "done"
        assert wp_past["weeks"][0]["days"][3]["sessions"][0]["status"] == "done"

        # Current week is removed
        assert "2026-03-09" not in state["week_plans"]

        # _prev_week_plan stashed for current week merge
        assert state["_prev_week_plan"] is current_plan

    @patch("backend.api.deps.datetime")
    def test_outdoor_on_past_week_survives_full_regen(self, mock_dt):
        """Outdoor session_status on past days survives the full regenerate flow."""
        mock_dt.now.return_value = datetime(2026, 3, 9, 12, 0, 0)
        mock_dt.strptime = datetime.strptime

        past_plan = _make_week_plan("2026-03-02", {
            5: [_session("endurance_aerobic_gym", status="skipped")],
            6: [_session("prehab_maintenance", status="skipped")],
        })
        past_plan["weeks"][0]["days"][5]["outdoor_session_status"] = "done"
        past_plan["weeks"][0]["days"][5]["outdoor_spot_name"] = "projecting"
        past_plan["weeks"][0]["days"][5]["outdoor_discipline"] = "both"
        past_plan["weeks"][0]["days"][5]["status"] = "done"
        past_plan["weeks"][0]["days"][6]["outdoor_session_status"] = "done"
        past_plan["weeks"][0]["days"][6]["outdoor_spot_name"] = "volume"
        past_plan["weeks"][0]["days"][6]["outdoor_discipline"] = "lead"
        past_plan["weeks"][0]["days"][6]["status"] = "done"

        current_plan = _make_week_plan("2026-03-09")

        state = {
            "current_week_plan": current_plan,
            "week_plans": {
                "2026-03-02": past_plan,
                "2026-03-09": current_plan,
            },
        }

        invalidate_week_cache(state)

        # Past week with outdoor data fully preserved
        wp_past = state["week_plans"]["2026-03-02"]
        sat = wp_past["weeks"][0]["days"][5]
        assert sat["outdoor_session_status"] == "done"
        assert sat["outdoor_spot_name"] == "projecting"
        assert sat["outdoor_discipline"] == "both"

        sun = wp_past["weeks"][0]["days"][6]
        assert sun["outdoor_session_status"] == "done"
        assert sun["outdoor_spot_name"] == "volume"
        assert sun["outdoor_discipline"] == "lead"
