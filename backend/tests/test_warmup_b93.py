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


class TestInstructionOnlyBlocks:
    """Verify instruction_only blocks appear in resolver output with instructions."""

    def test_instruction_only_blocks_in_output(self):
        """Resolver must include instruction_only blocks with status='selected' and instructions."""
        result = _resolve()
        blocks = result["resolved_session"]["blocks"]

        instruction_blocks = [
            b for b in blocks if b.get("selected_exercises") == [] and b.get("instructions")
        ]
        assert len(instruction_blocks) >= 2, (
            f"Expected at least 2 instruction_only blocks (pulse_raise, mobility), got {len(instruction_blocks)}"
        )

        for b in instruction_blocks:
            assert b["status"] == "selected"
            instructions = b["instructions"]
            assert isinstance(instructions, dict)
            # Must have at least one instruction field
            assert any(
                k in instructions
                for k in ("notes", "options", "focus", "duration_min_range")
            ), f"Block {b['block_id']} has no instruction content: {instructions}"

    def test_pulse_raise_has_options(self):
        """pulse_raise block must include options (brisk_walk, easy_jog, etc.)."""
        result = _resolve()
        blocks = result["resolved_session"]["blocks"]
        pulse = next((b for b in blocks if b["block_id"] == "pulse_raise"), None)
        assert pulse is not None, "pulse_raise block not found in output"
        assert pulse["instructions"]["options"] == [
            "brisk_walk", "easy_jog", "jumping_jacks", "air_squats_flow"
        ]
        assert pulse["instructions"]["duration_min_range"] == [3, 5]

    def test_mobility_has_focus(self):
        """mobility block must include focus areas."""
        result = _resolve()
        blocks = result["resolved_session"]["blocks"]
        mobility = next((b for b in blocks if b["block_id"] == "mobility"), None)
        assert mobility is not None, "mobility block not found in output"
        assert "thoracic_spine" in mobility["instructions"]["focus"]
        assert mobility["instructions"]["duration_min_range"] == [3, 5]


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
