"""B253: tests for assessment.tests_source backfill migration.

Pre-D214 legacy user_state lacks the tests_source sidecar. The migration
infers measurement status from tests.* append-only history.
"""
from backend.engine.migrations.m001_backfill_tests_source import migrate


def _legacy_state_with_max_hang(exercise_id: str = "max_hang_5s") -> dict:
    """Legacy state: no tests_source key, but tests.max_strength has a real entry."""
    return {
        "assessment": {
            "tests": {
                "max_hang_20mm_5s_total_kg": 120,
                "max_hang_20mm_7s_total_kg": 120,
            },
            # NOTE: no tests_source — this is the pre-D214 shape
        },
        "tests": {
            "max_strength": [{
                "date": "2026-03-17",
                "exercise_id": exercise_id,
                "total_load_kg": 120.0,
                "external_load_kg": 43.0,
                "bodyweight_kg": 77.0,
                "test_id": "max_hang_5s_total_load",
                "confidence": "high",
            }],
        },
    }


class TestBackfillMaxHang:
    def test_max_hang_5s_marks_both_keys(self):
        state = _legacy_state_with_max_hang("max_hang_5s")
        assert migrate(state) is True
        src = state["assessment"]["tests_source"]
        assert src["max_hang_20mm_5s_total_kg"] == "measured"
        assert src["max_hang_20mm_7s_total_kg"] == "measured"

    def test_max_hang_7s_marks_both_keys(self):
        state = _legacy_state_with_max_hang("max_hang_7s")
        assert migrate(state) is True
        src = state["assessment"]["tests_source"]
        assert src["max_hang_20mm_5s_total_kg"] == "measured"
        assert src["max_hang_20mm_7s_total_kg"] == "measured"

    def test_ignores_unrelated_exercise(self):
        state = _legacy_state_with_max_hang("dead_hang_easy")
        assert migrate(state) is False
        assert "tests_source" not in state["assessment"]


class TestBackfillRepeater:
    def test_repeater_history_marks_scalar(self):
        state = {
            "assessment": {"tests": {"repeater_7_3_max_sets_20mm": 25}},
            "tests": {
                "repeater_strength_endurance": [{
                    "date": "2026-03-19",
                    "test_id": "repeater_7_3_max_reps",
                    "exercise_id": "test_repeater_7_3_to_failure",
                    "completed_reps": 25,
                }],
            },
        }
        assert migrate(state) is True
        assert state["assessment"]["tests_source"]["repeater_7_3_max_sets_20mm"] == "measured"


class TestBackfillPulling:
    def test_pulling_history_marks_2rm_scalar(self):
        state = {
            "assessment": {"tests": {"weighted_pullup_2rm_total_kg": 100}},
            "tests": {
                "pulling_strength": [{
                    "date": "2026-03-13",
                    "test_id": "weighted_pullup_2rm",
                    "total_load_kg": 100.0,
                }],
            },
        }
        assert migrate(state) is True
        assert state["assessment"]["tests_source"]["weighted_pullup_2rm_total_kg"] == "measured"


class TestBackfillIdempotence:
    def test_running_twice_is_noop_second_time(self):
        state = _legacy_state_with_max_hang("max_hang_5s")
        first = migrate(state)
        second = migrate(state)
        assert first is True
        assert second is False  # no change on rerun

    def test_existing_measured_not_overwritten_or_marked_changed(self):
        state = _legacy_state_with_max_hang("max_hang_5s")
        state["assessment"]["tests_source"] = {
            "max_hang_20mm_5s_total_kg": "measured",
            "max_hang_20mm_7s_total_kg": "measured",
        }
        assert migrate(state) is False  # already measured, no work to do


class TestBackfillSafety:
    def test_no_history_is_noop(self):
        # No top-level "tests" key → migration is a pure no-op (no side effects).
        state = {"assessment": {"tests": {}}}
        assert migrate(state) is False
        assert "tests_source" not in state["assessment"]

    def test_missing_assessment_is_noop(self):
        state = {"tests": {"max_strength": [{"exercise_id": "max_hang_5s"}]}}
        assert migrate(state) is False

    def test_post_d214_state_is_noop(self):
        # Post-D214 onboarded user: tests_source already populated, no tests.* history yet
        state = {
            "assessment": {
                "tests": {"max_hang_20mm_7s_total_kg": 130},
                "tests_source": {
                    "max_hang_20mm_7s_total_kg": "measured",
                    "max_hang_20mm_5s_total_kg": "measured",
                },
            },
        }
        assert migrate(state) is False

    def test_estimated_onboarding_with_no_history_stays_estimated(self):
        # Pre-D214 user who never completed a test: tests.* exists from
        # onboarding form but no max_strength history. Must NOT be promoted
        # to "measured" (the value was a user-typed estimate from a grade).
        state = {
            "assessment": {"tests": {"max_hang_20mm_7s_total_kg": 100}},
            "tests": {},  # no history — never tested in-app
        }
        assert migrate(state) is False
        assert "tests_source" not in state["assessment"]

    def test_handles_non_dict_input(self):
        assert migrate(None) is False  # type: ignore[arg-type]
        assert migrate([]) is False  # type: ignore[arg-type]
        assert migrate({"assessment": "not_a_dict"}) is False
