"""Tests for D80: age gate filtering in exercise selection."""

import unittest

from backend.engine.resolve_session import pick_best_exercise_p0


def _ex(ex_id, role="main", domain="finger_strength", age_minimum=None, **kw):
    """Helper: build a minimal exercise dict."""
    e = {
        "exercise_id": ex_id,
        "role": [role],
        "domain": [domain],
        "location_allowed": ["gym"],
        "equipment_required": [],
    }
    if age_minimum is not None:
        e["age_minimum"] = age_minimum
    e.update(kw)
    return e


class TestAgeGateFiltering(unittest.TestCase):
    """D80: exercises with age_minimum > user_age must be filtered out."""

    def _pick(self, exercises, user_age=None):
        ex, trace = pick_best_exercise_p0(
            exercises=exercises,
            location="gym",
            available_equipment=[],
            role_req="main",
            domain_req="finger_strength",
            user_age=user_age,
        )
        return ex

    def test_under_16_blocked_from_age_16_exercise(self):
        """User age 14 must NOT get an exercise with age_minimum=16."""
        exercises = [
            _ex("max_hang_maw", age_minimum=16),
            _ex("warmup_repeaters"),  # no age_minimum
        ]
        result = self._pick(exercises, user_age=14)
        self.assertIsNotNone(result)
        self.assertEqual(result["exercise_id"], "warmup_repeaters")

    def test_age_16_gets_age_16_exercise(self):
        """User age 16 CAN get an exercise with age_minimum=16."""
        exercises = [
            _ex("max_hang_maw", age_minimum=16),
        ]
        result = self._pick(exercises, user_age=16)
        self.assertIsNotNone(result)
        self.assertEqual(result["exercise_id"], "max_hang_maw")

    def test_adult_gets_all_exercises(self):
        """User age 25 gets all exercises regardless of age_minimum."""
        exercises = [
            _ex("campus_double_dynos", age_minimum=16),
            _ex("max_hang_maw", age_minimum=16),
        ]
        result = self._pick(exercises, user_age=25)
        self.assertIsNotNone(result)

    def test_no_age_means_no_filtering(self):
        """When user_age is None (not provided), no age filtering occurs."""
        exercises = [
            _ex("max_hang_maw", age_minimum=16),
        ]
        result = self._pick(exercises, user_age=None)
        self.assertIsNotNone(result)
        self.assertEqual(result["exercise_id"], "max_hang_maw")

    def test_all_blocked_returns_none(self):
        """If all exercises are blocked by age gate, return None."""
        exercises = [
            _ex("max_hang_maw", age_minimum=16),
            _ex("campus_double_dynos", age_minimum=16),
        ]
        result = self._pick(exercises, user_age=14)
        self.assertIsNone(result)

    def test_exercise_without_age_minimum_always_available(self):
        """Exercises without age_minimum are always available."""
        exercises = [
            _ex("basic_pullup"),
        ]
        result = self._pick(exercises, user_age=10)
        self.assertIsNotNone(result)
        self.assertEqual(result["exercise_id"], "basic_pullup")


if __name__ == "__main__":
    unittest.main()
