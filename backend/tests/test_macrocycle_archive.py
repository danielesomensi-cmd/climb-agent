"""Tests for backend.engine.macrocycle_archive (A-NEW-MACRO)."""

from __future__ import annotations

from copy import deepcopy

from backend.engine.macrocycle_archive import archive_current_macrocycle


def _make_macrocycle(start: str = "2026-02-02", end: str = "2026-04-26") -> dict:
    return {
        "macrocycle_version": "macrocycle.v1",
        "generated_at": "2026-02-01T10:00:00",
        "start_date": start,
        "end_date": end,
        "total_weeks": 12,
        "goal_snapshot": {
            "discipline": "lead",
            "target_grade": "8a",
            "deadline": "2026-09-15",
        },
        "assessment_snapshot": {
            "finger_strength": 60, "pulling_strength": 55,
            "power_endurance": 50, "technique": 65, "endurance": 55,
        },
        "phases": [
            {"phase_id": "base", "duration_weeks": 4},
            {"phase_id": "strength_power", "duration_weeks": 3},
            {"phase_id": "power_endurance", "duration_weeks": 2},
            {"phase_id": "performance", "duration_weeks": 2},
            {"phase_id": "deload", "duration_weeks": 1},
        ],
    }


def _make_state_with_logs() -> dict:
    return {
        "goal": {"discipline": "lead", "target_grade": "8a"},
        "macrocycle": _make_macrocycle(),
        "session_completion_log": [
            {"date": "2026-02-03", "session_id": "endurance_aerobic_gym", "status": "done"},
            {"date": "2026-02-05", "session_id": "test_max_hang_7s", "status": "done"},
            {"date": "2026-02-08", "session_id": "boulder_circuit_gym", "status": "skipped"},
            {"date": "2026-03-02", "session_id": "limit_boulder_gym", "status": "done"},
            # Out-of-window entry — must be ignored.
            {"date": "2026-01-15", "session_id": "old_session", "status": "done"},
            # After-window entry — must be ignored.
            {"date": "2026-05-01", "session_id": "future_session", "status": "done"},
        ],
        "week_plans": {
            "2026-02-02": {
                "weeks": [{"days": [
                    {"date": "2026-02-02", "sessions": [{"session_id": "x"}, {"session_id": "y"}]},
                    {"date": "2026-02-04", "sessions": [{"session_id": "z"}]},
                ]}],
            },
            # Out-of-window plan — should not contribute to sessions_planned.
            "2025-12-01": {
                "weeks": [{"days": [{"date": "2025-12-01", "sessions": [{"session_id": "old"}]}]}],
            },
        },
    }


# ── Empty / missing state ──────────────────────────────────────────────────


class TestEmptyState:
    def test_empty_state_initializes_history(self):
        state = {}
        result = archive_current_macrocycle(state)
        assert result is state  # in-place mutation
        assert state["macrocycle_history"] == []

    def test_no_macrocycle_keeps_history_empty(self):
        state = {"goal": {"discipline": "lead"}}
        archive_current_macrocycle(state)
        assert state["macrocycle_history"] == []

    def test_macrocycle_without_dates_archives_with_zero_counts(self):
        # Edge case: malformed macrocycle without start/end dates.
        state = {"macrocycle": {"phases": [{"phase_id": "base"}]}}
        archive_current_macrocycle(state)
        assert len(state["macrocycle_history"]) == 1
        summary = state["macrocycle_history"][0]["completion_summary"]
        assert summary["sessions_done"] == 0
        assert summary["sessions_skipped"] == 0


# ── Valid cycle ────────────────────────────────────────────────────────────


class TestValidCycle:
    def test_archive_appends_one_entry(self):
        state = _make_state_with_logs()
        archive_current_macrocycle(state)
        assert len(state["macrocycle_history"]) == 1

    def test_archived_entry_shape(self):
        state = _make_state_with_logs()
        archive_current_macrocycle(state)
        entry = state["macrocycle_history"][0]
        assert set(entry.keys()) == {
            "archived_at",
            "macrocycle",
            "goal_at_archive",
            "weeks_completed",
            "total_weeks",
            "completion_summary",
        }
        assert entry["total_weeks"] == 12
        assert entry["macrocycle"]["start_date"] == "2026-02-02"

    def test_completion_summary_counts_correctly(self):
        state = _make_state_with_logs()
        archive_current_macrocycle(state)
        summary = state["macrocycle_history"][0]["completion_summary"]
        # In-window: 3 done + 1 skipped (out-of-window entries ignored).
        assert summary["sessions_done"] == 3
        assert summary["sessions_skipped"] == 1
        # Test detection: only test_max_hang_7s in-window.
        assert summary["tests_completed"] == [
            {"session_id": "test_max_hang_7s", "date": "2026-02-05"},
        ]
        # Phases extracted.
        assert summary["phases_completed"] == [
            "base", "strength_power", "power_endurance", "performance", "deload",
        ]
        # Sessions planned: 3 from in-window plan, 0 from out-of-window plan.
        assert summary["sessions_planned"] == 3

    def test_macrocycle_snapshot_is_deep_copy(self):
        """Mutating the state's macrocycle after archive must not affect history."""
        state = _make_state_with_logs()
        archive_current_macrocycle(state)
        original_phase_count = len(state["macrocycle_history"][0]["macrocycle"]["phases"])
        # Mutate live macrocycle.
        state["macrocycle"]["phases"].append({"phase_id": "junk"})
        # History entry untouched.
        assert len(state["macrocycle_history"][0]["macrocycle"]["phases"]) == original_phase_count

    def test_goal_at_archive_is_deep_copy(self):
        state = _make_state_with_logs()
        archive_current_macrocycle(state)
        # Mutate live goal after archive.
        state["goal"]["target_grade"] = "9a"
        assert state["macrocycle_history"][0]["goal_at_archive"]["target_grade"] == "8a"

    def test_session_completion_log_unchanged(self):
        """Archive must NOT mutate session_completion_log (read-only)."""
        state = _make_state_with_logs()
        before = deepcopy(state["session_completion_log"])
        archive_current_macrocycle(state)
        assert state["session_completion_log"] == before


# ── Idempotency and chaining ───────────────────────────────────────────────


class TestChaining:
    def test_two_calls_produce_two_entries(self):
        """archive_current_macrocycle is NOT idempotent — caller must call once per replacement."""
        state = _make_state_with_logs()
        archive_current_macrocycle(state)
        archive_current_macrocycle(state)
        assert len(state["macrocycle_history"]) == 2

    def test_history_grows_when_new_macrocycle_arrives(self):
        """Simulate: archive cycle 1, then cycle 1 is replaced, then archive cycle 2."""
        state = _make_state_with_logs()
        archive_current_macrocycle(state)
        # Replace current macrocycle (as the caller would do post-archive).
        state["macrocycle"] = _make_macrocycle(start="2026-04-27", end="2026-07-19")
        archive_current_macrocycle(state)
        assert len(state["macrocycle_history"]) == 2
        assert state["macrocycle_history"][0]["macrocycle"]["start_date"] == "2026-02-02"
        assert state["macrocycle_history"][1]["macrocycle"]["start_date"] == "2026-04-27"


# ── weeks_completed ─────────────────────────────────────────────────────────


class TestWeeksCompleted:
    def test_weeks_completed_caps_at_total_weeks(self):
        # Cycle from 2020 — way more than total_weeks have elapsed.
        state = {
            "macrocycle": {
                "start_date": "2020-01-06",
                "end_date": "2020-03-29",
                "total_weeks": 12,
            },
        }
        archive_current_macrocycle(state)
        assert state["macrocycle_history"][0]["weeks_completed"] == 12

    def test_weeks_completed_zero_for_future_cycle(self):
        state = {
            "macrocycle": {
                "start_date": "2099-01-05",
                "end_date": "2099-03-30",
                "total_weeks": 12,
            },
        }
        archive_current_macrocycle(state)
        assert state["macrocycle_history"][0]["weeks_completed"] == 0
