"""Tests for B133 — Repeater test protocol fixes.

- test_repeater_7_3_to_failure exercise exists with correct attrs
- Template uses new exercise, not repeater_hang_7_3
- LP repeater test has reps=40
- Progression records completed_reps from new exercise
"""
import json
import pytest
from pathlib import Path

EXERCISES_PATH = Path("backend/catalog/exercises/v1/exercises.json")
TEMPLATE_PATH = Path("backend/catalog/templates/v1/finger_strength_endurance_test.json")


@pytest.fixture(scope="module")
def exercises():
    data = json.loads(EXERCISES_PATH.read_text())
    return {e["id"]: e for e in data["exercises"]}


@pytest.fixture(scope="module")
def template():
    return json.loads(TEMPLATE_PATH.read_text())


class TestNewRepeaterTestExercise:
    """B133: test_repeater_7_3_to_failure catalog entry."""

    def test_exercise_exists(self, exercises):
        assert "test_repeater_7_3_to_failure" in exercises

    def test_intensity_pct_60(self, exercises):
        ex = exercises["test_repeater_7_3_to_failure"]
        assert ex["attributes"]["intensity_pct"] == 0.60

    def test_prescription_1_set_40_reps(self, exercises):
        ex = exercises["test_repeater_7_3_to_failure"]
        pd = ex["prescription_defaults"]
        assert pd["sets"] == 1
        assert pd["reps"] == 40
        assert pd["work_seconds"] == 7
        assert pd["rest_between_reps_seconds"] == 3

    def test_role_is_test(self, exercises):
        ex = exercises["test_repeater_7_3_to_failure"]
        assert "test" in ex["role"]

    def test_load_model_total_load(self, exercises):
        ex = exercises["test_repeater_7_3_to_failure"]
        assert ex["load_model"] == "total_load"


class TestLpRepeaterTestFix:
    """B133: lp_repeater_test reps fix."""

    def test_reps_is_40(self, exercises):
        ex = exercises["lp_repeater_test"]
        assert ex["prescription_defaults"]["reps"] == 40

    def test_intensity_pct_60(self, exercises):
        ex = exercises["lp_repeater_test"]
        assert ex["attributes"]["intensity_pct"] == 0.60


class TestTemplateUsesNewExercise:
    """B133: HB test template uses test_repeater_7_3_to_failure."""

    def test_main_block_exercise(self, template):
        main_block = next(b for b in template["blocks"] if b["block_id"] == "main")
        assert main_block["exercise_id"] == "test_repeater_7_3_to_failure"

    def test_main_block_not_old_exercise(self, template):
        main_block = next(b for b in template["blocks"] if b["block_id"] == "main")
        assert main_block["exercise_id"] != "repeater_hang_7_3"


class TestProgressionRecordsReps:
    """B133: progression_v1 records completed_reps from new exercise."""

    def _base_state(self):
        return {
            "body": {"weight_kg": 70},
            "bodyweight_kg": 70,
            "assessment": {"tests": {}},
            "working_loads": {"entries": []},
            "tests": {},
            "baselines": {},
        }

    def _log(self, exercise_id, **fields):
        return {
            "date": "2026-03-19",
            "planned": [{"session_id": "test_repeater_7_3", "tags": {"test": True}, "exercise_instances": []}],
            "actual": {"exercise_feedback_v1": [{"exercise_id": exercise_id, "feedback_label": "ok", **fields}]},
        }

    def test_new_exercise_records_reps(self):
        from backend.engine.progression_v1 import apply_feedback

        result = apply_feedback(
            self._log("test_repeater_7_3_to_failure", completed_reps=14),
            self._base_state(),
        )
        assert result["assessment"]["tests"]["repeater_7_3_max_sets_20mm"] == 14

    def test_legacy_exercise_still_works(self):
        from backend.engine.progression_v1 import apply_feedback

        result = apply_feedback(
            self._log("repeater_hang_7_3", completed_sets=3),
            self._base_state(),
        )
        assert result["assessment"]["tests"]["repeater_7_3_max_sets_20mm"] == 3
