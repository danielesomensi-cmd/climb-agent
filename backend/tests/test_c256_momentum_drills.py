"""C256 — Bechtel Momentum Drills batch (Climb Strong: Drills Manual pp.72-91).

Final batch 3/3 — Bechtel Drills Manual integration CLOSED (7 + 6 + 10 = 23
merged of 27 processed across C240/C255/C256).

Invariants locked here:
- all 10 new IDs present, schema-valid (5 canonical prescription fields,
  valid load_model + grade anchors, canonical equipment/pattern/stress_tags)
- D133: side-switching entries set rest_between_reps_seconds explicitly
- C243: every new drill declares a wall surface via equipment_required_any
- D80: no campus_board token in any new entry's equipment (campus is
  prose-only tool variant/regression)
- resolver pickup at a wall gym; graceful no-wall skip unchanged
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
TEMPLATES_DIR = "backend/catalog/templates/v1"

NEW_IDS = {
    "tech_contrast_bouldering",
    "tech_foot_flyaways",
    "tech_green_light_red_light",
    "tech_hard_target",
    "tech_hips_first",
    "tech_hop_and_skip",
    "tech_pogo",
    "tech_smooth_is_fast",
    "tech_the_bump",
    "tech_throwing_the_shoe",
}

# Side-switching entries must set rest_between_reps_seconds (D133).
SIDE_SWITCHING = {
    "tech_the_bump": (15, 15),
    "tech_throwing_the_shoe": (15, 15),
    "tech_hard_target": (40, 40),
}

CANONICAL_PATTERNS = {"technique_drill", "climbing_intervals", "explosive_touch"}
CANONICAL_STRESS_KEYS = {"fingers", "elbow", "cns", "skin"}
CANONICAL_EQUIPMENT = {
    "hangboard", "hangboard_20mm", "pullup_bar", "band", "weight", "dumbbell",
    "kettlebell", "campus_board", "foam_roller", "resistance_band", "ab_wheel",
    "bench", "barbell", "rings", "pinch_block", "spraywall", "board_kilter",
    "board_moonboard", "board_other", "homewall", "gym_boulder", "gym_routes",
    "cable_machine", "leg_press", "loading_pin",
}
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
        REPO_ROOT,
        session_path,
        TEMPLATES_DIR,
        EXERCISES_PATH,
        "",
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


class TestC256CatalogInvariants(unittest.TestCase):
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
            self.assertEqual(missing, set(), f"{eid} missing prescription fields: {missing}")

    def test_pattern_canonical(self):
        for eid in NEW_IDS:
            self.assertIn(
                self.by_id[eid].get("pattern"), CANONICAL_PATTERNS,
                f"{eid} pattern must be one of {CANONICAL_PATTERNS}",
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
            self.assertEqual(keys, CANONICAL_STRESS_KEYS, f"{eid} stress_tags keys: {keys}")

    def test_d133_side_switching_rest_between_reps(self):
        for eid, (lo, hi) in SIDE_SWITCHING.items():
            rest = self.by_id[eid]["prescription_defaults"].get("rest_between_reps_seconds")
            self.assertIsNotNone(rest, f"{eid} must set rest_between_reps_seconds (D133)")
            self.assertGreaterEqual(rest, lo, eid)
            self.assertLessEqual(rest, hi, eid)

    def test_c243_every_new_drill_declares_a_wall_surface(self):
        for eid in NEW_IDS:
            any_eq = set(self.by_id[eid].get("equipment_required_any") or [])
            self.assertTrue(
                any_eq & CLIMBING_SURFACES,
                f"{eid} must declare a climbing surface in equipment_required_any",
            )

    def test_d80_no_campus_token_in_new_entries(self):
        for eid in NEW_IDS:
            ex = self.by_id[eid]
            used = set(ex.get("equipment_required") or []) | set(
                ex.get("equipment_required_any") or []
            )
            self.assertNotIn(
                "campus_board", used,
                f"{eid} must not gate on campus_board (D80 — campus is prose-only here)",
            )


class TestC256ResolverPickup(unittest.TestCase):
    def test_wall_gym_session_resolves(self):
        resolved = _resolve(
            "backend/catalog/sessions/v1/technique_focus_gym.json", WALL_GYM
        )
        self.assertEqual(resolved.get("resolution_status"), "success")
        self.assertTrue(_selected_ids(resolved))

    def test_no_wall_gym_graceful_skip(self):
        resolved = _resolve(
            "backend/catalog/sessions/v1/strength_long.json", NO_WALL_GYM, gym_id="g2"
        )
        self.assertEqual(resolved.get("resolution_status"), "success")
        leaked = [x for x in _selected_ids(resolved) if x in NEW_IDS]
        self.assertEqual(leaked, [], f"C256 drills leaked at no-wall gym: {leaked}")


if __name__ == "__main__":
    unittest.main()
