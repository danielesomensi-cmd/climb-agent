"""Tests for D38: Brzycki 1RM estimation and pulling_strength integration."""

import unittest

from backend.engine.assessment_v1 import brzycki_1rm, compute_assessment_profile


class TestBrzycki1RM(unittest.TestCase):
    """Unit tests for the Brzycki formula."""

    def test_1_rep_returns_weight(self):
        self.assertAlmostEqual(brzycki_1rm(100.0, 1), 100.0)

    def test_5_reps(self):
        # 100 * 36 / (37 - 5) = 100 * 36/32 = 112.5
        self.assertAlmostEqual(brzycki_1rm(100.0, 5), 112.5)

    def test_10_reps(self):
        # 80 * 36 / (37 - 10) = 80 * 36/27 ≈ 106.67
        self.assertAlmostEqual(brzycki_1rm(80.0, 10), 80 * 36 / 27, places=1)

    def test_0_reps_returns_zero(self):
        self.assertEqual(brzycki_1rm(100.0, 0), 0.0)

    def test_37_reps_safe(self):
        """37 reps would cause division by zero — returns weight safely."""
        self.assertEqual(brzycki_1rm(100.0, 37), 100.0)

    def test_high_reps_safe(self):
        """Very high reps should not crash."""
        self.assertEqual(brzycki_1rm(100.0, 50), 100.0)


class TestPullingStrengthBrzycki(unittest.TestCase):
    """D38: pulling_strength should use Brzycki when direct 1RM is missing."""

    def _make_assessment(self, **test_overrides):
        tests = {
            "max_hang_20mm_5s_total_kg": None,
            "weighted_pullup_1rm_total_kg": None,
            "repeater_7_3_max_sets_20mm": None,
            "last_test_date": "2026-02-14",
        }
        tests.update(test_overrides)
        return {
            "body": {"weight_kg": 70.0, "height_cm": 175},
            "experience": {"climbing_years": 5, "structured_training_years": 2},
            "grades": {"lead_max_rp": "7b", "lead_max_os": "6c+"},
            "tests": tests,
            "self_eval": {"primary_weakness": "technique_errors", "secondary_weakness": "pump_too_early"},
        }

    def _goal(self):
        return {"target_grade": "7c+", "current_grade": "7b"}

    def test_direct_1rm_used_when_available(self):
        """Direct 1RM takes precedence over submaximal."""
        assessment = self._make_assessment(
            weighted_pullup_1rm_total_kg=95.0,
            pullup_submaximal_reps=5,
            pullup_submaximal_load_kg=20,
        )
        profile = compute_assessment_profile(assessment, self._goal())
        # Should use direct 1RM (95kg), not Brzycki
        self.assertIsInstance(profile["pulling_strength"], int)

    def test_brzycki_used_when_no_direct_1rm(self):
        """When no direct 1RM, Brzycki estimation from submaximal data."""
        # BW=70, submaximal: 5 reps at +20kg → total weight = 90kg
        # Brzycki: 90 * 36 / (37-5) = 90 * 36/32 = 101.25 → 1RM ≈ 101.3
        assessment = self._make_assessment(
            pullup_submaximal_reps=5,
            pullup_submaximal_load_kg=20,
        )
        profile = compute_assessment_profile(assessment, self._goal())
        self.assertIsInstance(profile["pulling_strength"], int)
        self.assertGreater(profile["pulling_strength"], 0)

    def test_brzycki_gives_higher_score_than_grade_estimate(self):
        """Brzycki with good data should score higher than grade-only estimate."""
        grade_only = self._make_assessment()
        with_brzycki = self._make_assessment(
            pullup_submaximal_reps=5,
            pullup_submaximal_load_kg=25,
        )
        goal = self._goal()
        p1 = compute_assessment_profile(grade_only, goal)
        p2 = compute_assessment_profile(with_brzycki, goal)
        self.assertGreater(p2["pulling_strength"], p1["pulling_strength"])

    def test_no_data_still_works(self):
        """No pulling test data at all → falls back to grade estimate."""
        assessment = self._make_assessment()
        profile = compute_assessment_profile(assessment, self._goal())
        self.assertGreater(profile["pulling_strength"], 0)
        self.assertLessEqual(profile["pulling_strength"], 100)


if __name__ == "__main__":
    unittest.main()
