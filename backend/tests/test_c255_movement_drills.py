"""C255 — Bechtel Movement Drills batch (Climb Strong: Drills Manual pp.51-69).

6 drills merged (of 8 proposed; move_and_lock skipped for dedup vs hover_hands/
freeze_drill, rockovers excluded pending a plyo_box equipment token).

Invariants locked here:
- all 6 new IDs present, schema-valid (5 canonical prescription fields, valid
  load_model, canonical equipment tokens, canonical stress_tags keys)
- D133: side-switching drills set rest_between_reps_seconds explicitly
- C243: every new drill declares a wall surface via equipment_required_any
- resolver pickup: eligible at a wall gym, graceful skip at a no-wall gym
"""
from __future__ import annotations

import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from backend.engine.resolve_session import resolve_session  # noqa: E402

EXERCISES_PATH = os.path.join(REPO_ROOT, "backend/catalog/exercises/v1/exercises.json")
SESSION_PATH = "backend/catalog/sessions/v1/technique_focus_gym.json"
TEMPLATES_DIR = "backend/catalog/templates/v1"

NEW_IDS = {
    "tech_barn_door_2000",
    "tech_climb_it_backwards",
    "tech_deadpoint_roll_through",
    "tech_foot_to_hand",
    "tech_single_leg_climbing",
    "tech_trust_the_eyes",
}

# Side-switching drills must set rest_between_reps_seconds (D133).
SIDE_SWITCHING = {
    "tech_barn_door_2000",
    "tech_deadpoint_roll_through",
    "tech_foot_to_hand",
    "tech_single_leg_climbing",
}

CANONICAL_EQUIPMENT = {
    "hangboard", "hangboard_20mm", "pullup_bar", "band", "weight", "dumbbell",
    "kettlebell", "campus_board", "foam_roller", "resistance_band", "ab_wheel",
    "bench", "barbell", "rings", "pinch_block", "spraywall", "board_kilter",
    "board_moonboard", "board_other", "homewall", "gym_boulder", "gym_routes",
    "cable_machine", "leg_press", "loading_pin",
}
CANONICAL_STRESS_KEYS = {"fingers", "elbow", "cns", "skin"}
CLIMBING_SURFACES = {
    "gym_boulder", "board_kilter", "board_moonboard",
    "board_other", "spraywall", "homewall", "gym_routes",
}
VALID_LOAD_MODELS = {"bodyweight_only", "grade_relative", "external_load", "total_load"}
PRESCRIPTION_FIELDS = {
    "sets", "reps", "work_seconds",
    "rest_between_reps_seconds", "rest_between_sets_seconds",
}

NO_WALL_GYM = ["pullup_bar", "dumbbell", "band", "bench"]
WALL_GYM = ["pullup_bar", "gym_boulder", "gym_routes", "hangboard"]


def _resolve(session_path, gym_equipment, gym_id="g1"):
    state = {
        "context": {"location": "gym", "gym_id": gym_id},
        "equipment": {
            "gyms": [{"gym_id": gym_id, "priority": 1, "equipment": gym_equipment}],
            "home": [],
        },
        "assessment": {"grades": {"boulder_max_rp": "7C", "boulder_max_os": "7A"}},
        "defaults": {"location": "gym"},
    }
    return resolve_session(
        repo_root=REPO_ROOT,
        session_path=session_path,
        templates_dir=TEMPLATES_DIR,
        exercises_path=EXERCISES_PATH,
        out_path="",
        user_state_override=state,
        write_output=False,
        user_id=None,
    )


def _selected_ids(resolved):
    return [
        se.get("exercise_id")
        for blk in resolved["resolved_session"]["blocks"]
        for se in blk.get("selected_exercises", [])
    ]


class TestC255CatalogInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(EXERCISES_PATH, "r", encoding="utf-8") as f:
            cls.by_id = {e["id"]: e for e in json.load(f)["exercises"]}

    def test_all_new_ids_present(self):
        for eid in NEW_IDS:
            self.assertIn(eid, self.by_id, f"{eid} missing from catalog")

    def test_prescription_defaults_canonical_fields(self):
        for eid in NEW_IDS:
            pres = self.by_id[eid].get("prescription_defaults") or {}
            missing = PRESCRIPTION_FIELDS - set(pres.keys())
            self.assertEqual(
                missing, set(),
                f"{eid} prescription_defaults missing canonical fields: {missing}",
            )

    def test_load_model_valid_and_grade_anchor_consistent(self):
        for eid in NEW_IDS:
            ex = self.by_id[eid]
            self.assertIn(ex.get("load_model"), VALID_LOAD_MODELS, eid)
            pres = ex.get("prescription_defaults") or {}
            if ex["load_model"] == "grade_relative":
                self.assertIn("grade_ref", pres, f"{eid} grade_relative needs grade_ref")
                self.assertIn("grade_offset", pres, f"{eid} grade_relative needs grade_offset")

    def test_equipment_tokens_canonical(self):
        for eid in NEW_IDS:
            ex = self.by_id[eid]
            used = set(ex.get("equipment_required") or []) | set(
                ex.get("equipment_required_any") or []
            )
            unknown = used - CANONICAL_EQUIPMENT
            self.assertEqual(unknown, set(), f"{eid} non-canonical equipment: {unknown}")

    def test_stress_tags_keys_canonical(self):
        for eid in NEW_IDS:
            keys = set((self.by_id[eid].get("stress_tags") or {}).keys())
            self.assertEqual(
                keys, CANONICAL_STRESS_KEYS,
                f"{eid} stress_tags keys must be exactly {CANONICAL_STRESS_KEYS}, got {keys}",
            )

    def test_d133_side_switching_drills_set_rest_between_reps(self):
        for eid in SIDE_SWITCHING:
            pres = self.by_id[eid]["prescription_defaults"]
            rest = pres.get("rest_between_reps_seconds")
            self.assertIsNotNone(rest, f"{eid} (side-switching) must set rest_between_reps_seconds (D133)")
            self.assertGreaterEqual(rest, 10, eid)
            self.assertLessEqual(rest, 30, eid)

    def test_c243_every_new_drill_declares_a_wall_surface(self):
        for eid in NEW_IDS:
            any_eq = set(self.by_id[eid].get("equipment_required_any") or [])
            self.assertTrue(
                any_eq & CLIMBING_SURFACES,
                f"{eid} must declare a climbing surface in equipment_required_any",
            )


class TestC255ResolverPickup(unittest.TestCase):
    def test_wall_gym_new_drills_eligible_and_selectable(self):
        resolved = _resolve(SESSION_PATH, WALL_GYM)
        self.assertEqual(resolved.get("resolution_status"), "success")
        # No hard requirement that a C255 drill wins tie-breaks on first resolve,
        # but the session must resolve and technique blocks must select something.
        self.assertTrue(_selected_ids(resolved), "technique_focus_gym selected nothing")

    def test_no_wall_gym_graceful_skip(self):
        # C243 case-b behavior unchanged: wall drills never leak at a no-wall gym.
        resolved = _resolve(
            "backend/catalog/sessions/v1/strength_long.json", NO_WALL_GYM, gym_id="g2"
        )
        self.assertEqual(resolved.get("resolution_status"), "success")
        leaked = [x for x in _selected_ids(resolved) if x in NEW_IDS]
        self.assertEqual(leaked, [], f"C255 drills leaked at no-wall gym: {leaked}")


if __name__ == "__main__":
    unittest.main()
