"""A193: hangboard implies pullup_bar in equipment expansion.

A hangboard is always mounted on either a doorframe pullup bar or a dedicated
bar — the two cannot be separated in practice. Users who list only "hangboard"
in their home equipment should still be able to resolve exercises that require
"pullup_bar" (front lever progressions, toes-to-bar, knees-to-elbows, etc).

loading_pin is NOT a pullup_bar implier: it is a ground-based weight alternative
for finger training that does not require a bar.
"""

from __future__ import annotations

import unittest

from backend.engine.equipment_utils import (
    PULLUP_BAR_IMPLIERS,
    expand_equipment,
)
from backend.engine.resolve_session import pick_best_exercise_p0


class TestExpandEquipmentHangboard(unittest.TestCase):
    def test_hangboard_implies_pullup_bar(self):
        eq = expand_equipment(["hangboard"])
        self.assertIn("pullup_bar", eq)

    def test_hangboard_20mm_implies_pullup_bar(self):
        eq = expand_equipment(["hangboard_20mm"])
        self.assertIn("pullup_bar", eq)

    def test_loading_pin_does_not_imply_pullup_bar(self):
        # loading_pin is a ground-based alternative, not a bar
        eq = expand_equipment(["loading_pin"])
        self.assertNotIn("pullup_bar", eq)

    def test_idempotent_when_pullup_bar_already_present(self):
        eq = expand_equipment(["hangboard", "pullup_bar"])
        self.assertEqual(eq.count("pullup_bar"), 1)

    def test_no_hangboard_no_implication(self):
        eq = expand_equipment(["dumbbell", "band"])
        self.assertNotIn("pullup_bar", eq)

    def test_pullup_bar_impliers_set_is_stable(self):
        # Guard against accidental inclusion of loading_pin or other items.
        self.assertEqual(
            PULLUP_BAR_IMPLIERS,
            frozenset({"hangboard", "hangboard_20mm"}),
        )


class TestResolverP0WithHangboardOnly(unittest.TestCase):
    """Integration: pick_best_exercise_p0 must accept pullup_bar exercises
    when the user only lists hangboard in home equipment."""

    def _exercises(self):
        return [
            {
                "id": "knees_to_elbows",
                "role": ["accessory"],
                "domain": ["core"],
                "pattern": "compression",
                "equipment_required": ["pullup_bar"],
                "equipment_required_any": [],
                "location_allowed": ["home", "gym"],
            },
            {
                "id": "v_up",
                "role": ["accessory"],
                "domain": ["core"],
                "pattern": "compression",
                "equipment_required": [],
                "equipment_required_any": [],
                "location_allowed": ["home", "gym"],
            },
        ]

    def test_pullup_bar_exercise_selectable_with_hangboard_only(self):
        """With only hangboard → pullup_bar is implied → knees_to_elbows passes P0."""
        available = expand_equipment(["hangboard"])
        self.assertIn("pullup_bar", available)

        picked, _trace = pick_best_exercise_p0(
            exercises=self._exercises(),
            location="home",
            available_equipment=available,
            role_req=["accessory"],
            domain_req=["core"],
            pattern_req=["compression"],
        )
        self.assertIsNotNone(picked)
        # knees_to_elbows wins deterministic tie-break (alphabetical on id)
        self.assertEqual(picked["id"], "knees_to_elbows")

    def test_pullup_bar_exercise_rejected_without_hangboard_or_bar(self):
        """Sanity check: without hangboard OR pullup_bar, the bar exercise is filtered out."""
        available = expand_equipment(["dumbbell", "band"])
        self.assertNotIn("pullup_bar", available)

        picked, _trace = pick_best_exercise_p0(
            exercises=self._exercises(),
            location="home",
            available_equipment=available,
            role_req=["accessory"],
            domain_req=["core"],
            pattern_req=["compression"],
        )
        # Only v_up (bodyweight, no equipment) is selectable
        self.assertIsNotNone(picked)
        self.assertEqual(picked["id"], "v_up")


if __name__ == "__main__":
    unittest.main()
