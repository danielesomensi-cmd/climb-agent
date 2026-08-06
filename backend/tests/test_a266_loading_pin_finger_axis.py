"""A266 — the finger axis ignored loading-pin tests.

`_compute_finger_strength` only ever read `max_hang_20mm_{5,7}s_total_kg`.
Climbers who test on a loading pin — the wizard swaps the LP variants in for
them when `finger_device == "loading_pin"`, and the beta tester uses one because
a shoulder limitation rules out hangboarding entirely — record
`lp_max_lift_5s_left/right_kg` and nothing else. Their measured numbers were
invisible: the axis fell back to estimating from grade, exactly the silent
substitution B321 removed elsewhere.

The conversion constant is not invented here — see LP_ONE_ARM_TO_TWO_HAND for
the three sources that agree on it. These tests pin the behaviour, the
plausibility bound, and the precedence of a real hangboard number over a
converted one.
"""

import unittest

from backend.engine.assessment_v1 import (
    LP_MAX_PLAUSIBLE_BW_RATIO,
    LP_ONE_ARM_TO_TWO_HAND,
    _FINGER_BENCHMARK,
    compute_assessment_profile,
    loading_pin_two_hand_equivalent,
)


class TestLoadingPinConversion(unittest.TestCase):

    def test_averages_both_hands(self):
        # A left/right spread is an asymmetry to train, not extra strength.
        got = loading_pin_two_hand_equivalent(
            {"lp_max_lift_5s_left_kg": 40, "lp_max_lift_5s_right_kg": 50}, 70.0
        )
        self.assertAlmostEqual(got, 45 * LP_ONE_ARM_TO_TWO_HAND, places=6)

    def test_single_hand_is_used_alone(self):
        got = loading_pin_two_hand_equivalent({"lp_max_lift_5s_right_kg": 40}, 70.0)
        self.assertAlmostEqual(got, 40 * LP_ONE_ARM_TO_TWO_HAND, places=6)

    def test_no_pin_data_returns_none(self):
        self.assertIsNone(loading_pin_two_hand_equivalent({}, 70.0))
        self.assertIsNone(loading_pin_two_hand_equivalent({"max_hang_20mm_7s_total_kg": 90}, 70.0))

    def test_junk_values_are_ignored(self):
        for value in (None, 0, -5, "", "abc"):
            self.assertIsNone(
                loading_pin_two_hand_equivalent({"lp_max_lift_5s_right_kg": value}, 70.0),
                f"{value!r} should not produce a score",
            )

    def test_implausible_value_dropped_not_saturated(self):
        """Past the hardest boulder ever climbed, it's a typo — not a climber."""
        bw = 70.0
        absurd = bw * (LP_MAX_PLAUSIBLE_BW_RATIO + 0.2)
        self.assertIsNone(loading_pin_two_hand_equivalent({"lp_max_lift_5s_right_kg": absurd}, bw))

    def test_implausible_hand_dropped_other_hand_kept(self):
        bw = 70.0
        got = loading_pin_two_hand_equivalent(
            {"lp_max_lift_5s_left_kg": 40, "lp_max_lift_5s_right_kg": bw * 3}, bw
        )
        self.assertAlmostEqual(got, 40 * LP_ONE_ARM_TO_TWO_HAND, places=6)

    def test_zero_bodyweight_returns_none(self):
        self.assertIsNone(loading_pin_two_hand_equivalent({"lp_max_lift_5s_right_kg": 40}, 0))


class TestConversionAgreesWithHangboard(unittest.TestCase):
    """The two devices must land a climber on the same axis score."""

    def test_lattice_one_arm_reproduces_the_8a_benchmark(self):
        # Lattice puts V8/V9 (~lead 8a) at 0.73-0.79 x bodyweight on one arm;
        # _FINGER_BENCHMARK puts 8a at 1.40 x bodyweight across two hands.
        bw = 70.0
        for one_arm_ratio in (0.73, 0.76, 0.79):
            equivalent = loading_pin_two_hand_equivalent(
                {"lp_max_lift_5s_right_kg": one_arm_ratio * bw}, bw
            )
            implied = equivalent / bw
            self.assertAlmostEqual(
                implied, _FINGER_BENCHMARK["8a"], delta=0.12,
                msg=f"one-arm {one_arm_ratio} BW implied {implied:.2f}, "
                    f"benchmark says {_FINGER_BENCHMARK['8a']}",
            )

    def test_constant_sits_inside_the_literature_range(self):
        # Bilateral-deficit literature for climbers: two-arm total / one-arm 1.6-2.0.
        self.assertGreater(LP_ONE_ARM_TO_TWO_HAND, 1.6)
        self.assertLess(LP_ONE_ARM_TO_TWO_HAND, 2.0)


def _profile(tests, *, weight=70.0):
    assessment = {
        "body": {"age": 30, "height_cm": 175, "weight_kg": weight},
        "tests": tests,
        "grades": {"boulder_max_rp": "7A", "boulder_max_os": "6C"},
        "self_eval": {},
        "experience": {"climbing_years": 5, "structured_training_years": 1},
    }
    goal = {
        "discipline": "boulder", "goal_type": "boulder_grade",
        "current_grade": "7A", "target_grade": "8a", "target_boulder_grade": "7C",
    }
    return compute_assessment_profile(assessment, goal)


class TestProfileUsesPinData(unittest.TestCase):

    def test_pin_user_axis_is_no_longer_a_grade_estimate(self):
        weak = _profile({"lp_max_lift_5s_left_kg": 20, "lp_max_lift_5s_right_kg": 21})
        strong = _profile({"lp_max_lift_5s_left_kg": 55, "lp_max_lift_5s_right_kg": 57})
        self.assertLess(
            weak["finger_strength"], strong["finger_strength"],
            "the axis does not move with the pin numbers — still estimating from grade",
        )

    def test_hangboard_wins_when_both_present(self):
        """A directly measured hang beats a converted lift."""
        both = _profile({
            "max_hang_20mm_7s_total_kg": 95,
            "lp_max_lift_5s_left_kg": 20, "lp_max_lift_5s_right_kg": 20,
        })
        hang_only = _profile({"max_hang_20mm_7s_total_kg": 95})
        self.assertEqual(both["finger_strength"], hang_only["finger_strength"])

    def test_no_test_data_still_estimates_from_grade(self):
        profile = _profile({})
        self.assertGreater(profile["finger_strength"], 0)
        self.assertLessEqual(profile["finger_strength"], 100)

    def test_axis_stays_bounded(self):
        profile = _profile({"lp_max_lift_5s_left_kg": 100, "lp_max_lift_5s_right_kg": 100}, weight=70.0)
        self.assertLessEqual(profile["finger_strength"], 100)
        self.assertGreaterEqual(profile["finger_strength"], 0)


if __name__ == "__main__":
    unittest.main()
