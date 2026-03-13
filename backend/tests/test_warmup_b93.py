"""Tests for B93 — warmup instruction_only blocks + exercise variety."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.engine.resolve_session import resolve_session, pick_best_exercise_p0, load_json

REPO_ROOT = os.path.join(os.path.dirname(__file__), "../..")
TEMPLATES_DIR = "backend/catalog/templates/v1"
EXERCISES_PATH = "backend/catalog/exercises/v1/exercises.json"


def _user_state():
    return {
        "assessment": {
            "profile": {
                "finger_strength": 50,
                "pulling_strength": 50,
                "power_endurance": 50,
                "technique": 50,
                "endurance": 50,
                "body_composition": 50,
            }
        },
        "bodyweight_kg": 75,
        "equipment": {
            "gyms": [
                {
                    "gym_id": "test_gym",
                    "name": "Test Gym",
                    "equipment": [
                        "hangboard",
                        "pullup_bar",
                        "resistance_band",
                        "dumbbell",
                        "campus_board",
                    ],
                    "priority": 1,
                }
            ]
        },
        "baselines": {},
        "working_loads": {"entries": [], "rules": {}},
        "context": {"gym_id": "test_gym", "location": "gym"},
    }


def _resolve(session_name="strength_long"):
    return resolve_session(
        repo_root=REPO_ROOT,
        session_path=f"backend/catalog/sessions/v1/{session_name}.json",
        templates_dir=TEMPLATES_DIR,
        exercises_path=EXERCISES_PATH,
        out_path="/dev/null",
        user_state_override=_user_state(),
        write_output=False,
    )


class TestWarmupBlocksResolveExercises:
    """B124: warmup blocks now resolve to real exercises (no longer instruction_only)."""

    def test_warmup_blocks_resolve_to_exercises(self):
        """pulse_raise and mobility blocks must resolve real exercises with exercise_id."""
        result = _resolve()
        blocks = result["resolved_session"]["blocks"]

        pulse = next((b for b in blocks if b["block_id"] == "pulse_raise"), None)
        assert pulse is not None, "pulse_raise block not found in output"
        assert pulse["status"] == "selected"
        assert len(pulse.get("selected_exercises", [])) == 1, "pulse_raise should select 1 exercise"
        assert pulse["selected_exercises"][0]["exercise_id"] == "general_pulse_raise"

        mobility = next((b for b in blocks if b["block_id"] == "mobility"), None)
        assert mobility is not None, "mobility block not found in output"
        assert mobility["status"] == "selected"
        assert len(mobility.get("selected_exercises", [])) == 1, "mobility should select 1 exercise"
        assert mobility["selected_exercises"][0]["exercise_id"] == "dynamic_mobility_flow"

    def test_pulse_raise_has_work_seconds(self):
        """pulse_raise exercise must have work_seconds in prescription for timer."""
        result = _resolve()
        instances = result["resolved_session"]["exercise_instances"]
        pulse_inst = next((e for e in instances if e["exercise_id"] == "general_pulse_raise"), None)
        assert pulse_inst is not None, "general_pulse_raise not in exercise_instances"
        rx = pulse_inst.get("prescription", {})
        assert rx.get("work_seconds", 0) > 0, "general_pulse_raise must have work_seconds for timer"

    def test_mobility_has_work_seconds(self):
        """mobility exercise must have work_seconds in prescription for timer."""
        result = _resolve()
        instances = result["resolved_session"]["exercise_instances"]
        mob_inst = next((e for e in instances if e["exercise_id"] == "dynamic_mobility_flow"), None)
        assert mob_inst is not None, "dynamic_mobility_flow not in exercise_instances"
        rx = mob_inst.get("prescription", {})
        assert rx.get("work_seconds", 0) > 0, "dynamic_mobility_flow must have work_seconds for timer"


class TestWarmupVariety:
    """Verify that warmup exercise selection varies with recent_ex_ids."""

    def test_variety_with_recent_ids(self):
        """When recent_ex_ids contains the alphabetically-first candidate,
        a different exercise must be selected for upper_activation."""
        exercises_raw = load_json(os.path.join(REPO_ROOT, EXERCISES_PATH))
        exercises = exercises_raw["exercises"] if isinstance(exercises_raw, dict) else exercises_raw

        # First call without recent_ex_ids — should pick band_external_rotation (alphabetical)
        ex1, _ = pick_best_exercise_p0(
            exercises=exercises,
            location="gym",
            available_equipment=["hangboard", "pullup_bar", "resistance_band", "dumbbell"],
            role_req=["warmup", "prehab"],
            domain_req=["prehab_shoulder"],
            recent_ex_ids=[],
        )
        assert ex1 is not None
        first_id = ex1["id"]

        # Second call with first_id in recent_ex_ids — must pick a different one
        ex2, _ = pick_best_exercise_p0(
            exercises=exercises,
            location="gym",
            available_equipment=["hangboard", "pullup_bar", "resistance_band", "dumbbell"],
            role_req=["warmup", "prehab"],
            domain_req=["prehab_shoulder"],
            exclude_ids={first_id},
            recent_ex_ids=[first_id],
        )
        assert ex2 is not None
        assert ex2["id"] != first_id, (
            f"Expected different exercise after excluding {first_id}, got {ex2['id']}"
        )

    def test_intra_session_dedup_works(self):
        """Within a single resolve call, the same exercise should not appear in
        both warmup upper_activation and antagonist shoulder_prehab blocks."""
        result = _resolve()
        instances = result["resolved_session"]["exercise_instances"]

        warmup_block = [e for e in instances if e["block_uid"] == "warmup_climbing.upper_activation"]
        prehab_block = [e for e in instances if e["block_uid"] == "antagonist_prehab.shoulder_prehab"]

        if warmup_block and prehab_block:
            warmup_id = warmup_block[0]["exercise_id"]
            prehab_id = prehab_block[0]["exercise_id"]
            assert warmup_id != prehab_id, (
                f"Same exercise {warmup_id} in both warmup and prehab blocks — intra-session dedup failed"
            )
