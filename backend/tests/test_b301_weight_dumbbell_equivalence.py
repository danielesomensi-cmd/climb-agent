"""Tests for B301 — weight ≡ dumbbell equivalence.

Before B301 the free-weight expansion was one-directional: dumbbell/kettlebell/
barbell → "weight", but a user who ticked only "Weight plates" ("weight") never
got "dumbbell", so the two strength sessions gated on ["dumbbell"]
(heavy_conditioning_gym, lower_body_gym) were unreachable for them.

B301 makes the whole free-weight family interchangeable for planning: any of
{weight, dumbbell, kettlebell, barbell} implies BOTH "weight" and "dumbbell".

7 tests:
1. weight (plates) → implies dumbbell
2. weight (plates) → still implies weight (idempotent tag)
3. dumbbell → implies weight (unchanged B159 behaviour)
4. barbell → implies both weight and dumbbell
5. kettlebell → implies both weight and dumbbell
6. no double-add when dumbbell already present
7. planner: a weight-plates-only gym can be served the dumbbell strength sessions
"""

import unittest

from backend.engine.equipment_utils import expand_equipment
from backend.engine.planner_v2 import _SESSION_META, _equipment_for_location


class TestWeightDumbbellEquivalence(unittest.TestCase):
    def test_weight_implies_dumbbell(self):
        eq = expand_equipment(["weight", "gym_boulder"])
        self.assertIn("dumbbell", eq)

    def test_weight_still_implies_weight(self):
        eq = expand_equipment(["weight"])
        self.assertIn("weight", eq)

    def test_dumbbell_implies_weight(self):
        # B159 behaviour preserved
        eq = expand_equipment(["dumbbell"])
        self.assertIn("weight", eq)
        self.assertIn("dumbbell", eq)

    def test_barbell_implies_both(self):
        eq = expand_equipment(["barbell"])
        self.assertIn("weight", eq)
        self.assertIn("dumbbell", eq)

    def test_kettlebell_implies_both(self):
        eq = expand_equipment(["kettlebell"])
        self.assertIn("weight", eq)
        self.assertIn("dumbbell", eq)

    def test_no_double_add(self):
        eq = expand_equipment(["dumbbell", "weight"])
        self.assertEqual(eq.count("dumbbell"), 1)
        self.assertEqual(eq.count("weight"), 1)

    def test_no_weight_no_dumbbell(self):
        """A gym with no free weights at all gets neither tag."""
        eq = expand_equipment(["gym_boulder", "hangboard"])
        self.assertNotIn("weight", eq)
        self.assertNotIn("dumbbell", eq)

    def test_strength_sessions_reachable_with_plates_only(self):
        """The two dumbbell-gated strength sessions must be selectable for a
        user whose gym only has weight plates."""
        avail = expand_equipment(["gym_boulder", "weight"])
        avail_set = set(avail)
        for sid in ("heavy_conditioning_gym", "lower_body_gym"):
            meta = _SESSION_META.get(sid)
            self.assertIsNotNone(meta, f"{sid} missing from _SESSION_META")
            req = set(meta.get("required_equipment") or [])
            self.assertTrue(
                req.issubset(avail_set),
                f"{sid} requires {req}, not satisfied by plates-only gym {avail_set}",
            )


if __name__ == "__main__":
    unittest.main()
