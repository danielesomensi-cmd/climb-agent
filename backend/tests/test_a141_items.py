"""Tests for A141 items: fall practice exercise + phase rationale keys."""

import json
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXERCISES_PATH = os.path.join(REPO_ROOT, "backend", "catalog", "exercises", "v1", "exercises.json")


def _load_exercises() -> list[dict]:
    with open(EXERCISES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["exercises"]


class TestFallPracticeExercise:
    """Verify fall_practice exercise is in the catalog and properly configured."""

    def test_exercise_exists(self):
        exercises = _load_exercises()
        fall = [e for e in exercises if e["id"] == "fall_practice"]
        assert len(fall) == 1, "fall_practice exercise not found in catalog"

    def test_requires_lead_wall(self):
        exercises = _load_exercises()
        fall = next(e for e in exercises if e["id"] == "fall_practice")
        assert "lead_wall" in fall.get("equipment_required_any", []), \
            "fall_practice should require lead_wall in equipment_required_any"

    def test_gym_only(self):
        exercises = _load_exercises()
        fall = next(e for e in exercises if e["id"] == "fall_practice")
        assert fall["location_allowed"] == ["gym"], \
            "fall_practice should be gym-only"

    def test_technique_category(self):
        exercises = _load_exercises()
        fall = next(e for e in exercises if e["id"] == "fall_practice")
        assert fall["category"] == "technique"
        assert fall["pattern"] == "technique_drill"


class TestPhaseRationaleKeys:
    """Phase rationale keys must match vocabulary phase_ids."""

    def test_all_phases_covered(self):
        # Canonical phase_ids from vocabulary_v1.md
        canonical_phases = {"base", "strength_power", "power_endurance", "performance", "deload"}

        # Import from frontend source — we test the TS file was created with correct keys
        # by reading the file directly
        rationale_path = os.path.join(
            REPO_ROOT, "frontend", "src", "lib", "phase-rationales.ts"
        )
        assert os.path.exists(rationale_path), "phase-rationales.ts not found"

        with open(rationale_path, encoding="utf-8") as f:
            content = f.read()

        for phase_id in canonical_phases:
            assert f'  {phase_id}:' in content or f'"{phase_id}":' in content, \
                f"Phase {phase_id} not found in phase-rationales.ts"
