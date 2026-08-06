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
        )
        goal = _make_goal("7c+", "7b")
        profile = compute_assessment_profile(assessment, goal)
        self.assertEqual(set(profile.keys()), {
            "finger_strength", "pulling_strength", "power_endurance",
            "technique", "endurance",
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

    def test_pe_ignores_the_gap_entirely(self):
        """A270/D266: the gap used to carry 60% of PE (0.4 + 0.2), against 40%
        for the only objective input. Now it carries none."""
        wide = compute_assessment_profile(
            _make_assessment(lead_max_rp="8a+", lead_max_os="7b"), _make_goal("8a+", "8a")
        )
        narrow = compute_assessment_profile(
            _make_assessment(lead_max_rp="8a+", lead_max_os="8a"), _make_goal("8a+", "8a")
        )
        self.assertEqual(wide["power_endurance"], narrow["power_endurance"])

    def test_pe_without_a_repeater_is_exactly_neutral(self):
        """No measurement, no signal — and exactly 50, not 50 minus a penalty.

        The domain-weight response has a dead band at 50-75; a self-eval penalty
        would drop it below the `< 50` cliff and let a self-declaration steer the
        plan, which is what this brief takes away from technique.
        """
        for weakness in (None, "pump_too_early", "poor_dynamic_movement"):
            assessment = _make_assessment(
                lead_max_rp="7b", lead_max_os="7a+", primary_weakness=weakness,
            )
            profile = compute_assessment_profile(assessment, _make_goal("7c", "7a"))
            self.assertEqual(profile["power_endurance"], 50, weakness)

    def test_pe_with_a_repeater_is_the_repeater(self):
        """Undiluted: D260 found a repeater worth 78/100 dragged to 54."""
        assessment = _make_assessment(
            lead_max_rp="8a+", lead_max_os="7b",
            primary_weakness="cant_hold_hard_moves", secondary_weakness=None,
        )
        assessment["tests"]["repeater_7_3_max_sets_20mm"] = 30
        profile = compute_assessment_profile(assessment, _make_goal("8a+", "8a"))
        # 30 / 32 (8a+ benchmark) * 100, no PE weakness penalty
        self.assertEqual(profile["power_endurance"], 94)

    def test_score_clamped_0_100(self):
        # Very strong climber → scores should not exceed 100
        assessment = _make_assessment(max_hang_total=200, weighted_pullup_total=200)
        goal = _make_goal("7a", "6c+")
        profile = compute_assessment_profile(assessment, goal)
        for k, v in profile.items():
            self.assertGreaterEqual(v, 0, f"{k} below 0")
            self.assertLessEqual(v, 100, f"{k} above 100")

    def test_self_eval_modifier_pump(self):
        """A270: the pump penalty still bites — but only on top of a real
        measurement. Without a repeater PE is a flat neutral 50 and no
        self-declaration can move it."""
        def _pe(weakness, *, repeater):
            a = _make_assessment(
                lead_max_rp="7b", lead_max_os="6c+", primary_weakness=weakness,
            )
            if repeater:
                a["tests"]["repeater_7_3_max_sets_20mm"] = 20
            return compute_assessment_profile(a, _make_goal())["power_endurance"]

        self.assertLess(
            _pe("pump_too_early", repeater=True),
            _pe("cant_hold_hard_moves", repeater=True),
        )
        self.assertEqual(
            _pe("pump_too_early", repeater=False),
            _pe("cant_hold_hard_moves", repeater=False),
        )

    def test_deterministic(self):
        assessment = _make_assessment(max_hang_total=90, weighted_pullup_total=100)
        goal = _make_goal()
        p1 = compute_assessment_profile(assessment, goal)
        p2 = compute_assessment_profile(assessment, goal)
        self.assertEqual(p1, p2)

class TestPERepeaterIntegration(unittest.TestCase):
    """Tests for PE repeater test integration + no double counting (F5 fix)."""

    def test_pe_with_repeater_data(self):
        """Repeater data should influence PE score."""
        # Without repeater
        no_rep = _make_assessment(lead_max_rp="8a+", lead_max_os="7b")
        # With repeater
        with_rep = _make_assessment(lead_max_rp="8a+", lead_max_os="7b")
        with_rep["tests"]["repeater_7_3_max_sets_20mm"] = 30  # good score for 7c+ target

        goal = _make_goal("7c+", "7b")
        p1 = compute_assessment_profile(no_rep, goal)
        p2 = compute_assessment_profile(with_rep, goal)
        # With a decent repeater score, PE should be higher
        self.assertGreater(p2["power_endurance"], p1["power_endurance"])

    def test_pe_repeater_low_reps(self):
        """Low repeater reps → lower PE score than gap alone would suggest."""
        assessment = _make_assessment(
            lead_max_rp="7b", lead_max_os="7a+",  # gap=1 → gap_score=75
            primary_weakness="cant_hold_hard_moves",
            secondary_weakness=None,
        )
        assessment["tests"]["repeater_7_3_max_sets_20mm"] = 10  # very low

        goal = _make_goal("8b", "7b")
        profile = compute_assessment_profile(assessment, goal)
        # Low repeater should pull score down despite good gap
        self.assertLess(profile["power_endurance"], 60)

    def test_pe_no_double_counting_pump(self):
        """Self-eval penalty for pump_too_early should be reduced (no double counting)."""
        # With repeater data, the penalty is only 20% weight (reduced from full penalty)
        assessment = _make_assessment(
            lead_max_rp="7b", lead_max_os="6c+",  # gap=3 → gap_score=55
            primary_weakness="pump_too_early",
        )
        assessment["tests"]["repeater_7_3_max_sets_20mm"] = 22

        # Without pump weakness
        no_pump = _make_assessment(
            lead_max_rp="7b", lead_max_os="6c+",
            primary_weakness="cant_hold_hard_moves",
        )
        no_pump["tests"]["repeater_7_3_max_sets_20mm"] = 22

        goal = _make_goal("7c+", "7b")
        with_pump = compute_assessment_profile(assessment, goal)
        without_pump = compute_assessment_profile(no_pump, goal)
        # Pump penalty should exist but be small (reduced from -15 to -8, weighted at 20%)
        diff = without_pump["power_endurance"] - with_pump["power_endurance"]
        self.assertGreater(diff, 0, "Pump weakness should still reduce PE score")
        self.assertLess(diff, 10, "Pump penalty should be small to avoid double counting")

    def test_pe_deterministic_with_repeater(self):
        """PE with repeater data must be deterministic."""
        assessment = _make_assessment(lead_max_rp="8a+", lead_max_os="7b")
        assessment["tests"]["repeater_7_3_max_sets_20mm"] = 24
        goal = _make_goal("8b", "8a+")
        p1 = compute_assessment_profile(assessment, goal)
        p2 = compute_assessment_profile(assessment, goal)
        self.assertEqual(p1["power_endurance"], p2["power_endurance"])

    def test_pe_without_repeater_still_works(self):
        """PE without repeater data should still compute correctly (backward compatible)."""
        assessment = _make_assessment(lead_max_rp="7b", lead_max_os="6c+")
        # repeater is None by default in _make_assessment
        goal = _make_goal("7c+", "7b")
        profile = compute_assessment_profile(assessment, goal)
        self.assertGreater(profile["power_endurance"], 0)
        self.assertLessEqual(profile["power_endurance"], 100)


class TestEnduranceHangDuration(unittest.TestCase):
    """Tests for max_hang_duration_20mm_seconds modifier on endurance axis."""

    def test_endurance_hang_duration_bonus(self):
        """>=90s hang adds 8 points to endurance."""
        assessment_base = _make_assessment(primary_weakness="technique_errors", secondary_weakness="cant_read_routes")
        goal = _make_goal("7c+", "7b")
        base = compute_assessment_profile(assessment_base, goal)["endurance"]

        assessment_with = _make_assessment(primary_weakness="technique_errors", secondary_weakness="cant_read_routes")
        assessment_with["tests"]["max_hang_duration_20mm_seconds"] = 95
        with_bonus = compute_assessment_profile(assessment_with, goal)["endurance"]
        self.assertEqual(with_bonus, min(100, base + 8))

    def test_endurance_hang_duration_penalty(self):
        """<30s subtracts 8 from endurance."""
        assessment_base = _make_assessment(primary_weakness="technique_errors", secondary_weakness="cant_read_routes")
        goal = _make_goal("7c+", "7b")
        base = compute_assessment_profile(assessment_base, goal)["endurance"]

        assessment_with = _make_assessment(primary_weakness="technique_errors", secondary_weakness="cant_read_routes")
        assessment_with["tests"]["max_hang_duration_20mm_seconds"] = 20
        with_penalty = compute_assessment_profile(assessment_with, goal)["endurance"]
        self.assertEqual(with_penalty, max(0, base - 8))

    def test_endurance_no_hang_duration_unchanged(self):
        """Missing hang duration = existing behavior (no change)."""
        assessment = _make_assessment()
        goal = _make_goal()
        base = compute_assessment_profile(assessment, goal)["endurance"]

        assessment2 = _make_assessment()
        assessment2["tests"]["max_hang_duration_20mm_seconds"] = None
        same = compute_assessment_profile(assessment2, goal)["endurance"]
        self.assertEqual(base, same)


if __name__ == "__main__":
    unittest.main()
