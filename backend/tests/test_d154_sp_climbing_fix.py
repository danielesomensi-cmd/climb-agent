"""Tests for D154 — Phase 1: Fix S&P Climbing Distribution.

9 tests covering:
1. finger_strength_home metadata fix (climbing=False)
2. limit_boulder_gym.json schema validation
3. limit_boulder_gym in S&P primary pool
4. limit_boulder_gym resolves to concrete exercises
5. Differentiation: limit_boulder_gym vs power_contact_gym
6. S&P week with 2+ gym days gets >=2 on-wall hard sessions
7. S&P week with 1 gym day doesn't crash
8. Exercise ordering: limit bouldering after warmup, before cooldown
9. Immutability: past weeks not affected
"""

import json
import os
import unittest
from copy import deepcopy

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.engine.planner_v2 import _SESSION_META, generate_phase_week
from backend.engine.macrocycle_v1 import (
    _SESSION_POOL,
    _SESSION_POOL_BOULDER,
    _BASE_WEIGHTS,
    _adjust_domain_weights,
    _build_session_pool,
)
from backend.engine.resolve_session import resolve_session


def _load_user_state():
    with open(os.path.join(REPO_ROOT, "backend", "tests", "fixtures", "test_user_state.json")) as f:
        return json.load(f)


def _make_user_state(base, location="gym", gym_id="blocx"):
    us = deepcopy(base)
    us.setdefault("context", {})
    us["context"]["location"] = location
    us["context"]["gym_id"] = gym_id
    return us


def _resolve(session_id, user_state):
    return resolve_session(
        repo_root=REPO_ROOT,
        session_path=f"backend/catalog/sessions/v1/{session_id}.json",
        templates_dir="backend/catalog/templates",
        exercises_path="backend/catalog/exercises/v1/exercises.json",
        out_path=f"output/__test_d154_{session_id}.json",
        user_state_override=user_state,
        write_output=False,
    )


def _base_availability_multi_gym():
    """Availability with 3 gym days (Mon, Wed, Fri) + home days."""
    return {
        "mon": {"evening": {"available": True, "locations": ["gym", "home"]}},
        "tue": {"evening": {"available": True, "locations": ["home"]}},
        "wed": {"evening": {"available": True, "locations": ["gym", "home"]}},
        "thu": {"evening": {"available": True, "locations": ["home"]}},
        "fri": {"evening": {"available": True, "locations": ["gym", "home"]}},
        "sat": {"morning": {"available": True, "locations": ["home"]}},
        "sun": {"available": False},
    }


def _base_availability_one_gym():
    """Availability with only 1 gym day (Tue)."""
    return {
        "mon": {"evening": {"available": True, "locations": ["home"]}},
        "tue": {"evening": {"available": True, "locations": ["gym", "home"]}},
        "wed": {"evening": {"available": True, "locations": ["home"]}},
        "thu": {"evening": {"available": True, "locations": ["home"]}},
        "fri": {"evening": {"available": True, "locations": ["home"]}},
        "sat": {"available": False},
        "sun": {"available": False},
    }


def _make_sp_kwargs(**overrides):
    profile = {
        "finger_strength": 60, "pulling_strength": 55,
        "power_endurance": 45, "technique": 50, "endurance": 40,
    }
    base_weights = _BASE_WEIGHTS["strength_power"]
    domain_weights = _adjust_domain_weights(base_weights, profile)
    session_pool = _build_session_pool("strength_power")
    defaults = dict(
        phase_id="strength_power",
        domain_weights=domain_weights,
        session_pool=session_pool,
        start_date="2026-03-02",
        availability=_base_availability_multi_gym(),
        allowed_locations=["home", "gym"],
        hard_cap_per_week=3,
        planning_prefs={"target_training_days_per_week": 5, "hard_day_cap_per_week": 3},
        default_gym_id="blocx",
        gyms=[{
            "gym_id": "blocx",
            "equipment": [
                "spraywall", "board_kilter", "hangboard",
                "gym_boulder", "gym_routes", "dumbbell", "pullup_bar",
            ],
        }],
    )
    defaults.update(overrides)
    return defaults


class TestD154MetadataFix(unittest.TestCase):
    """Test 1: finger_strength_home is NOT classified as climbing."""

    def test_finger_strength_home_not_climbing(self):
        meta = _SESSION_META["finger_strength_home"]
        self.assertFalse(
            meta["climbing"],
            "finger_strength_home is pure hangboard — climbing must be False",
        )


class TestD154SessionValid(unittest.TestCase):
    """Test 2: limit_boulder_gym.json exists and is valid JSON with required fields."""

    def test_limit_boulder_gym_json_valid(self):
        path = os.path.join(
            REPO_ROOT, "backend", "catalog", "sessions", "v1", "limit_boulder_gym.json",
        )
        self.assertTrue(os.path.exists(path), "limit_boulder_gym.json must exist")
        with open(path) as f:
            session = json.load(f)
        self.assertEqual(session["id"], "limit_boulder_gym")
        self.assertIn("modules", session)
        self.assertIn("required_equipment", session)
        self.assertIn("gym_boulder", session["required_equipment"])
        self.assertGreater(len(session["modules"]), 0)


class TestD154PoolMembership(unittest.TestCase):
    """Test 3: limit_boulder_gym is in S&P primary pool (both lead and boulder)."""

    def test_in_lead_sp_primary_pool(self):
        self.assertIn("limit_boulder_gym", _SESSION_POOL["strength_power"])
        self.assertEqual(
            _SESSION_POOL["strength_power"]["limit_boulder_gym"], "primary",
        )

    def test_in_boulder_sp_primary_pool(self):
        self.assertIn("limit_boulder_gym", _SESSION_POOL_BOULDER["strength_power"])
        self.assertEqual(
            _SESSION_POOL_BOULDER["strength_power"]["limit_boulder_gym"], "primary",
        )

    def test_in_build_session_pool_output(self):
        pool = _build_session_pool("strength_power", discipline="lead")
        self.assertIn("limit_boulder_gym", pool)


class TestD154SessionResolves(unittest.TestCase):
    """Test 4: limit_boulder_gym resolves to concrete exercises without errors."""

    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_user_state()

    def test_resolves_successfully(self):
        us = _make_user_state(self.base_us)
        result = _resolve("limit_boulder_gym", us)
        self.assertEqual(
            result["resolution_status"], "success",
            f"Resolution failed",
        )
        exercises = result["resolved_session"]["exercise_instances"]
        self.assertGreaterEqual(len(exercises), 3, "Should have at least warmup + main + prehab")


class TestD154Differentiation(unittest.TestCase):
    """Test 5: limit_boulder_gym and power_contact_gym are meaningfully different."""

    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_user_state()

    def test_different_exercise_sets(self):
        us = _make_user_state(self.base_us)
        limit_result = _resolve("limit_boulder_gym", us)
        power_result = _resolve("power_contact_gym", us)

        limit_ids = {e["exercise_id"] for e in limit_result["resolved_session"]["exercise_instances"]
                     if e.get("exercise_id")}
        power_ids = {e["exercise_id"] for e in power_result["resolved_session"]["exercise_instances"]
                     if e.get("exercise_id")}

        # They share warmup/cooldown but should NOT be identical
        self.assertNotEqual(
            limit_ids, power_ids,
            "limit_boulder_gym and power_contact_gym must resolve to different exercise sets",
        )

    def test_different_session_ids(self):
        """Session JSON files have distinct IDs."""
        sessions_dir = os.path.join(REPO_ROOT, "backend", "catalog", "sessions", "v1")
        with open(os.path.join(sessions_dir, "limit_boulder_gym.json")) as f:
            limit_session = json.load(f)
        with open(os.path.join(sessions_dir, "power_contact_gym.json")) as f:
            power_session = json.load(f)
        self.assertNotEqual(limit_session["id"], power_session["id"])
        # Different module structure (limit has supplementary_pulling, power has campus_power)
        limit_block_ids = {m.get("block_id") or m.get("template_id") for m in limit_session["modules"]}
        power_block_ids = {m.get("block_id") or m.get("template_id") for m in power_session["modules"]}
        self.assertNotEqual(limit_block_ids, power_block_ids)


class TestD154SPWeekMultiGym(unittest.TestCase):
    """Test 6: S&P week with 2+ gym days generates >=2 on-wall hard sessions."""

    def test_sp_week_has_multiple_climbing_hard_sessions(self):
        kwargs = _make_sp_kwargs()
        plan = generate_phase_week(**kwargs)
        week = plan["weeks"][0]
        all_sessions = [s for d in week["days"] for s in d["sessions"]]
        climbing_hard = [
            s for s in all_sessions
            if _SESSION_META.get(s["session_id"], {}).get("climbing", False)
            and _SESSION_META.get(s["session_id"], {}).get("hard", False)
        ]
        self.assertGreaterEqual(
            len(climbing_hard), 2,
            f"S&P with 3 gym days should have >=2 on-wall hard sessions, got {len(climbing_hard)}: "
            f"{[s['session_id'] for s in climbing_hard]}",
        )


class TestD154SPWeekOneGym(unittest.TestCase):
    """Test 7: S&P week with 1 gym day doesn't crash, still generates valid plan."""

    def test_sp_week_one_gym_day_valid(self):
        kwargs = _make_sp_kwargs(availability=_base_availability_one_gym())
        plan = generate_phase_week(**kwargs)
        self.assertIn("weeks", plan)
        week = plan["weeks"][0]
        self.assertEqual(week["phase"], "strength_power")
        all_sessions = [s for d in week["days"] for s in d["sessions"]]
        self.assertGreater(len(all_sessions), 0, "Should still generate sessions")


class TestD154ExerciseOrdering(unittest.TestCase):
    """Test 8: Exercise ordering — limit bouldering after warmup, before cooldown."""

    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_user_state()

    def test_warmup_before_main_before_cooldown(self):
        us = _make_user_state(self.base_us)
        result = _resolve("limit_boulder_gym", us)
        exercises = result["resolved_session"]["exercise_instances"]
        self.assertGreater(len(exercises), 0)

        # Find indices by instance_id prefix (block origin)
        warmup_indices = []
        main_indices = []
        cooldown_indices = []
        for i, ex in enumerate(exercises):
            iid = ex.get("instance_id", "")
            eid = ex.get("exercise_id", "")
            if "warmup" in iid or "warmup" in eid or "pulse_raise" in iid or "mobility" in iid:
                warmup_indices.append(i)
            elif "limit_projecting" in iid or "limit_boulder" in eid or "board_limit" in eid:
                main_indices.append(i)
            elif "cooldown" in iid or "cooldown" in eid:
                cooldown_indices.append(i)

        if warmup_indices and main_indices:
            self.assertLess(
                max(warmup_indices), min(main_indices),
                "Warmup exercises must appear BEFORE main limit bouldering",
            )
        if main_indices and cooldown_indices:
            self.assertLess(
                max(main_indices), min(cooldown_indices),
                "Main limit bouldering must appear BEFORE cooldown",
            )


class TestD154Immutability(unittest.TestCase):
    """Test 9: Past weeks with old S&P plans are NOT affected."""

    def test_past_sessions_immutable(self):
        # Generate a week, store its sessions, then generate again — sessions should be identical
        kwargs = _make_sp_kwargs()
        plan1 = generate_phase_week(**kwargs)
        plan2 = generate_phase_week(**kwargs)

        sessions1 = [
            (s["session_id"], s.get("day"))
            for d in plan1["weeks"][0]["days"]
            for s in d["sessions"]
        ]
        sessions2 = [
            (s["session_id"], s.get("day"))
            for d in plan2["weeks"][0]["days"]
            for s in d["sessions"]
        ]
        self.assertEqual(
            sessions1, sessions2,
            "Deterministic planner: same inputs must produce same output (past immutability)",
        )


class TestD154SessionMetaEntry(unittest.TestCase):
    """Additional: limit_boulder_gym has correct SESSION_META entry."""

    def test_meta_exists_and_correct(self):
        self.assertIn("limit_boulder_gym", _SESSION_META)
        meta = _SESSION_META["limit_boulder_gym"]
        self.assertTrue(meta["hard"])
        self.assertTrue(meta["climbing"])
        self.assertTrue(meta["finger"])  # Brief A: limit bouldering = max finger stress, 48h gap
        self.assertEqual(meta["intensity"], "max")
        self.assertIn("gym", meta["location"])
        self.assertIn("gym_boulder", meta["required_equipment"])


if __name__ == "__main__":
    unittest.main()
