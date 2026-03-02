"""Tests for generate_test_week() and should_show_test_reminder()."""

from datetime import date, timedelta

import pytest

from backend.engine.planner_v2 import generate_test_week, should_show_test_reminder


# ---------------------------------------------------------------------------
# Availability helpers
# ---------------------------------------------------------------------------

def _full_availability():
    """All 7 days available, evening slot, gym location."""
    avail = {}
    for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
        avail[wd] = {
            "evening": {"available": True, "preferred_location": "gym"},
        }
    return avail


def _partial_availability(days: list[str]):
    """Only specified weekdays available."""
    avail = {}
    for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
        avail[wd] = {
            "evening": {"available": wd in days, "preferred_location": "gym"},
        }
    return avail


# ---------------------------------------------------------------------------
# generate_test_week tests
# ---------------------------------------------------------------------------

class TestGenerateTestWeekBasic:
    def test_basic_structure(self):
        """Test week has 3 test sessions on non-consecutive days."""
        plan = generate_test_week(
            start_date="2026-03-02",
            availability=_full_availability(),
            allowed_locations=["gym", "home"],
        )
        assert plan["plan_version"] == "test_week.v1"
        assert plan["start_date"] == "2026-03-02"
        assert len(plan["weeks"]) == 1
        assert len(plan["weeks"][0]["days"]) == 7

        # Collect test sessions
        test_sessions = []
        for day in plan["weeks"][0]["days"]:
            for s in day["sessions"]:
                if s.get("tags", {}).get("test"):
                    test_sessions.append((day["date"], s["session_id"]))
        assert len(test_sessions) == 3
        session_ids = {s[1] for s in test_sessions}
        assert session_ids == {"test_max_hang_5s", "test_max_weighted_pullup", "test_repeater_7_3"}


class TestFingerSpacing:
    def test_finger_spacing(self):
        """max_hang and repeater (both finger) must have >=2 day gap."""
        plan = generate_test_week(
            start_date="2026-03-02",
            availability=_full_availability(),
            allowed_locations=["gym", "home"],
        )
        finger_days = []
        for i, day in enumerate(plan["weeks"][0]["days"]):
            for s in day["sessions"]:
                if s["session_id"] in ("test_max_hang_5s", "test_repeater_7_3"):
                    finger_days.append(i)

        assert len(finger_days) == 2
        assert finger_days[1] - finger_days[0] >= 2, f"Finger days {finger_days} too close"


class TestRespectsAvailability:
    def test_respects_availability(self):
        """Only available days should have sessions."""
        avail = _partial_availability(["mon", "wed", "fri"])
        plan = generate_test_week(
            start_date="2026-03-02",  # Monday
            availability=avail,
            allowed_locations=["gym", "home"],
        )
        for day in plan["weeks"][0]["days"]:
            weekday = day["weekday"]
            if weekday not in ("mon", "wed", "fri"):
                assert len(day["sessions"]) == 0, f"Unexpected session on {weekday}"


class TestFillsEasySessions:
    def test_fills_easy_sessions(self):
        """Non-test available days get prehab/flexibility filler."""
        plan = generate_test_week(
            start_date="2026-03-02",
            availability=_full_availability(),
            allowed_locations=["gym", "home"],
        )
        filler_ids = {"prehab_maintenance", "flexibility_full"}
        for day in plan["weeks"][0]["days"]:
            for s in day["sessions"]:
                if not s.get("tags", {}).get("test"):
                    assert s["session_id"] in filler_ids, f"Unexpected filler: {s['session_id']}"


class TestOutputStructure:
    def test_output_structure(self):
        """Output matches week plan schema."""
        plan = generate_test_week(
            start_date="2026-03-02",
            availability=_full_availability(),
            allowed_locations=["gym"],
        )
        assert "weekly_load_summary" in plan
        assert "total_load" in plan["weekly_load_summary"]
        assert "hard_days_count" in plan["weekly_load_summary"]
        assert "recovery_days_count" in plan["weekly_load_summary"]
        week = plan["weeks"][0]
        assert week["phase"] == "test_week"
        for day in week["days"]:
            assert "date" in day
            assert "weekday" in day
            assert "sessions" in day
            for s in day["sessions"]:
                assert "slot" in s
                assert "session_id" in s
                assert "location" in s
                assert "intensity" in s
                assert "estimated_load_score" in s


# ---------------------------------------------------------------------------
# should_show_test_reminder tests
# ---------------------------------------------------------------------------

class TestReminderFiresAtCorrectWeeks:
    def test_fires_at_week_5_11_17(self):
        state = {}
        # (week_num + 1) % 6 == 0 means weeks 5, 11, 17, 23
        assert should_show_test_reminder(state, 5) is not None
        assert should_show_test_reminder(state, 11) is not None
        assert should_show_test_reminder(state, 17) is not None
        # Should NOT fire at other weeks
        assert should_show_test_reminder(state, 4) is None
        assert should_show_test_reminder(state, 6) is None
        assert should_show_test_reminder(state, 10) is None


class TestReminderPostpone:
    def test_postpone_delays_by_1(self):
        state = {"test_reminder_postponed_to": 6}
        # Week 5 normally fires, but postponed to 6
        assert should_show_test_reminder(state, 5) is None
        # Week 6: the postponed target
        assert should_show_test_reminder(state, 6) is not None


class TestReminderSkip:
    def test_skip_resets_counter(self):
        state = {"test_reminder_skipped_until": 11}
        # Weeks 5 and 6 suppressed
        assert should_show_test_reminder(state, 5) is None
        assert should_show_test_reminder(state, 6) is None
        # Week 11 is the normal trigger and skip_until has expired
        assert should_show_test_reminder(state, 11) is not None
