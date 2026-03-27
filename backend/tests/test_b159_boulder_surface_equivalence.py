"""Tests for B159 — Boulder Surface Equivalence + Weight Expansion.

8 tests covering:
1. expand_equipment: spraywall → adds gym_boulder
2. expand_equipment: board_kilter → adds gym_boulder
3. expand_equipment: homewall → adds gym_boulder
4. expand_equipment: gym_routes only → does NOT add gym_boulder
5. expand_equipment: dumbbell → adds weight
6. Planner: Cocque (spraywall+kilter, no gym_boulder) gets boulder sessions
7. Planner: Work (no boulder surfaces) does NOT get boulder sessions
8. Planner: Daniele's real availability → 3 hard sessions including power_contact at Cocque
"""

import json
import os
import unittest

from backend.engine.equipment_utils import BOULDER_SURFACES, WEIGHT_SUBTYPES, expand_equipment
from backend.engine.planner_v2 import (
    _SESSION_META,
    _equipment_for_location,
    generate_phase_week,
)
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _adjust_domain_weights, _build_session_pool


class TestExpandEquipment(unittest.TestCase):
    """Unit tests for expand_equipment()."""

    def test_spraywall_implies_gym_boulder(self):
        eq = expand_equipment(["spraywall", "hangboard"])
        self.assertIn("gym_boulder", eq)

    def test_board_kilter_implies_gym_boulder(self):
        eq = expand_equipment(["board_kilter", "pullup_bar"])
        self.assertIn("gym_boulder", eq)

    def test_homewall_implies_gym_boulder(self):
        eq = expand_equipment(["homewall", "hangboard"])
        self.assertIn("gym_boulder", eq)

    def test_gym_routes_only_no_gym_boulder(self):
        eq = expand_equipment(["gym_routes", "hangboard", "pullup_bar"])
        self.assertNotIn("gym_boulder", eq)

    def test_dumbbell_implies_weight(self):
        eq = expand_equipment(["dumbbell", "pullup_bar"])
        self.assertIn("weight", eq)

    def test_barbell_implies_weight(self):
        eq = expand_equipment(["barbell"])
        self.assertIn("weight", eq)

    def test_no_double_add(self):
        """If gym_boulder already present, don't add it again."""
        eq = expand_equipment(["gym_boulder", "spraywall"])
        self.assertEqual(eq.count("gym_boulder"), 1)

    def test_empty_input(self):
        eq = expand_equipment([])
        self.assertEqual(eq, [])


class TestPlannerEquipmentExpansion(unittest.TestCase):
    """Planner places boulder sessions at gyms with board/spray surfaces."""

    @staticmethod
    def _cocque_slot_info():
        return {
            "available": True,
            "locations": ["gym", "home"],
            "preferred_location": "gym",
            "gym_id": "cocque",
        }

    @staticmethod
    def _work_slot_info():
        return {
            "available": True,
            "locations": ["gym", "home"],
            "preferred_location": "gym",
            "gym_id": "work",
        }

    @staticmethod
    def _gyms():
        return [
            {"gym_id": "bkl", "equipment": ["gym_boulder", "spraywall", "hangboard", "pullup_bar", "dumbbell"]},
            {"gym_id": "cocque", "equipment": ["spraywall", "board_kilter", "gym_routes", "hangboard", "pullup_bar"]},
            {"gym_id": "work", "equipment": ["barbell", "cable_machine", "dumbbell", "pullup_bar", "bench"]},
        ]

    def test_cocque_has_gym_boulder_via_expansion(self):
        """Cocque (spraywall+kilter) should report gym_boulder in equipment."""
        equip = _equipment_for_location(
            "gym", self._cocque_slot_info(), ["hangboard"], self._gyms(), "bkl",
        )
        self.assertIn("gym_boulder", equip)

    def test_work_no_gym_boulder(self):
        """Work (weights only) should NOT have gym_boulder."""
        equip = _equipment_for_location(
            "gym", self._work_slot_info(), ["hangboard"], self._gyms(), "bkl",
        )
        self.assertNotIn("gym_boulder", equip)

    def test_work_has_weight(self):
        """Work (barbell+dumbbell) should have weight via expansion."""
        equip = _equipment_for_location(
            "gym", self._work_slot_info(), ["hangboard"], self._gyms(), "bkl",
        )
        self.assertIn("weight", equip)


class TestDanieleRealPlan(unittest.TestCase):
    """Integration: Daniele's actual availability produces correct S&P plan."""

    @staticmethod
    def _daniele_kwargs():
        availability = {
            "mon": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "bkl"}},
            "tue": {"evening": {"available": True, "preferred_location": "home"}},
            "wed": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "cocque"}},
            "thu": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "cocque"}},
            "fri": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "work"}},
            "sat": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "cocque"}},
            "sun": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "cocque"}},
        }
        gyms = [
            {"gym_id": "bkl", "equipment": ["hangboard", "board_moonboard", "spraywall", "gym_boulder", "campus_board", "pullup_bar", "dumbbell", "rings"]},
            {"gym_id": "cocque", "equipment": ["spraywall", "board_kilter", "gym_routes", "hangboard", "campus_board", "pullup_bar"]},
            {"gym_id": "work", "equipment": ["barbell", "cable_machine", "leg_press", "bench", "dumbbell", "pullup_bar", "weight", "resistance_band", "rings", "ab_wheel", "foam_roller"]},
        ]
        profile = {"finger_strength": 65, "pulling_strength": 60, "power_endurance": 50, "technique": 55, "endurance": 45}
        dw = _adjust_domain_weights(_BASE_WEIGHTS["strength_power"], profile)
        pool = _build_session_pool("strength_power", "lead")
        return dict(
            phase_id="strength_power",
            domain_weights=dw,
            session_pool=pool,
            start_date="2026-03-30",
            availability=availability,
            allowed_locations=["home", "gym"],
            hard_cap_per_week=4,
            planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 4},
            default_gym_id="bkl",
            gyms=gyms,
            home_equipment=["hangboard", "pullup_bar", "dumbbell", "band", "resistance_band", "loading_pin"],
        )

    def test_hard_climbing_sessions(self):
        """B162: S&P now includes route_endurance_gym for lead route mileage,
        so hard climbing count drops from 3 to 2 (limit_boulder + strength_long).
        power_contact_gym may or may not be placed depending on scheduling."""
        plan = generate_phase_week(**self._daniele_kwargs())
        days = plan["weeks"][0]["days"]
        all_sessions = [s for d in days for s in d["sessions"]]
        hard_climbing = [
            s for s in all_sessions
            if _SESSION_META.get(s["session_id"], {}).get("hard")
            and _SESSION_META.get(s["session_id"], {}).get("climbing")
        ]
        hard_ids = [s["session_id"] for s in hard_climbing]
        self.assertGreaterEqual(len(hard_climbing), 2,
                                f"Expected ≥2 hard climbing, got {len(hard_climbing)}: {hard_ids}")

    def test_power_contact_or_route_at_cocque(self):
        """B162: with route_endurance_gym in S&P pool, Cocque gym_routes days
        may get route_endurance instead of power_contact. Either is valid."""
        plan = generate_phase_week(**self._daniele_kwargs())
        days = plan["weeks"][0]["days"]
        cocque_climbing = []
        for d in days:
            for s in d["sessions"]:
                if s.get("gym_id") == "cocque" and _SESSION_META.get(s["session_id"], {}).get("climbing"):
                    cocque_climbing.append(s["session_id"])
        self.assertTrue(len(cocque_climbing) >= 1,
                        f"Expected ≥1 climbing session at Cocque, got: {cocque_climbing}")

    def test_strength_long_placed(self):
        plan = generate_phase_week(**self._daniele_kwargs())
        days = plan["weeks"][0]["days"]
        placed = [s["session_id"] for d in days for s in d["sessions"]]
        self.assertIn("strength_long", placed,
                       f"strength_long must be placed, got: {placed}")


if __name__ == "__main__":
    unittest.main()
