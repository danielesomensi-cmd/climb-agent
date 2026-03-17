"""Tests for D81: youth training cap (max 4 days/week for <18)."""

import unittest

from backend.engine.planner_v2 import generate_phase_week
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _build_session_pool, _adjust_domain_weights


def _avail_6_days():
    """Availability for 6 days (Mon-Sat), all gym evening slots."""
    return {
        "mon": {"evening": {"available": True, "locations": ["gym"]}},
        "tue": {"evening": {"available": True, "locations": ["gym"]}},
        "wed": {"evening": {"available": True, "locations": ["gym"]}},
        "thu": {"evening": {"available": True, "locations": ["gym"]}},
        "fri": {"evening": {"available": True, "locations": ["gym"]}},
        "sat": {"evening": {"available": True, "locations": ["gym"]}},
    }


def _make_kwargs(user_age=None, target_days=6):
    profile = {"finger_strength": 60, "pulling_strength": 55,
               "power_endurance": 45, "technique": 50, "endurance": 40}
    base_weights = _BASE_WEIGHTS["base"]
    domain_weights = _adjust_domain_weights(base_weights, profile)
    session_pool = _build_session_pool("base")
    return {
        "phase_id": "base",
        "domain_weights": domain_weights,
        "session_pool": session_pool,
        "start_date": "2026-03-16",
        "availability": _avail_6_days(),
        "allowed_locations": ["gym"],
        "planning_prefs": {"target_training_days_per_week": target_days, "hard_day_cap_per_week": 3},
        "default_gym_id": "blocx",
        "gyms": [{"gym_id": "blocx", "equipment": ["hangboard", "gym_boulder", "gym_routes", "dumbbell", "pullup_bar"]}],
        "user_age": user_age,
    }


class TestYouthTrainingCap(unittest.TestCase):

    def _count_training_days(self, plan):
        """Count days that have at least one session."""
        count = 0
        for day in plan.get("weeks", [{}])[0].get("days", []):
            if day.get("sessions"):
                count += 1
        return count

    def test_adult_can_have_6_days(self):
        """Adult (25) with 6-day availability gets more than 4 training days."""
        plan = generate_phase_week(**_make_kwargs(user_age=25, target_days=6))
        training_days = self._count_training_days(plan)
        self.assertGreater(training_days, 4)

    def test_youth_capped_at_4_days(self):
        """Youth (16) with 6-day availability gets max 4 training days."""
        plan = generate_phase_week(**_make_kwargs(user_age=16, target_days=6))
        training_days = self._count_training_days(plan)
        self.assertLessEqual(training_days, 4)
        self.assertGreater(training_days, 0)

    def test_youth_with_4_days_ok(self):
        """Youth (16) requesting 4 days is not further reduced."""
        plan = generate_phase_week(**_make_kwargs(user_age=16, target_days=4))
        training_days = self._count_training_days(plan)
        self.assertGreater(training_days, 0)
        self.assertLessEqual(training_days, 4)

    def test_no_age_no_cap(self):
        """When user_age is None, no youth cap is applied."""
        plan = generate_phase_week(**_make_kwargs(user_age=None, target_days=6))
        training_days = self._count_training_days(plan)
        self.assertGreater(training_days, 4)

    def test_17_year_old_still_capped(self):
        """17-year-old (under 18) is still capped at 4."""
        plan = generate_phase_week(**_make_kwargs(user_age=17, target_days=6))
        training_days = self._count_training_days(plan)
        self.assertLessEqual(training_days, 4)

    def test_18_year_old_not_capped(self):
        """18-year-old is NOT capped (18 >= 18)."""
        plan = generate_phase_week(**_make_kwargs(user_age=18, target_days=6))
        training_days = self._count_training_days(plan)
        self.assertGreater(training_days, 4)


if __name__ == "__main__":
    unittest.main()
