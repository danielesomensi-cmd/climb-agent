"""C243 — Gate climbing technique drills by equipment (catalog retag).

Source: D248 audit, root cause L3 (catalog mistag). ~10 wall technique drills
were equipment-ungated in exercises.json, so they survived the equipment filter
at a no-wall gym and leaked into the `climbing_movement` block (tie-break →
`breathing_awareness`).

These tests lock the invariant: a wall drill must declare its climbing-surface
requirement (`equipment_required_any`) so the existing equipment filter drops it
when no wall is available — and still resolves it when a wall is present.
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
SESSION_PATH = "backend/catalog/sessions/v1/strength_long.json"
TEMPLATES_DIR = "backend/catalog/templates/v1"

# The 10 wall technique drills gated by C243 (full list confirmed against catalog).
GATED_DRILLS = {
    "breathing_awareness", "foothold_stare", "hip_rotation_drill", "hover_hands",
    "one_hand_climbing", "sloth_monkey", "sticky_feet", "straight_arms",
    "tap_and_place", "three_limb_drill",
}

CLIMBING_SURFACES = {
    "gym_boulder", "board_kilter", "board_moonboard",
    "board_other", "spraywall", "homewall", "gym_routes",
}

NO_WALL_GYM = ["pullup_bar", "dumbbell", "band", "bench"]
WALL_GYM = ["pullup_bar", "dumbbell", "gym_boulder", "hangboard"]


def _resolve_strength_long(gym_equipment, gym_id="g1"):
    state = {
        "context": {"location": "gym", "gym_id": gym_id},
        "equipment": {
            "gyms": [{"gym_id": gym_id, "priority": 1, "equipment": gym_equipment}],
            "home": [],
        },
        "assessment": {"grades": {"boulder_max_rp": "7C"}},
        "defaults": {"location": "gym"},
    }
    return resolve_session(
        repo_root=REPO_ROOT,
        session_path=SESSION_PATH,
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


def _block(resolved, block_id):
    for blk in resolved["resolved_session"]["blocks"]:
        if blk.get("block_id") == block_id:
            return blk
    return None


class TestC243CatalogInvariant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(EXERCISES_PATH, "r", encoding="utf-8") as f:
            cls.by_id = {e["id"]: e for e in json.load(f)["exercises"]}

    def test_all_gated_drills_declare_a_climbing_surface(self):
        for eid in GATED_DRILLS:
            ex = self.by_id[eid]
            any_eq = set(ex.get("equipment_required_any") or [])
            self.assertTrue(
                any_eq & CLIMBING_SURFACES,
                f"{eid} must declare a climbing surface in equipment_required_any "
                f"(got {sorted(any_eq)})",
            )

    def test_no_role_technique_drill_is_equipment_ungated(self):
        # The original L3 leak class: a role=technique drill with neither
        # equipment_required nor equipment_required_any survives any filter.
        offenders = []
        for ex in self.by_id.values():
            if "technique" not in [str(r) for r in (ex.get("role") or [])]:
                continue
            if not (ex.get("equipment_required") or ex.get("equipment_required_any")):
                offenders.append(ex["id"])
        self.assertEqual(
            offenders, [],
            f"equipment-ungated role=technique drills (L3 leak surface): {offenders}",
        )


class TestC243ResolverGating(unittest.TestCase):
    def test_no_wall_gym_surfaces_no_wall_drill(self):
        resolved = _resolve_strength_long(NO_WALL_GYM)
        self.assertEqual(resolved.get("resolution_status"), "success")

        leaked = [x for x in _selected_ids(resolved) if x in GATED_DRILLS]
        self.assertEqual(leaked, [], f"wall drills leaked at no-wall gym: {leaked}")

        # climbing_movement (required=false) degrades gracefully → skipped, no error.
        cm = _block(resolved, "climbing_movement")
        self.assertIsNotNone(cm)
        self.assertEqual(cm.get("status"), "skipped")
        self.assertEqual(cm.get("selected_exercises"), [])

    def test_wall_gym_still_surfaces_a_technique_drill(self):
        resolved = _resolve_strength_long(WALL_GYM, gym_id="g2")
        self.assertEqual(resolved.get("resolution_status"), "success")

        cm = _block(resolved, "climbing_movement")
        self.assertIsNotNone(cm)
        self.assertEqual(cm.get("status"), "selected")
        ids = [se.get("exercise_id") for se in cm.get("selected_exercises", [])]
        self.assertEqual(len(ids), 1, f"expected one technique drill, got {ids}")


if __name__ == "__main__":
    unittest.main()
