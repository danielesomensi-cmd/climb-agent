"""E2E tests for guided test session → assessment.tests update.

Simulates the complete flow that happens when a user finishes a test session
in the guided session UI:

    resolve_session
        → guided execution (sets / reps / load input)
        → submit feedback payload (exercise_feedback_v1)
        → apply_feedback()            [progression_v1]
        → _update_test_from_log()     [progression_v1, internal]
        → assessment.tests updated    (scalar + append-only history)
        → compute_assessment_profile() picks up new data → scores change

Each test class maps to one of the six scenarios in the spec.
"""

from copy import deepcopy

import pytest

from backend.engine.assessment_v1 import compute_assessment_profile
from backend.engine.progression_v1 import apply_feedback

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _base_state(bodyweight: float = 75.0) -> dict:
    """Full user_state suitable for both apply_feedback() and compute_assessment_profile()."""
    return {
        "body": {"weight_kg": bodyweight},
        "bodyweight_kg": bodyweight,
        "assessment": {
            "body": {"weight_kg": bodyweight},
            "experience": {"climbing_years": 5, "structured_training_years": 2},
            "grades": {
                "lead_max_rp": "7c",
                "lead_max_os": "7a+",
                "boulder_max_os": "7b",
            },
            "tests": {},
            "self_eval": {},
        },
        "working_loads": {"entries": []},
        "tests": {},
        "baselines": {},
    }


def _test_session_log(date: str, session_id: str, feedback_items: list) -> dict:
    """Build a log_entry representing a completed guided test session."""
    return {
        "date": date,
        "planned": [
            {
                "session_id": session_id,
                "tags": {"test": True},
                "exercise_instances": [],
            }
        ],
        "actual": {"exercise_feedback_v1": feedback_items},
    }


def _goal(target_grade: str = "8b", current_grade: str = "7c") -> dict:
    return {"target_grade": target_grade, "current_grade": current_grade}


# ---------------------------------------------------------------------------
# Test 1 — Max hang updates finger strength baseline
# ---------------------------------------------------------------------------


class TestMaxHangUpdatesFingerstrengtBaseline:
    """
    User completes test_max_hang_5s.
    Payload: used_external_load_kg=20.0, used_total_load_kg=95.0 (BW=75).
    """

    def _run(self) -> dict:
        state = _base_state(75.0)
        log = _test_session_log(
            "2026-03-03",
            "test_max_hang_5s",
            [
                {
                    "exercise_id": "max_hang_5s",
                    "used_external_load_kg": 20.0,
                    "used_total_load_kg": 95.0,
                    "feedback_label": "ok",
                }
            ],
        )
        return apply_feedback(log, state)

    def test_assessment_tests_max_hang_total_kg(self):
        result = self._run()
        assert result["assessment"]["tests"]["max_hang_20mm_5s_total_kg"] == 95.0

    def test_hangboard_baseline_max_total_load_kg(self):
        result = self._run()
        baseline = result["baselines"]["hangboard"][0]
        assert baseline["max_total_load_kg"] == 95.0

    def test_hangboard_baseline_source_is_test(self):
        result = self._run()
        baseline = result["baselines"]["hangboard"][0]
        assert baseline["source"] == "test"

    def test_hangboard_baseline_updated_at(self):
        result = self._run()
        baseline = result["baselines"]["hangboard"][0]
        assert baseline["updated_at"] == "2026-03-03"


# ---------------------------------------------------------------------------
# Test 2 — Repeater updates PE scalar + append-only history
# ---------------------------------------------------------------------------


class TestRepeaterUpdatesPEScalar:
    """
    User completes test_repeater_7_3 (completed_sets=8).
    A second test two weeks later appends to history (two entries total).
    """

    def test_repeater_scalar_written(self):
        state = _base_state(75.0)
        log = _test_session_log(
            "2026-03-03",
            "test_repeater_7_3",
            [{"exercise_id": "repeater_hang_7_3", "completed_sets": 8, "feedback_label": "ok"}],
        )
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"]["repeater_7_3_max_sets_20mm"] == 8

    def test_second_test_appends_history(self):
        """Two sequential test sessions → history list has exactly 2 entries."""
        state = _base_state(75.0)

        # First session
        log1 = _test_session_log(
            "2026-03-03",
            "test_repeater_7_3",
            [{"exercise_id": "repeater_hang_7_3", "completed_sets": 8, "feedback_label": "ok"}],
        )
        state = apply_feedback(log1, state)
        assert len(state["tests"]["repeater_strength_endurance"]) == 1

        # Second session two weeks later
        log2 = _test_session_log(
            "2026-03-17",
            "test_repeater_7_3",
            [{"exercise_id": "repeater_hang_7_3", "completed_sets": 10, "feedback_label": "ok"}],
        )
        state = apply_feedback(log2, state)
        history = state["tests"]["repeater_strength_endurance"]

        assert len(history) == 2
        assert history[0]["completed_sets"] == 8
        assert history[1]["completed_sets"] == 10

    def test_scalar_latest_wins(self):
        """The scalar in assessment.tests is overwritten by the most recent result."""
        state = _base_state(75.0)
        log1 = _test_session_log(
            "2026-03-03",
            "test_repeater_7_3",
            [{"exercise_id": "repeater_hang_7_3", "completed_sets": 8, "feedback_label": "ok"}],
        )
        state = apply_feedback(log1, state)
        assert state["assessment"]["tests"]["repeater_7_3_max_sets_20mm"] == 8

        log2 = _test_session_log(
            "2026-03-17",
            "test_repeater_7_3",
            [{"exercise_id": "repeater_hang_7_3", "completed_sets": 10, "feedback_label": "ok"}],
        )
        state = apply_feedback(log2, state)
        assert state["assessment"]["tests"]["repeater_7_3_max_sets_20mm"] == 10


# ---------------------------------------------------------------------------
# Test 3 — Weighted pullup updates pulling strength
# ---------------------------------------------------------------------------


class TestWeightedPullupUpdatesPullingStrength:
    """
    User completes test_max_weighted_pullup.
    Payload: used_external_load_kg=30.0, used_total_load_kg=105.0 (BW=75).
    """

    def _run(self) -> dict:
        state = _base_state(75.0)
        log = _test_session_log(
            "2026-03-03",
            "test_max_weighted_pullup",
            [
                {
                    "exercise_id": "weighted_pullup",
                    "used_external_load_kg": 30.0,
                    "used_total_load_kg": 105.0,
                    "feedback_label": "ok",
                }
            ],
        )
        return apply_feedback(log, state)

    def test_assessment_tests_weighted_pullup_total_kg(self):
        result = self._run()
        assert result["assessment"]["tests"]["weighted_pullup_1rm_total_kg"] == 105.0

    def test_pullup_history_entry_total_load(self):
        result = self._run()
        history = result["tests"]["pulling_strength"]
        assert len(history) == 1
        assert history[0]["total_load_kg"] == 105.0

    def test_pullup_history_entry_external_load(self):
        result = self._run()
        history = result["tests"]["pulling_strength"]
        assert history[0]["external_load_kg"] == 30.0


# ---------------------------------------------------------------------------
# Test 4 — Measurement exercises update assessment.tests
# ---------------------------------------------------------------------------


class TestMeasurementExercisesWriteToAssessmentTests:
    """
    max_hang_duration_20mm and hip_flexibility exercises in a test session
    each write an independent scalar to assessment.tests.
    """

    def test_both_measurements_written_in_same_session(self):
        state = _base_state(75.0)
        log = _test_session_log(
            "2026-03-03",
            "test_max_hang_5s",
            [
                {
                    "exercise_id": "test_max_hang_duration_20mm",
                    "max_hang_duration_20mm_seconds": 72.0,
                    "feedback_label": "ok",
                },
                {
                    "exercise_id": "test_hip_flexibility",
                    "hip_flexibility_cm": 110.0,
                    "feedback_label": "ok",
                },
            ],
        )
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"]["max_hang_duration_20mm_seconds"] == 72.0
        assert result["assessment"]["tests"]["hip_flexibility_cm"] == 110.0

    def test_missing_hip_flexibility_does_not_affect_duration(self):
        """One measurement missing → the other is still written correctly."""
        state = _base_state(75.0)
        log = _test_session_log(
            "2026-03-03",
            "test_max_hang_5s",
            [
                {
                    "exercise_id": "test_max_hang_duration_20mm",
                    "max_hang_duration_20mm_seconds": 72.0,
                    "feedback_label": "ok",
                }
            ],
        )
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"]["max_hang_duration_20mm_seconds"] == 72.0
        assert "hip_flexibility_cm" not in result["assessment"]["tests"]


# ---------------------------------------------------------------------------
# Test 5 — Full E2E: feedback → recompute profile → scores change
# ---------------------------------------------------------------------------


class TestFullE2EProfileUpdatesAfterFeedback:
    """
    Verifies the complete closed loop:

        1. Compute profile from grades only (no test data) → baseline score.
        2. Apply test session feedback with a strong result.
        3. Recompute profile from updated assessment.tests → score must increase.
    """

    def test_finger_strength_score_increases_after_strong_hang_test(self):
        """
        BW=75, target=8b.
        Grade-only finger baseline: (grade_idx("7c")/grade_idx("8b")) * 70 ≈ 57.
        With 1.6×BW = 120kg total: ratio/benchmark(8b)=1.6/1.6 → score 100.
        """
        bw = 75.0
        state = _base_state(bw)
        goal = _goal(target_grade="8b", current_grade="7c")

        # Baseline profile — no test data
        profile_before = compute_assessment_profile(state["assessment"], goal)
        baseline_finger = profile_before["finger_strength"]

        # Apply test feedback: 1.6× BW (strong for 8b target)
        total_load = round(1.6 * bw, 1)  # 120.0
        log = _test_session_log(
            "2026-03-03",
            "test_max_hang_5s",
            [
                {
                    "exercise_id": "max_hang_5s",
                    "used_total_load_kg": total_load,
                    "feedback_label": "ok",
                }
            ],
        )
        result = apply_feedback(log, state)

        # Recompute with updated assessment.tests
        profile_after = compute_assessment_profile(result["assessment"], goal)

        assert profile_after["finger_strength"] > baseline_finger

    def test_pulling_strength_score_increases_after_pullup_test(self):
        """
        BW=75, target=8a.
        Grade-only pulling baseline: (grade_idx("7b+")/grade_idx("8a")) * 65 ≈ 52.
        With 1.6×BW = 120kg total: ratio/benchmark(8a)=1.6/1.55 → score 100 (clamped).
        """
        bw = 75.0
        state = _base_state(bw)
        goal = _goal(target_grade="8a", current_grade="7b+")

        profile_before = compute_assessment_profile(state["assessment"], goal)
        baseline_pulling = profile_before["pulling_strength"]

        total_load = round(1.6 * bw, 1)  # 120.0
        log = _test_session_log(
            "2026-03-03",
            "test_max_weighted_pullup",
            [
                {
                    "exercise_id": "weighted_pullup",
                    "used_total_load_kg": total_load,
                    "feedback_label": "ok",
                }
            ],
        )
        result = apply_feedback(log, state)

        profile_after = compute_assessment_profile(result["assessment"], goal)

        assert profile_after["pulling_strength"] > baseline_pulling

    def test_profile_before_and_after_are_distinct_objects(self):
        """apply_feedback() returns a new deep-copied state; original is unmodified."""
        bw = 75.0
        state = _base_state(bw)
        goal = _goal()
        original_tests = deepcopy(state["assessment"]["tests"])

        log = _test_session_log(
            "2026-03-03",
            "test_max_hang_5s",
            [{"exercise_id": "max_hang_5s", "used_total_load_kg": 95.0, "feedback_label": "ok"}],
        )
        result = apply_feedback(log, state)

        # Original state must be untouched
        assert state["assessment"]["tests"] == original_tests
        # Result has the new data
        assert "max_hang_20mm_5s_total_kg" in result["assessment"]["tests"]


# ---------------------------------------------------------------------------
# Test 6 — Empty or non-test payloads must not write to assessment.tests
# ---------------------------------------------------------------------------


class TestNoWriteForEmptyOrNonTestPayloads:
    """
    _update_test_from_log() is a no-op when the feedback payload contains
    no exercise_feedback_v1 items, or none with a recognised test exercise ID.
    An exercise from a regular (non-test) session must also be ignored.
    """

    def test_empty_feedback_list_in_test_session(self):
        """Test session submitted with an empty exercise list → assessment.tests stays {}."""
        state = _base_state(75.0)
        log = _test_session_log("2026-03-03", "test_max_hang_5s", [])
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"] == {}

    def test_unrecognised_exercise_id_in_test_session(self):
        """Unknown exercise_id in a test session → assessment.tests stays {}."""
        state = _base_state(75.0)
        log = _test_session_log(
            "2026-03-03",
            "test_max_hang_5s",
            [
                {
                    "exercise_id": "some_random_exercise",
                    "used_total_load_kg": 80.0,
                    "feedback_label": "ok",
                }
            ],
        )
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"] == {}

    def test_test_exercise_in_regular_session_does_not_write(self):
        """
        max_hang_5s feedback in a non-test session (strength_long) must not
        write to assessment.tests even though the exercise_id is recognised.
        """
        state = _base_state(75.0)
        log = {
            "date": "2026-03-03",
            "planned": [{"session_id": "strength_long", "exercise_instances": []}],
            "actual": {
                "exercise_feedback_v1": [
                    {
                        "exercise_id": "max_hang_5s",
                        "used_total_load_kg": 95.0,
                        "feedback_label": "ok",
                    }
                ]
            },
        }
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"].get("max_hang_20mm_5s_total_kg") is None

    def test_missing_required_field_skips_exercise(self):
        """
        max_hang_5s item without used_total_load_kg must be silently skipped;
        no partial write to assessment.tests.
        """
        state = _base_state(75.0)
        log = _test_session_log(
            "2026-03-03",
            "test_max_hang_5s",
            [
                {
                    "exercise_id": "max_hang_5s",
                    # used_total_load_kg intentionally absent
                    "feedback_label": "ok",
                }
            ],
        )
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"].get("max_hang_20mm_5s_total_kg") is None


# ---------------------------------------------------------------------------
# Test 7 — session_id fallback when planned field is missing
# ---------------------------------------------------------------------------


def _no_planned_log(date: str, session_id: str, feedback_items: list) -> dict:
    """Build a log_entry WITHOUT the planned field (simulates frontend bug)."""
    return {
        "date": date,
        "session_id": session_id,
        "actual": {"exercise_feedback_v1": feedback_items},
    }


class TestSessionIdFallbackNoPlannedField:
    """
    The frontend guided session UI does not send the ``planned`` field.
    ``_update_test_from_log()`` must fall back to the top-level ``session_id``
    to decide whether this is a test session.
    """

    def test_max_hang_writes_without_planned(self):
        state = _base_state(75.0)
        log = _no_planned_log(
            "2026-03-03",
            "test_max_hang_5s",
            [{"exercise_id": "max_hang_5s", "used_total_load_kg": 95.0, "feedback_label": "ok"}],
        )
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"]["max_hang_20mm_5s_total_kg"] == 95.0

    def test_repeater_writes_without_planned(self):
        state = _base_state(75.0)
        log = _no_planned_log(
            "2026-03-03",
            "test_repeater_7_3",
            [{"exercise_id": "repeater_hang_7_3", "completed_sets": 8, "feedback_label": "ok"}],
        )
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"]["repeater_7_3_max_sets_20mm"] == 8

    def test_weighted_pullup_writes_without_planned(self):
        state = _base_state(75.0)
        log = _no_planned_log(
            "2026-03-03",
            "test_max_weighted_pullup",
            [{"exercise_id": "weighted_pullup", "used_total_load_kg": 105.0, "feedback_label": "ok"}],
        )
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"]["weighted_pullup_1rm_total_kg"] == 105.0

    def test_non_test_session_id_still_blocked(self):
        """A non-test session_id (e.g. strength_long) must not write to assessment.tests."""
        state = _base_state(75.0)
        log = _no_planned_log(
            "2026-03-03",
            "strength_long",
            [{"exercise_id": "max_hang_5s", "used_total_load_kg": 95.0, "feedback_label": "ok"}],
        )
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"].get("max_hang_20mm_5s_total_kg") is None

    def test_no_session_id_no_planned_still_blocked(self):
        """No session_id and no planned → assessment.tests stays empty."""
        state = _base_state(75.0)
        log = {
            "date": "2026-03-03",
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "max_hang_5s", "used_total_load_kg": 95.0, "feedback_label": "ok"}
                ]
            },
        }
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"].get("max_hang_20mm_5s_total_kg") is None
