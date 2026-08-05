"""B321 — boulder grades must reach the assessment benchmarks.

The benchmark tables in ``assessment_v1`` are calibrated to lowercase French
lead grades, but the engine stores boulder grades in Fontainebleau (CLAUDE.md,
"Fontainebleau for boulder grades"). Three code paths turned that mismatch into
a wrong score instead of an error:

1. ``_compute_finger_strength`` / ``_compute_pulling_strength`` mapped any grade
   outside the lead table to index **0** — i.e. "beginner" — so the grade-based
   fallback floored the axis for every boulderer.
2. ``_compute_power_endurance`` / ``_compute_technique`` read ``lead_max_*``
   only, so a boulder-only athlete always got the neutral 50 on both axes.
3. ``_benchmark_for`` raised ValueError on a Font target, which takes the whole
   profile down (and with it the plan — see B302).

The first real user to hit this was a 7B boulderer who onboarded from Reddit on
2026-08-05 with measured tests on file and was shown ``finger_strength: 0``.
``test_the_reddit_boulderer_case`` is that exact payload.
"""

import unittest

from backend.engine.assessment_v1 import (
    _benchmark_for,
    _FINGER_BENCHMARK,
    compute_assessment_profile,
    resolve_grade,
)


class TestResolveGrade(unittest.TestCase):
    def test_lead_grades_pass_through(self):
        self.assertEqual(resolve_grade("7b+"), "7b+")

    def test_font_grades_map_to_lead(self):
        self.assertEqual(resolve_grade("7B"), "7c+")
        self.assertEqual(resolve_grade("6A"), "6c+")

    def test_font_is_case_insensitive(self):
        self.assertEqual(resolve_grade("7b"), "7b")  # lead wins over Font 7B
        self.assertEqual(resolve_grade("8a"), "8a")  # lead wins over Font 8A

    def test_unknown_and_empty_return_none(self):
        self.assertIsNone(resolve_grade("V12"))
        self.assertIsNone(resolve_grade(""))
        self.assertIsNone(resolve_grade(None))


class TestBenchmarkSurvivesFontTarget(unittest.TestCase):
    def test_font_target_does_not_raise(self):
        # Pre-B321 this raised ValueError: Unknown grade: '7C'
        self.assertEqual(
            _benchmark_for(_FINGER_BENCHMARK, "7C"),
            _benchmark_for(_FINGER_BENCHMARK, "8a"),
        )

    def test_unknown_target_falls_back_instead_of_raising(self):
        self.assertEqual(
            _benchmark_for(_FINGER_BENCHMARK, "V15"),
            _benchmark_for(_FINGER_BENCHMARK, "7c+"),
        )


def _boulderer(**overrides):
    """A boulder-only athlete: Font grades filled, lead grades empty."""
    assessment = {
        "body": {"weight_kg": 67, "height_cm": 174, "age": 25},
        "experience": {"climbing_years": 3, "structured_training_years": 2},
        "grades": {
            "lead_max_os": "",
            "lead_max_rp": "",
            "boulder_max_os": "7A",
            "boulder_max_rp": "7B",
        },
        "tests": {},
        "self_eval": {
            "primary_weakness": "weak_on_slopers",
            "secondary_weakness": "poor_dynamic_movement",
        },
    }
    assessment.update(overrides)
    goal = {
        "discipline": "boulder",
        "goal_type": "boulder_grade",
        "current_grade": "7B",          # Font, as the wizard stores it
        "target_boulder_grade": "7C",
        "target_grade": "8a",           # already mapped by the onboarding router
    }
    return assessment, goal


class TestBoulderProfile(unittest.TestCase):
    def test_finger_strength_is_not_floored_without_a_hang_test(self):
        """The regression: no max hang on file → grade fallback → used to be 0."""
        profile = compute_assessment_profile(*_boulderer())
        self.assertGreater(
            profile["finger_strength"], 0,
            "a 7B boulderer must not score 0 on fingers just because the "
            "fallback could not read a Font grade",
        )

    def test_gap_axes_read_boulder_grades(self):
        """PE and technique used to sit on the neutral 50 for boulder-only users."""
        profile = compute_assessment_profile(*_boulderer())
        # 7A onsight → 7b+, 7B redpoint → 7c+ ⇒ gap of 2 half-grades ⇒ top band,
        # minus the poor_dynamic_movement penalties. Both land well above neutral.
        self.assertGreater(profile["technique"], 50)
        self.assertGreater(profile["power_endurance"], 50)

    def test_font_and_mapped_lead_grades_score_identically(self):
        """Storing 7B or its lead equivalent 7c+ must not change the profile."""
        font_assessment, font_goal = _boulderer()
        lead_goal = dict(font_goal, current_grade="7c+")
        lead_assessment = dict(font_assessment)
        lead_assessment["grades"] = {
            "lead_max_os": "7b+", "lead_max_rp": "7c+",
            "boulder_max_os": "", "boulder_max_rp": "",
        }
        self.assertEqual(
            compute_assessment_profile(font_assessment, font_goal),
            compute_assessment_profile(lead_assessment, lead_goal),
        )

    def test_lead_grades_win_when_both_are_present(self):
        """A 'both' athlete is scored on their lead pair, not the boulder one."""
        assessment, goal = _boulderer()
        assessment["grades"] = {
            "lead_max_os": "6a", "lead_max_rp": "8a",   # huge gap → low technique
            "boulder_max_os": "7A", "boulder_max_rp": "7B",  # small gap → high
        }
        profile = compute_assessment_profile(assessment, goal)
        self.assertLess(profile["technique"], 50)

    def test_unknown_grade_reads_as_neutral_not_beginner(self):
        """An unscoreable grade must not masquerade as a floor score."""
        assessment, goal = _boulderer()
        goal["current_grade"] = "V7"  # V-scale never reaches the engine (A262)
        profile = compute_assessment_profile(assessment, goal)
        self.assertGreater(profile["finger_strength"], 0)


class TestTheRedditBouldererCase(unittest.TestCase):
    """The production payload that surfaced this, 2026-08-05."""

    def test_measured_pullup_still_beats_the_grade_fallback(self):
        assessment, goal = _boulderer(
            tests={
                "weighted_pullup_1rm_total_kg": 45,
                "lp_max_lift_5s_left_kg": 62.5,
                "lp_max_lift_5s_right_kg": 65,
                "lp_duration_20mm_left_seconds": 90,
                "lp_duration_20mm_right_seconds": 90,
                "l_sit_hold_seconds": 25,
            },
        )
        profile = compute_assessment_profile(assessment, goal)
        # +45kg on 67kg bodyweight = ratio 0.67 against the 1.55 8a benchmark.
        # Measured, so it must not move when the grade fallback changes.
        self.assertEqual(profile["pulling_strength"], 43)
        # Every axis must carry information — no zeros, no bare neutrals.
        self.assertTrue(all(v > 0 for v in profile.values()), profile)


if __name__ == "__main__":
    unittest.main()
