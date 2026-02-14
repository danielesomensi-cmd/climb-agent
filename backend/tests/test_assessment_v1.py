"""Tests for assessment_v1 — profile computation."""

import unittest

from backend.engine.assessment_v1 import (
    GRADE_ORDER,
    compute_assessment_profile,
    grade_gap,
    grade_index,
)


def _make_assessment(
    *,
    weight_kg=77.0,
    height_cm=182,
    body_fat_pct=None,
    climbing_years=5,
    structured_training_years=1,
    boulder_max_rp="7A",
    lead_max_rp="7b",
    lead_max_os="6c+",
    max_hang_total=None,
    weighted_pullup_total=None,
    max_pullups=None,
    primary_weakness="pump_too_early",
    secondary_weakness="technique_errors",
):
    return {
        "body": {
            "weight_kg": weight_kg,
            "height_cm": height_cm,
            "body_fat_pct": body_fat_pct,
        },
        "experience": {
            "climbing_years": climbing_years,
            "structured_training_years": structured_training_years,
        },
        "grades": {
            "boulder_max_rp": boulder_max_rp,
            "lead_max_rp": lead_max_rp,
            "lead_max_os": lead_max_os,
        },
        "tests": {
            "max_hang_20mm_5s_total_kg": max_hang_total,
            "weighted_pullup_1rm_total_kg": weighted_pullup_total,
            "max_pullups_bodyweight": max_pullups,
            "repeater_7_3_max_sets_20mm": None,
            "last_test_date": "2026-02-14",
        },
        "self_eval": {
            "primary_weakness": primary_weakness,
            "secondary_weakness": secondary_weakness,
        },
    }


def _make_goal(target_grade="7c+", current_grade="7b"):
    return {
        "goal_type": "lead_grade",
        "discipline": "lead",
        "target_grade": target_grade,
        "target_style": "redpoint",
        "current_grade": current_grade,
        "deadline": "2026-06-30",
        "override_mode": None,
        "created_at": "2026-02-14",
    }


class TestGradeHelpers(unittest.TestCase):
    def test_grade_gap_same(self):
        self.assertEqual(grade_gap("7a", "7a"), 0)

    def test_grade_gap_positive(self):
        self.assertEqual(grade_gap("7c", "7a"), 4)

    def test_grade_gap_negative(self):
        self.assertEqual(grade_gap("7a", "7c"), -4)

    def test_grade_gap_half_grades(self):
        self.assertEqual(grade_gap("7a+", "7a"), 1)

    def test_grade_index_order(self):
        for i in range(len(GRADE_ORDER) - 1):
            self.assertLess(grade_index(GRADE_ORDER[i]), grade_index(GRADE_ORDER[i + 1]))

    def test_grade_index_unknown_raises(self):
        with self.assertRaises(ValueError):
            grade_index("V10")


class TestAssessmentProfile(unittest.TestCase):
    def test_profile_with_all_tests(self):
        assessment = _make_assessment(
            max_hang_total=100,
            weighted_pullup_total=112,
            body_fat_pct=14,
        )
        goal = _make_goal("7c+", "7b")
        profile = compute_assessment_profile(assessment, goal)
        self.assertEqual(set(profile.keys()), {
            "finger_strength", "pulling_strength", "power_endurance",
            "technique", "endurance", "body_composition",
        })
        for v in profile.values():
            self.assertGreaterEqual(v, 0)
            self.assertLessEqual(v, 100)

    def test_profile_without_tests(self):
        assessment = _make_assessment()  # no test data
        goal = _make_goal("7c+", "7b")
        profile = compute_assessment_profile(assessment, goal)
        for v in profile.values():
            self.assertGreaterEqual(v, 0)
            self.assertLessEqual(v, 100)

    def test_profile_partial_tests(self):
        assessment = _make_assessment(max_hang_total=85)  # only finger test
        goal = _make_goal("7c+", "7b")
        profile = compute_assessment_profile(assessment, goal)
        # Finger should use test data; pulling should estimate
        self.assertIsInstance(profile["finger_strength"], int)
        self.assertIsInstance(profile["pulling_strength"], int)

    def test_finger_score_benchmark_7c(self):
        # 1.25 BW benchmark for 7c. 100kg / 77kg = 1.30 → 1.30/1.25 * 100 = 104 → clamped to 100
        assessment = _make_assessment(max_hang_total=100)
        goal = _make_goal("7c", "7a")
        profile = compute_assessment_profile(assessment, goal)
        self.assertGreaterEqual(profile["finger_strength"], 95)

    def test_finger_score_benchmark_8a(self):
        # 1.40 BW benchmark for 8a. 100kg / 77kg = 1.30 → 1.30/1.40 * 100 ≈ 93
        assessment = _make_assessment(max_hang_total=100)
        goal = _make_goal("8a", "7b")
        profile = compute_assessment_profile(assessment, goal)
        self.assertGreater(profile["finger_strength"], 80)
        self.assertLess(profile["finger_strength"], 100)

    def test_pe_score_high_gap(self):
        # Big OS-RP gap → low PE. 8a+ RP, 7b OS → gap = 5 half grades
        assessment = _make_assessment(lead_max_rp="8a+", lead_max_os="7b")
        goal = _make_goal("8a+", "8a")
        profile = compute_assessment_profile(assessment, goal)
        self.assertLess(profile["power_endurance"], 50)

    def test_pe_score_low_gap(self):
        # Small gap → high PE. 7b RP, 7a+ OS → gap = 1
        assessment = _make_assessment(
            lead_max_rp="7b", lead_max_os="7a+",
            primary_weakness="cant_hold_hard_moves",
            secondary_weakness=None,
        )
        goal = _make_goal("7c", "7a")
        profile = compute_assessment_profile(assessment, goal)
        self.assertGreater(profile["power_endurance"], 60)

    def test_score_clamped_0_100(self):
        # Very strong climber → scores should not exceed 100
        assessment = _make_assessment(max_hang_total=200, weighted_pullup_total=200, body_fat_pct=8)
        goal = _make_goal("7a", "6c+")
        profile = compute_assessment_profile(assessment, goal)
        for k, v in profile.items():
            self.assertGreaterEqual(v, 0, f"{k} below 0")
            self.assertLessEqual(v, 100, f"{k} above 100")

    def test_self_eval_modifier_pump(self):
        # pump_too_early as primary → PE should be lower
        base = _make_assessment(
            lead_max_rp="7b", lead_max_os="6c+",
            primary_weakness="cant_hold_hard_moves",
        )
        with_pump = _make_assessment(
            lead_max_rp="7b", lead_max_os="6c+",
            primary_weakness="pump_too_early",
        )
        goal = _make_goal()
        p1 = compute_assessment_profile(base, goal)
        p2 = compute_assessment_profile(with_pump, goal)
        self.assertLess(p2["power_endurance"], p1["power_endurance"])

    def test_deterministic(self):
        assessment = _make_assessment(max_hang_total=90, weighted_pullup_total=100, body_fat_pct=15)
        goal = _make_goal()
        p1 = compute_assessment_profile(assessment, goal)
        p2 = compute_assessment_profile(assessment, goal)
        self.assertEqual(p1, p2)

    def test_body_composition_with_bf(self):
        lean = _make_assessment(body_fat_pct=12)
        heavy = _make_assessment(body_fat_pct=22)
        goal = _make_goal()
        p1 = compute_assessment_profile(lean, goal)
        p2 = compute_assessment_profile(heavy, goal)
        self.assertGreater(p1["body_composition"], p2["body_composition"])


if __name__ == "__main__":
    unittest.main()
