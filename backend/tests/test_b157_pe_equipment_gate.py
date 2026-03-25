"""Tests for B157 — PE session equipment gate fix.

power_endurance_gym must be placeable at gyms with only gym_boulder (no gym_routes).
Boulder intervals (4x4, linked boulders) are the primary PE stimulus; route intervals optional.
"""

import json
import os
import unittest
from copy import deepcopy

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.engine.planner_v2 import _SESSION_META, generate_phase_week
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _adjust_domain_weights, _build_session_pool
from backend.engine.resolve_session import resolve_session


def _load_user_state():
    with open(os.path.join(REPO_ROOT, "backend", "tests", "fixtures", "test_user_state.json")) as f:
        return json.load(f)


def _make_user_state(base, location="gym", gym_id="bkl", equipment=None):
    us = deepcopy(base)
    us.setdefault("context", {})
    us["context"]["location"] = location
    us["context"]["gym_id"] = gym_id
    if equipment is not None:
        us["context"]["available_equipment"] = equipment
    return us


def _resolve(session_id, user_state):
    return resolve_session(
        repo_root=REPO_ROOT,
        session_path=f"backend/catalog/sessions/v1/{session_id}.json",
        templates_dir="backend/catalog/templates",
        exercises_path="backend/catalog/exercises/v1/exercises.json",
        out_path=f"output/__test_b157_{session_id}.json",
        user_state_override=user_state,
        write_output=False,
    )


class TestB157ResolveBoulderOnly(unittest.TestCase):
    """PE session resolves at a gym with ONLY gym_boulder (no gym_routes)."""

    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_user_state()

    def test_resolves_without_gym_routes(self):
        us = _make_user_state(
            self.base_us, gym_id="bkl",
            equipment=["gym_boulder", "hangboard", "pullup_bar"],
        )
        result = _resolve("power_endurance_gym", us)
        self.assertEqual(
            result["resolution_status"], "success",
            "power_endurance_gym must resolve at a boulder-only gym",
        )
        exercises = result["resolved_session"]["exercise_instances"]
        self.assertGreater(len(exercises), 0)

    def test_includes_boulder_interval_exercises(self):
        us = _make_user_state(
            self.base_us, gym_id="bkl",
            equipment=["gym_boulder", "hangboard", "pullup_bar"],
        )
        result = _resolve("power_endurance_gym", us)
        exercises = result["resolved_session"]["exercise_instances"]
        exercise_ids = {e["exercise_id"] for e in exercises if e.get("exercise_id")}
        # Should include 4x4 or linked boulders pattern exercises
        pe_boulder_ids = {"boulder_4x4", "linked_boulders", "emom_boulders", "otm_boulders"}
        found = exercise_ids & pe_boulder_ids
        # At least one boulder PE exercise should be present
        # (exact IDs may vary, so also check by block origin)
        blocks = result["resolved_session"].get("blocks", [])
        pe_boulder_blocks = [b for b in blocks if b.get("block_id") == "pe_boulder"]
        self.assertTrue(
            found or pe_boulder_blocks,
            f"Expected boulder PE exercises or pe_boulder block. Got exercises: {exercise_ids}",
        )


class TestB157ResolveWithRoutes(unittest.TestCase):
    """PE session still works at a gym WITH gym_routes."""

    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_user_state()

    def test_resolves_with_gym_routes(self):
        us = _make_user_state(
            self.base_us, gym_id="full_gym",
            equipment=["gym_boulder", "gym_routes", "hangboard", "pullup_bar"],
        )
        result = _resolve("power_endurance_gym", us)
        self.assertEqual(result["resolution_status"], "success")
        exercises = result["resolved_session"]["exercise_instances"]
        self.assertGreater(len(exercises), 0)


class TestB157PEPhasePlacement(unittest.TestCase):
    """PE session is placed in PE phase for Scenario A (BKL = gym_boulder only)."""

    def test_pe_session_placed_for_boulder_only_gym(self):
        profile = {
            "finger_strength": 60, "pulling_strength": 55,
            "power_endurance": 45, "technique": 50, "endurance": 40,
        }
        base_weights = _BASE_WEIGHTS["power_endurance"]
        domain_weights = _adjust_domain_weights(base_weights, profile)
        session_pool = _build_session_pool("power_endurance")

        availability = {
            "mon": {"evening": {"available": True, "locations": ["home"]}},
            "tue": {"lunch": {"available": True, "locations": ["gym"]}},
            "wed": {"evening": {"available": True, "locations": ["home"]}},
            "thu": {"evening": {"available": True, "locations": ["gym"]}},
            "fri": {"evening": {"available": True, "locations": ["home", "gym"]}},
            "sat": {"evening": {"available": True, "locations": ["home", "gym"]}},
            "sun": {"evening": {"available": True, "locations": ["home"]}},
        }

        plan = generate_phase_week(
            phase_id="power_endurance",
            domain_weights=domain_weights,
            session_pool=session_pool,
            start_date="2026-03-02",
            availability=availability,
            allowed_locations=["home", "gym"],
            hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 5, "hard_day_cap_per_week": 3},
            default_gym_id="bkl",
            gyms=[{"gym_id": "bkl", "equipment": ["gym_boulder", "hangboard", "pullup_bar"]}],
            home_equipment=["hangboard", "pullup_bar", "loading_pin"],
        )

        week = plan["weeks"][0]
        all_sessions = [s["session_id"] for d in week["days"] for s in d["sessions"]]
        self.assertIn(
            "power_endurance_gym", all_sessions,
            f"power_endurance_gym must be placed in PE phase for boulder-only gym. Got: {all_sessions}",
        )


class TestB157MetadataCorrect(unittest.TestCase):
    """SESSION_META entry uses gym_boulder, not gym_routes."""

    def test_meta_requires_gym_boulder(self):
        meta = _SESSION_META["power_endurance_gym"]
        self.assertIn("gym_boulder", meta["required_equipment"])
        self.assertNotIn("gym_routes", meta["required_equipment"])


if __name__ == "__main__":
    unittest.main()
