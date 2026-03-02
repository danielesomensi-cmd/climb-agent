"""Tests for _update_test_from_log — verifies test results flow into assessment.tests."""

from copy import deepcopy

import pytest

from backend.engine.progression_v1 import apply_feedback

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_state(bodyweight: float = 75.0) -> dict:
    return {
        "body": {"weight_kg": bodyweight},
        "bodyweight_kg": bodyweight,
        "assessment": {"tests": {}},
        "working_loads": {"entries": []},
        "tests": {},
        "baselines": {},
    }


def _test_log(date: str, session_id: str, feedback_items: list, planned_sessions: list | None = None) -> dict:
    if planned_sessions is None:
        planned_sessions = [{"session_id": session_id, "tags": {"test": True}, "exercise_instances": []}]
    return {
        "date": date,
        "planned": planned_sessions,
        "actual": {"exercise_feedback_v1": feedback_items},
    }


# ---------------------------------------------------------------------------
# Max hang → assessment.tests
# ---------------------------------------------------------------------------

class TestMaxHangWritesAssessmentTests:
    def test_max_hang_writes_assessment_tests(self):
        state = _base_state(75.0)
        log = _test_log("2026-03-01", "test_max_hang_5s", [
            {"exercise_id": "max_hang_5s", "used_total_load_kg": 100.0, "feedback_label": "ok"},
        ])
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"]["max_hang_20mm_5s_total_kg"] == 100.0

    def test_max_hang_baseline_source_test(self):
        state = _base_state(75.0)
        log = _test_log("2026-03-01", "test_max_hang_5s", [
            {"exercise_id": "max_hang_5s", "used_total_load_kg": 100.0, "feedback_label": "ok"},
        ])
        result = apply_feedback(log, state)
        baselines = result["baselines"]["hangboard"]
        assert baselines[0]["source"] == "test"
        assert baselines[0]["updated_at"] == "2026-03-01"


# ---------------------------------------------------------------------------
# Repeater → assessment.tests + history
# ---------------------------------------------------------------------------

class TestRepeaterWritesHistoryAndAssessment:
    def test_repeater_writes_history_and_assessment(self):
        state = _base_state(75.0)
        log = _test_log("2026-03-02", "test_repeater_7_3", [
            {"exercise_id": "repeater_hang_7_3", "completed_sets": 22, "feedback_label": "ok"},
        ])
        result = apply_feedback(log, state)
        # assessment.tests scalar
        assert result["assessment"]["tests"]["repeater_7_3_max_sets_20mm"] == 22
        # history list
        history = result["tests"]["repeater_strength_endurance"]
        assert len(history) == 1
        assert history[0]["completed_sets"] == 22
        assert history[0]["date"] == "2026-03-02"


# ---------------------------------------------------------------------------
# Weighted pullup → assessment.tests + history
# ---------------------------------------------------------------------------

class TestWeightedPullupWritesHistoryAndAssessment:
    def test_weighted_pullup_writes_history_and_assessment(self):
        state = _base_state(75.0)
        log = _test_log("2026-03-03", "test_max_weighted_pullup", [
            {"exercise_id": "weighted_pullup", "used_total_load_kg": 110.0, "feedback_label": "ok"},
        ])
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"]["weighted_pullup_1rm_total_kg"] == 110.0
        history = result["tests"]["pulling_strength"]
        assert len(history) == 1
        assert history[0]["total_load_kg"] == 110.0

    def test_pullup_external_to_total_derivation(self):
        """When only used_external_load_kg is provided, total is derived from BW."""
        state = _base_state(75.0)
        log = _test_log("2026-03-03", "test_max_weighted_pullup", [
            {"exercise_id": "weighted_pullup", "used_external_load_kg": 35.0, "feedback_label": "ok"},
        ])
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"]["weighted_pullup_1rm_total_kg"] == 110.0
        history = result["tests"]["pulling_strength"]
        assert history[0]["total_load_kg"] == 110.0
        assert history[0]["external_load_kg"] == 35.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestNonTestSessionIgnored:
    def test_non_test_session_ignored(self):
        """Feedback from a regular (non-test) session must not write to assessment.tests."""
        state = _base_state(75.0)
        log = {
            "date": "2026-03-04",
            "planned": [{"session_id": "strength_long", "exercise_instances": []}],
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "max_hang_5s", "used_total_load_kg": 95.0, "feedback_label": "ok"},
                ]
            },
        }
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"].get("max_hang_20mm_5s_total_kg") is None


class TestAppendOnlyHistory:
    def test_append_only_history(self):
        """Second test appends to history, doesn't overwrite."""
        state = _base_state(75.0)
        # First test
        log1 = _test_log("2026-03-01", "test_max_hang_5s", [
            {"exercise_id": "max_hang_5s", "used_total_load_kg": 100.0, "feedback_label": "ok"},
        ])
        state = apply_feedback(log1, state)
        assert len(state["tests"]["max_strength"]) == 1

        # Second test
        log2 = _test_log("2026-03-15", "test_max_hang_5s", [
            {"exercise_id": "max_hang_5s", "used_total_load_kg": 105.0, "feedback_label": "ok"},
        ])
        state = apply_feedback(log2, state)
        assert len(state["tests"]["max_strength"]) == 2
        assert state["tests"]["max_strength"][0]["total_load_kg"] == 100.0
        assert state["tests"]["max_strength"][1]["total_load_kg"] == 105.0


# ---------------------------------------------------------------------------
# Max hang duration → assessment.tests
# ---------------------------------------------------------------------------

class TestMaxHangDurationWritesAssessmentTests:
    def test_max_hang_duration_writes(self):
        state = _base_state(75.0)
        log = _test_log("2026-03-05", "test_max_hang_5s", [
            {"exercise_id": "test_max_hang_duration_20mm", "max_hang_duration_20mm_seconds": 65.0, "feedback_label": "ok"},
        ])
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"]["max_hang_duration_20mm_seconds"] == 65.0


# ---------------------------------------------------------------------------
# L-sit hold → assessment.tests
# ---------------------------------------------------------------------------

class TestLSitHoldWritesAssessmentTests:
    def test_l_sit_hold_writes(self):
        state = _base_state(75.0)
        log = _test_log("2026-03-05", "test_max_weighted_pullup", [
            {"exercise_id": "test_l_sit_hold", "l_sit_hold_seconds": 22.0, "feedback_label": "ok"},
        ])
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"]["l_sit_hold_seconds"] == 22.0


# ---------------------------------------------------------------------------
# Hip flexibility → assessment.tests
# ---------------------------------------------------------------------------

class TestHipFlexibilityWritesAssessmentTests:
    def test_hip_flexibility_writes(self):
        state = _base_state(75.0)
        log = _test_log("2026-03-05", "test_max_hang_5s", [
            {"exercise_id": "test_hip_flexibility", "hip_flexibility_cm": 125.0, "feedback_label": "ok"},
        ])
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"]["hip_flexibility_cm"] == 125.0


# ---------------------------------------------------------------------------
# Scalar latest-wins
# ---------------------------------------------------------------------------

class TestAssessmentScalarLatestWins:
    def test_assessment_scalar_latest_wins(self):
        """Latest test overwrites the scalar in assessment.tests."""
        state = _base_state(75.0)
        # First test
        log1 = _test_log("2026-03-01", "test_max_hang_5s", [
            {"exercise_id": "max_hang_5s", "used_total_load_kg": 100.0, "feedback_label": "ok"},
        ])
        state = apply_feedback(log1, state)
        assert state["assessment"]["tests"]["max_hang_20mm_5s_total_kg"] == 100.0

        # Second test with higher value
        log2 = _test_log("2026-03-15", "test_max_hang_5s", [
            {"exercise_id": "max_hang_5s", "used_total_load_kg": 108.0, "feedback_label": "ok"},
        ])
        state = apply_feedback(log2, state)
        assert state["assessment"]["tests"]["max_hang_20mm_5s_total_kg"] == 108.0
