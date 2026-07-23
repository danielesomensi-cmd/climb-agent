"""Tests for B302 — grade ladder includes 5a+/5b+/5c+.

The lead grade picker (frontend LEAD_GRADES) offers 5a+/5b+/5c+, but the engine
ladder (assessment_v1.GRADE_ORDER) was missing them, so grade_index() raised
"Unknown grade" → assessment compute crashed → no profile → no plan. Real users
targeting/climbing those beginner grades (e.g. ferrero: max 5a+, target 5c+)
could not generate a plan.

Also verifies:
- outdoor load weights are UNCHANGED for existing grades (behavior-preserving),
- the new grade-5 half-steps get sensible outdoor weights,
- BOULDER_TO_LEAD maps the boulder + variants onto grades present in the ladder.
"""

import unittest

from backend.engine.assessment_v1 import GRADE_ORDER, grade_index, grade_gap
from backend.engine.grade_mapping import BOULDER_TO_LEAD
from backend.engine.outdoor_log import _GRADE_WEIGHT, compute_outdoor_load_score


class TestGradeLadder(unittest.TestCase):
    def test_plus_variants_present(self):
        for g in ("5a+", "5b+", "5c+"):
            self.assertIn(g, GRADE_ORDER, f"{g} missing from GRADE_ORDER")

    def test_grade_index_no_longer_raises(self):
        # The exact crash reported for ferrero.
        self.assertIsInstance(grade_index("5c+"), int)
        self.assertIsInstance(grade_index("5a+"), int)

    def test_ordering_is_monotonic(self):
        seq = ["5a", "5a+", "5b", "5b+", "5c", "5c+", "6a", "6a+"]
        idxs = [grade_index(g) for g in seq]
        self.assertEqual(idxs, sorted(idxs))
        self.assertEqual(len(idxs), len(set(idxs)))

    def test_grade_gap_consistent(self):
        # Half-grade steps: 5c+ is one step above 5c, two above 5b+.
        self.assertEqual(grade_gap("5c+", "5c"), 1)
        self.assertEqual(grade_gap("5c+", "5b+"), 2)
        self.assertEqual(grade_gap("6a", "5c+"), 1)


class TestAssessmentAndPlanForBeginner(unittest.TestCase):
    """The ferrero scenario end-to-end: max 5a+, target 5c+ → profile + plan."""

    def _state(self):
        return {
            "goal": {
                "deadline": "",
                "goal_type": "lead_grade",
                "discipline": "lead",
                "total_weeks": 12,
                "target_grade": "5c+",
                "target_style": "redpoint",
                "current_grade": "5b",
            },
            "assessment": {
                "grades": {"lead_max_os": "5a+", "lead_max_rp": "5b"},
                "experience": {"climbing_years": 2, "structured_training_years": 0},
                "self_eval": {"primary_weakness": "technique_errors"},
                "body": {},
            },
        }

    def test_assessment_profile_computes(self):
        from backend.engine.assessment_v1 import compute_assessment_profile
        st = self._state()
        profile = compute_assessment_profile(st["assessment"], st["goal"])
        self.assertIsInstance(profile, dict)
        # 5-axis profile present
        for axis in ("finger_strength", "endurance", "technique"):
            self.assertIn(axis, profile)

    def test_macrocycle_generates(self):
        from backend.engine.assessment_v1 import compute_assessment_profile
        from backend.engine.macrocycle_v1 import generate_macrocycle
        st = self._state()
        profile = compute_assessment_profile(st["assessment"], st["goal"])
        mc = generate_macrocycle(st["goal"], profile, st, "2026-07-20", 12)
        self.assertTrue(mc.get("phases"))


class TestOutdoorWeightBehaviorPreserving(unittest.TestCase):
    def test_existing_grade_weights_unchanged(self):
        # These were the pre-B302 values (grade_index_old + 3).
        self.assertEqual(_GRADE_WEIGHT["5a"], 3)
        self.assertEqual(_GRADE_WEIGHT["5b"], 4)
        self.assertEqual(_GRADE_WEIGHT["5c"], 5)
        self.assertEqual(_GRADE_WEIGHT["6a"], 6)
        self.assertEqual(_GRADE_WEIGHT["7a"], 12)

    def test_new_plus_variants_fold_onto_base(self):
        self.assertEqual(_GRADE_WEIGHT["5a+"], _GRADE_WEIGHT["5a"])
        self.assertEqual(_GRADE_WEIGHT["5b+"], _GRADE_WEIGHT["5b"])
        self.assertEqual(_GRADE_WEIGHT["5c+"], _GRADE_WEIGHT["5c"])

    def test_5cplus_no_longer_unknown_in_outdoor(self):
        # Before B302 a 5c+ route fell to _UNKNOWN_GRADE_WEIGHT=10 (mis-weighted
        # as harder than 6c). Now it scores like the beginner grade it is.
        entry = {"routes": [{"grade": "5c+", "style": "redpoint"}], "duration_minutes": 120}
        score = compute_outdoor_load_score(entry)
        self.assertGreater(score, 0)
        self.assertLess(score, 10)


class TestBoulderMapping(unittest.TestCase):
    def test_boulder_plus_variants_map_to_valid_lead_grades(self):
        for b in ("5A+", "5B+", "5C+"):
            self.assertIn(b, BOULDER_TO_LEAD)
            self.assertIn(BOULDER_TO_LEAD[b], GRADE_ORDER)


if __name__ == "__main__":
    unittest.main()
