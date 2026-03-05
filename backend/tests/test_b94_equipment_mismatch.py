"""Tests for B94 — equipment mismatch must not burn pool cycling uses."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.engine.planner_v2 import generate_phase_week
from backend.engine.macrocycle_v1 import _build_session_pool, PHASE_INTENSITY_CAP


def _base_availability_all_gym(gym_ids: dict):
    """Build availability with all 7 days gym, each mapped to a specific gym_id."""
    avail = {}
    for day, gid in gym_ids.items():
        avail[day] = {"evening": {"available": True, "preferred_location": "gym", "gym_id": gid}}
    return avail


class TestEquipmentMismatchDoesNotBurnPool:
    """B94: When a session can't be placed due to equipment mismatch on a
    specific day's gym, the pool cycling counter must NOT be decremented.
    This allows the session to be placed on a later day with compatible equipment."""

    GYMS = [
        {"gym_id": "bouldering_gym", "name": "Boulder Gym",
         "equipment": ["gym_boulder", "hangboard", "campus_board"]},
        {"gym_id": "weights_gym", "name": "Weights Gym",
         "equipment": ["dumbbell", "barbell", "bench", "cable_machine", "hangboard"]},
        {"gym_id": "full_gym", "name": "Full Gym",
         "equipment": ["gym_boulder", "gym_routes", "hangboard", "dumbbell"]},
    ]

    DOMAIN_WEIGHTS = {
        "core_prehab": 0.1, "finger_strength": 0.2, "power_endurance": 0.2,
        "pulling_strength": 0.15, "technique": 0.2, "volume_climbing": 0.15,
    }

    def test_weights_gym_midweek_does_not_exhaust_pool(self):
        """A weights-only gym (no gym_boulder, no gym_routes) in mid-week must
        not consume pool cycling uses, leaving climbing sessions available
        for days with proper climbing gyms."""
        gym_ids = {
            "mon": "bouldering_gym",
            "tue": "weights_gym",     # no climbing equipment
            "wed": "weights_gym",     # no climbing equipment
            "thu": "full_gym",
            "fri": "full_gym",
            "sat": "bouldering_gym",
            "sun": "full_gym",
        }
        result = generate_phase_week(
            phase_id="base",
            domain_weights=self.DOMAIN_WEIGHTS,
            session_pool=_build_session_pool("base"),
            start_date="2026-03-09",
            availability=_base_availability_all_gym(gym_ids),
            allowed_locations=["gym", "home"],
            hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 3},
            gyms=self.GYMS,
            intensity_cap=PHASE_INTENSITY_CAP["base"],
            home_equipment=["hangboard"],
        )

        days = result["weeks"][0]["days"]
        climbing_days = []
        for day in days:
            for sess in day["sessions"]:
                if "pass1" in " ".join(sess.get("explain", [])):
                    climbing_days.append(day["weekday"])

        # With weights_gym on Tue/Wed (0 climbing possible there),
        # we still expect climbing on all other 5 gym days
        assert len(climbing_days) >= 5, (
            f"Expected >= 5 climbing days (pool should not be exhausted by "
            f"equipment mismatches), got {len(climbing_days)}: {climbing_days}"
        )

    def test_four_different_gyms_real_scenario(self):
        """Real user scenario: 4 different gyms with varying equipment.
        Climbing sessions should be placed on all days with compatible gyms."""
        gyms = [
            {"gym_id": "bkl", "name": "Bkl",
             "equipment": ["gym_boulder", "spraywall", "hangboard", "campus_board"]},
            {"gym_id": "work", "name": "Work",
             "equipment": ["dumbbell", "barbell", "bench", "cable_machine", "hangboard"]},
            {"gym_id": "cocque", "name": "Cocque",
             "equipment": ["spraywall", "board_kilter", "gym_routes", "hangboard"]},
            {"gym_id": "arlon", "name": "Arlon",
             "equipment": ["gym_boulder", "gym_routes", "spraywall", "hangboard",
                           "dumbbell", "campus_board"]},
        ]
        gym_ids = {
            "mon": "bkl",      # boulder only
            "tue": "work",     # weights only — NO climbing
            "wed": "cocque",   # routes only
            "thu": "cocque",   # routes only
            "fri": "cocque",   # routes only
            "sat": "arlon",    # full
            "sun": "arlon",    # full
        }
        result = generate_phase_week(
            phase_id="base",
            domain_weights=self.DOMAIN_WEIGHTS,
            session_pool=_build_session_pool("base"),
            start_date="2026-03-09",
            availability=_base_availability_all_gym(gym_ids),
            allowed_locations=["gym", "home"],
            hard_cap_per_week=4,
            planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 4},
            gyms=gyms,
            intensity_cap=PHASE_INTENSITY_CAP["base"],
            home_equipment=["hangboard"],
        )

        days = result["weeks"][0]["days"]
        climbing_count = 0
        non_climbing_days = []
        for day in days:
            has_climbing = False
            for sess in day["sessions"]:
                if "pass1" in " ".join(sess.get("explain", [])):
                    has_climbing = True
            if has_climbing:
                climbing_count += 1
            else:
                non_climbing_days.append(day["weekday"])

        # Mon(boulder), Wed-Fri(routes), Sat-Sun(full) = 6 days with climbing equipment
        # Tue(work) = 0 climbing. So at least 5 climbing days expected.
        assert climbing_count >= 5, (
            f"Expected >= 5 climbing days with 4-gym setup, got {climbing_count}. "
            f"Non-climbing days: {non_climbing_days}"
        )

    def test_equipment_mismatch_day_gets_complementary(self):
        """A day with only a weights gym should still get a complementary session,
        not be left empty."""
        gym_ids = {
            "mon": "bouldering_gym",
            "tue": "weights_gym",
            "wed": "full_gym",
            "thu": "full_gym",
            "fri": "full_gym",
            "sat": "full_gym",
            "sun": "full_gym",
        }
        result = generate_phase_week(
            phase_id="base",
            domain_weights=self.DOMAIN_WEIGHTS,
            session_pool=_build_session_pool("base"),
            start_date="2026-03-09",
            availability=_base_availability_all_gym(gym_ids),
            allowed_locations=["gym", "home"],
            hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 3},
            gyms=self.GYMS,
            intensity_cap=PHASE_INTENSITY_CAP["base"],
            home_equipment=["hangboard"],
        )

        days = result["weeks"][0]["days"]
        tue = next(d for d in days if d["weekday"] == "tue")
        assert len(tue["sessions"]) > 0, (
            "Tue (weights-only gym) should get a complementary session, not be empty"
        )
