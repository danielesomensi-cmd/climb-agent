"""Tests for B8 Session Enrichment.

Validates:
- 11 new exercises exist and have valid schema
- 8 new templates load correctly
- 4 rewritten gym sessions resolve successfully at Blocx
- 1 standalone core session resolves at home
- Cooldown, antagonist, and determinism constraints
"""

import json
import os
import unittest
from copy import deepcopy

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.engine.resolve_session import resolve_session  # noqa: E402


def _load_exercises():
    with open(os.path.join(REPO_ROOT, "backend/catalog/exercises/v1/exercises.json")) as f:
        return json.load(f)["exercises"]


def _load_user_state():
    with open(os.path.join(REPO_ROOT, "backend/tests/fixtures/test_user_state.json")) as f:
        return json.load(f)


def _make_user_state(base, location, gym_id=None):
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
        out_path=f"output/__test_enrichment_{session_id}.json",
        user_state_override=user_state,
        write_output=False,
    )


# ---- Constants ----

NEW_EXERCISE_IDS = [
    "route_redpoint_attempt",
    "cooldown_forearm_wrist_stretch",
    "cooldown_hip_pigeon",
    "cooldown_hip_frog",
    "cooldown_shoulder_chest",
    "cooldown_hamstring_fold",
    "cooldown_spinal_twist",
    "cooldown_deep_squat_hold",
    "flexibility_cossack_squat",
    "flexibility_active_leg_raise",
    "flexibility_ninety_ninety",
]

REQUIRED_EXERCISE_FIELDS = [
    "id", "name", "category", "time_min", "role", "domain", "pattern",
    "intensity_level", "fatigue_cost", "recency_group", "equipment_required",
    "location_allowed", "contraindications", "prescription_defaults", "stress_tags",
]

NEW_TEMPLATE_IDS = [
    "warmup_climbing",
    "warmup_strength",
    "warmup_recovery",
    "pulling_strength",
    "pulling_endurance",
    "antagonist_prehab",
    "core_standard",
    "cooldown_stretch",
]

GYM_EVENING_SESSIONS = [
    "strength_long",
    "power_contact_gym",
    "power_endurance_gym",
    "endurance_aerobic_gym",
]


class TestNewExercises(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exercises = _load_exercises()
        cls.by_id = {e["id"]: e for e in cls.exercises}

    def test_new_exercises_exist(self):
        """All 11 new exercise IDs present in exercises.json."""
        missing = [eid for eid in NEW_EXERCISE_IDS if eid not in self.by_id]
        self.assertEqual(missing, [], f"Missing exercises: {missing}")

    def test_new_exercises_valid_schema(self):
        """Each new exercise has all required fields."""
        for eid in NEW_EXERCISE_IDS:
            ex = self.by_id[eid]
            for field in REQUIRED_EXERCISE_FIELDS:
                self.assertIn(field, ex, f"{eid} missing field: {field}")


class TestNewTemplates(unittest.TestCase):
    def test_new_templates_load(self):
        """All 8 new template files load as valid JSON with id and blocks."""
        for tid in NEW_TEMPLATE_IDS:
            path = os.path.join(REPO_ROOT, f"backend/catalog/templates/v1/{tid}.json")
            self.assertTrue(os.path.exists(path), f"Template file missing: {tid}")
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["id"], tid, f"Template id mismatch in {tid}")
            self.assertIn("blocks", data, f"Template {tid} missing blocks")
            self.assertIsInstance(data["blocks"], list)
            self.assertGreater(len(data["blocks"]), 0, f"Template {tid} has no blocks")

    def test_new_templates_blocks_have_role_domain(self):
        """Every non-instruction_only block has role[] and domain[] or exercise_id."""
        for tid in NEW_TEMPLATE_IDS:
            path = os.path.join(REPO_ROOT, f"backend/catalog/templates/v1/{tid}.json")
            with open(path) as f:
                data = json.load(f)
            for b in data["blocks"]:
                mode = (b.get("mode") or "").lower()
                if mode == "instruction_only":
                    continue
                # Must have either exercise_id (explicit) or role+domain (dynamic)
                has_explicit = "exercise_id" in b
                has_dynamic = "role" in b and "domain" in b
                self.assertTrue(
                    has_explicit or has_dynamic,
                    f"Template {tid}, block {b.get('block_id')}: "
                    f"needs exercise_id or role+domain for selection"
                )


class TestStrengthLong(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_user_state()
        cls.result = _resolve("strength_long", _make_user_state(cls.base_us, "gym", "blocx"))

    def test_strength_long_resolves_7_modules(self):
        """Resolve strength_long at Blocx gym: status=success, ≥5 exercise instances."""
        self.assertEqual(self.result["resolution_status"], "success")
        exs = self.result["resolved_session"]["exercise_instances"]
        self.assertGreaterEqual(len(exs), 5, f"Expected ≥5 exercises, got {len(exs)}")


class TestPowerContact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_user_state()
        cls.result = _resolve("power_contact_gym", _make_user_state(cls.base_us, "gym", "blocx"))

    def test_power_contact_no_hangboard(self):
        """Resolve power_contact_gym: no finger_max_hang recency_group exercise appears."""
        exercises = _load_exercises()
        max_hang_ids = {e["id"] for e in exercises if e.get("recency_group") == "finger_max_hang"}
        resolved_ids = {e["exercise_id"] for e in self.result["resolved_session"]["exercise_instances"]}
        overlap = max_hang_ids & resolved_ids
        self.assertEqual(overlap, set(), f"Max hang exercises found in power session: {overlap}")


class TestPowerEndurance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_user_state()
        cls.result = _resolve("power_endurance_gym", _make_user_state(cls.base_us, "gym", "blocx"))

    def test_pe_session_has_climbing_then_finger(self):
        """Resolve power_endurance_gym: climbing block precedes finger block in output."""
        exs = self.result["resolved_session"]["exercise_instances"]
        ex_ids = [e["exercise_id"] for e in exs]
        # Find climbing exercise (from pe_climbing_main inline block)
        climbing_exs = {"gym_power_endurance_4x4", "four_by_four_bouldering",
                        "linked_boulder_circuit", "route_intervals"}
        # Find finger exercise (from finger_endurance inline block)
        finger_exs = {"density_hang_10_10", "repeaters_7_3", "long_duration_hang",
                       "min_edge_hang_submaximal"}
        climbing_idx = next((i for i, eid in enumerate(ex_ids) if eid in climbing_exs), None)
        finger_idx = next((i for i, eid in enumerate(ex_ids) if eid in finger_exs), None)
        if climbing_idx is not None and finger_idx is not None:
            self.assertLess(climbing_idx, finger_idx,
                            f"Climbing (idx={climbing_idx}) should come before finger (idx={finger_idx})")


class TestEnduranceAerobic(unittest.TestCase):
    def test_endurance_session_resolves(self):
        """Resolve endurance_aerobic_gym at Blocx: status=success."""
        base_us = _load_user_state()
        result = _resolve("endurance_aerobic_gym", _make_user_state(base_us, "gym", "blocx"))
        self.assertEqual(result["resolution_status"], "success")
        exs = result["resolved_session"]["exercise_instances"]
        self.assertGreaterEqual(len(exs), 3)


class TestCoreStandalone(unittest.TestCase):
    def test_core_standalone_resolves(self):
        """Resolve core_conditioning_standalone at home: status=success, ≥4 exercises."""
        base_us = _load_user_state()
        result = _resolve("core_conditioning_standalone", _make_user_state(base_us, "home"))
        self.assertEqual(result["resolution_status"], "success")
        exs = result["resolved_session"]["exercise_instances"]
        self.assertGreaterEqual(len(exs), 4, f"Expected ≥4 exercises, got {len(exs)}")


class TestCrossSession(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_user_state()

    def test_cooldown_has_forearm_stretch(self):
        """Resolve any gym session: cooldown_forearm_wrist_stretch appears."""
        result = _resolve("strength_long", _make_user_state(self.base_us, "gym", "blocx"))
        ex_ids = {e["exercise_id"] for e in result["resolved_session"]["exercise_instances"]}
        self.assertIn("cooldown_forearm_wrist_stretch", ex_ids)

    def test_antagonist_in_all_gym_sessions(self):
        """For each of the 4 evening sessions, pushup appears in resolved exercises."""
        for sid in GYM_EVENING_SESSIONS:
            result = _resolve(sid, _make_user_state(self.base_us, "gym", "blocx"))
            ex_ids = {e["exercise_id"] for e in result["resolved_session"]["exercise_instances"]}
            self.assertIn("pushup", ex_ids, f"{sid}: missing pushup in resolved exercises")

    def test_all_exercise_refs_exist(self):
        """Load all sessions + templates, extract every exercise_id reference, verify each exists."""
        exercises = _load_exercises()
        catalog_ids = {e["id"] for e in exercises}

        # Collect all explicit exercise_id refs from templates
        templates_dir = os.path.join(REPO_ROOT, "backend/catalog/templates/v1")
        refs = set()
        for fn in os.listdir(templates_dir):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(templates_dir, fn)) as f:
                data = json.load(f)
            for b in data.get("blocks", []):
                eid = b.get("exercise_id")
                if eid:
                    refs.add(eid)

        # Collect from sessions too (though sessions use inline blocks, not exercise_id)
        sessions_dir = os.path.join(REPO_ROOT, "backend/catalog/sessions/v1")
        for fn in os.listdir(sessions_dir):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(sessions_dir, fn)) as f:
                data = json.load(f)
            for m in data.get("modules", []):
                eid = m.get("exercise_id")
                if eid:
                    refs.add(eid)

        missing = refs - catalog_ids
        self.assertEqual(missing, set(), f"exercise_id refs not in catalog: {missing}")

    def test_enriched_sessions_deterministic(self):
        """Resolve each of the 5 sessions twice: identical exercise lists."""
        sessions = GYM_EVENING_SESSIONS + ["core_conditioning_standalone"]
        for sid in sessions:
            loc = "home" if sid == "core_conditioning_standalone" else "gym"
            gym_id = None if loc == "home" else "blocx"

            us_a = _make_user_state(self.base_us, loc, gym_id)
            us_b = _make_user_state(self.base_us, loc, gym_id)

            result_a = _resolve(sid, us_a)
            result_b = _resolve(sid, us_b)

            ids_a = [e["exercise_id"] for e in result_a["resolved_session"]["exercise_instances"]]
            ids_b = [e["exercise_id"] for e in result_b["resolved_session"]["exercise_instances"]]
            self.assertEqual(ids_a, ids_b, f"{sid}: non-deterministic resolution")


if __name__ == "__main__":
    unittest.main()
