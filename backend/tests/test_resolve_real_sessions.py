"""Integration tests: resolve every real session file from catalog/sessions/v1/.

Ensures that the resolver produces valid output for all real session files,
not just synthetic test sessions. This catches issues like inline blocks
being silently ignored (F1) or missing template references.
"""

import json
import os
import unittest
from copy import deepcopy

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.engine.resolve_session import resolve_session  # noqa: E402


def _load_user_state():
    with open(os.path.join(REPO_ROOT, "backend", "tests", "fixtures", "test_user_state.json")) as f:
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
        out_path=f"output/__test_real_{session_id}.json",
        user_state_override=user_state,
        write_output=False,
    )


# Sessions that are intentionally short (< 3 exercises is acceptable)
_SHORT_SESSIONS = {"yoga_recovery", "flexibility_full"}

# Minimum exercises for normal vs short sessions
_MIN_EXERCISES_NORMAL = 3
_MIN_EXERCISES_SHORT = 1


class TestResolveAllRealSessions(unittest.TestCase):
    """Resolve every real session file and validate output."""

    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_user_state()
        cls.sessions_dir = os.path.join(REPO_ROOT, "backend", "catalog", "sessions", "v1")
        cls.session_files = sorted(
            f.replace(".json", "")
            for f in os.listdir(cls.sessions_dir)
            if f.endswith(".json") and not f.startswith("__test__")
        )

    def test_all_sessions_resolve_successfully(self):
        """Every session must resolve with status=success."""
        failures = []
        for sid in self.session_files:
            with open(os.path.join(self.sessions_dir, f"{sid}.json")) as f:
                session = json.load(f)
            loc = (session.get("context") or {}).get("location", "home")
            gym_id = "blocx" if loc == "gym" else None
            us = _make_user_state(self.base_us, loc, gym_id)

            result = _resolve(sid, us)
            if result["resolution_status"] != "success":
                failures.append(f"{sid}: status={result['resolution_status']}")

        self.assertEqual(failures, [], f"Sessions with non-success status:\n" + "\n".join(failures))

    def test_all_sessions_produce_exercises(self):
        """Every session must produce at least the minimum number of exercises."""
        failures = []
        for sid in self.session_files:
            with open(os.path.join(self.sessions_dir, f"{sid}.json")) as f:
                session = json.load(f)
            loc = (session.get("context") or {}).get("location", "home")
            gym_id = "blocx" if loc == "gym" else None
            us = _make_user_state(self.base_us, loc, gym_id)

            result = _resolve(sid, us)
            n = len(result["resolved_session"]["exercise_instances"])
            min_ex = _MIN_EXERCISES_SHORT if sid in _SHORT_SESSIONS else _MIN_EXERCISES_NORMAL
            if n < min_ex:
                failures.append(f"{sid}: {n} exercises (min {min_ex})")

        self.assertEqual(failures, [], f"Sessions with too few exercises:\n" + "\n".join(failures))

    def test_no_failed_blocks(self):
        """No block should have status=failed."""
        failures = []
        for sid in self.session_files:
            with open(os.path.join(self.sessions_dir, f"{sid}.json")) as f:
                session = json.load(f)
            loc = (session.get("context") or {}).get("location", "home")
            gym_id = "blocx" if loc == "gym" else None
            us = _make_user_state(self.base_us, loc, gym_id)

            result = _resolve(sid, us)
            for b in result["resolved_session"]["blocks"]:
                if b.get("status") == "failed":
                    failures.append(f"{sid}: block {b.get('block_uid')} failed")

        self.assertEqual(failures, [], f"Blocks with failed status:\n" + "\n".join(failures))

    def test_all_blocks_have_filter_trace(self):
        """Every block must have a filter_trace with p_stage and counts."""
        failures = []
        for sid in self.session_files:
            with open(os.path.join(self.sessions_dir, f"{sid}.json")) as f:
                session = json.load(f)
            loc = (session.get("context") or {}).get("location", "home")
            gym_id = "blocx" if loc == "gym" else None
            us = _make_user_state(self.base_us, loc, gym_id)

            result = _resolve(sid, us)
            for b in result["resolved_session"]["blocks"]:
                ft = b.get("filter_trace")
                if not ft or "p_stage" not in ft or "counts" not in ft:
                    failures.append(f"{sid}: block {b.get('block_uid')} missing filter_trace")

        self.assertEqual(failures, [], f"Blocks missing filter_trace:\n" + "\n".join(failures))

    def test_resolution_is_deterministic(self):
        """Resolving the same session twice must produce identical exercise lists."""
        for sid in self.session_files:
            with open(os.path.join(self.sessions_dir, f"{sid}.json")) as f:
                session = json.load(f)
            loc = (session.get("context") or {}).get("location", "home")
            gym_id = "blocx" if loc == "gym" else None

            us_a = _make_user_state(self.base_us, loc, gym_id)
            us_b = _make_user_state(self.base_us, loc, gym_id)

            result_a = _resolve(sid, us_a)
            result_b = _resolve(sid, us_b)

            ids_a = [e["exercise_id"] for e in result_a["resolved_session"]["exercise_instances"]]
            ids_b = [e["exercise_id"] for e in result_b["resolved_session"]["exercise_instances"]]
            self.assertEqual(ids_a, ids_b, f"{sid}: non-deterministic resolution")


class TestPullingStrengthGym(unittest.TestCase):
    """Specific tests for the new pulling_strength_gym session."""

    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_user_state()

    def _resolve_pulling(self):
        us = _make_user_state(self.base_us, "gym", "blocx")
        return _resolve("pulling_strength_gym", us)

    def test_resolves_successfully(self):
        result = self._resolve_pulling()
        self.assertEqual(result["resolution_status"], "success")

    def test_contains_three_pull_vertical_exercises(self):
        """pulling_strength_compound now uses P0 — must resolve 3 distinct pull_vertical exercises."""
        import json
        with open("backend/catalog/exercises/v1/exercises.json") as f:
            ex_data = json.load(f)
        pull_vertical_ids = {
            e["id"] for e in ex_data["exercises"]
            if "pull_vertical" in ([e.get("pattern")] if isinstance(e.get("pattern"), str) else (e.get("pattern") or []))
            and "strength_general" in (e.get("domain") or [])
        }
        result = self._resolve_pulling()
        ids = [e["exercise_id"] for e in result["resolved_session"]["exercise_instances"]]
        pull_selected = [eid for eid in ids if eid in pull_vertical_ids]
        self.assertGreaterEqual(len(pull_selected), 3, f"Expected ≥3 pull_vertical exercises, got: {pull_selected}")
        # All 3 must be unique (rotation working)
        self.assertEqual(len(pull_selected), len(set(pull_selected)), f"Duplicate pull exercises: {pull_selected}")

    def test_has_load_score(self):
        result = self._resolve_pulling()
        self.assertGreater(result.get("session_load_score", 0), 0)

    def test_has_antagonist_prehab(self):
        """Antagonist prehab block must be present (required=true)."""
        result = self._resolve_pulling()
        block_ids = [b.get("block_uid", "") for b in result["resolved_session"]["blocks"]]
        has_prehab = any("antagonist" in bid or "prehab" in bid for bid in block_ids)
        self.assertTrue(has_prehab, f"No antagonist/prehab block found. Blocks: {block_ids}")


class TestTestSessionsResolveExactExercise(unittest.TestCase):
    """Test sessions must resolve exactly the hardcoded test exercise in main block."""

    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_user_state()

    def _main_exercise_ids(self, session_id):
        us = _make_user_state(self.base_us, "gym", "blocx")
        result = _resolve(session_id, us)
        self.assertEqual(result["resolution_status"], "success")
        return [
            e["exercise_id"]
            for e in result["resolved_session"]["exercise_instances"]
            if e.get("category") == "main_strength"
        ]

    def test_max_hang_7s_resolves_exact_exercise(self):
        """D85: test_max_hang_5s session now resolves to max_hang_7s via updated template."""
        ids = self._main_exercise_ids("test_max_hang_5s")
        self.assertEqual(ids, ["max_hang_7s"])

    def test_repeater_7_3_resolves_exact_exercise(self):
        """B133: test session now resolves to test_repeater_7_3_to_failure (category=test)."""
        us = _make_user_state(self.base_us, "gym", "blocx")
        result = _resolve("test_repeater_7_3", us)
        self.assertEqual(result["resolution_status"], "success")
        ids = [
            e["exercise_id"]
            for e in result["resolved_session"]["exercise_instances"]
            if e.get("category") == "test"
        ]
        self.assertEqual(ids, ["test_repeater_7_3_to_failure"])

    def test_max_weighted_pullup_resolves_exact_exercise(self):
        ids = self._main_exercise_ids("test_max_weighted_pullup")
        self.assertEqual(ids, ["weighted_pullup"])

    def test_max_weighted_pullup_2rm_protocol(self):
        """D84: Weighted pullup test session must use 2RM protocol: reps==2 and rest>=180."""
        us = _make_user_state(self.base_us, "gym", "blocx")
        result = _resolve("test_max_weighted_pullup", us)
        self.assertEqual(result["resolution_status"], "success")
        wp = [
            e for e in result["resolved_session"]["exercise_instances"]
            if e["exercise_id"] == "weighted_pullup"
        ]
        self.assertEqual(len(wp), 1)
        p = wp[0]["prescription"]
        self.assertEqual(p["reps"], 2, "2RM test must have reps == 2")
        self.assertGreaterEqual(
            p["rest_between_sets_seconds"], 180,
            "2RM test must have rest >= 180s between sets",
        )


class TestInlineBlockExplicitExerciseId(unittest.TestCase):
    """B174: _resolve_inline_block must respect selection.primary.exercise_id."""

    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_user_state()

    def _resolve_heavy_conditioning(self):
        us = _make_user_state(self.base_us, "gym", "blocx")
        return _resolve("heavy_conditioning_gym", us)

    def test_heavy_conditioning_gym_contains_dip(self):
        """B174: triceps_dip block must resolve to 'dip', not a random exercise."""
        result = self._resolve_heavy_conditioning()
        ex_ids = [e["exercise_id"] for e in result["resolved_session"]["exercise_instances"]]
        self.assertIn("dip", ex_ids, "triceps_dip block must resolve to exercise_id='dip'")

    def test_heavy_conditioning_gym_contains_hanging_leg_raise(self):
        """B174: core_compression block must resolve to 'hanging_leg_raise'."""
        result = self._resolve_heavy_conditioning()
        ex_ids = [e["exercise_id"] for e in result["resolved_session"]["exercise_instances"]]
        self.assertIn(
            "hanging_leg_raise", ex_ids,
            "core_compression block must resolve to exercise_id='hanging_leg_raise'",
        )

    def test_explicit_exercise_id_prescription_overrides_applied(self):
        """B174: prescription_overrides from selection.primary are applied over exercise defaults."""
        result = self._resolve_heavy_conditioning()
        dip_instances = [
            e for e in result["resolved_session"]["exercise_instances"]
            if e["exercise_id"] == "dip"
        ]
        self.assertEqual(len(dip_instances), 1)
        p = dip_instances[0]["prescription"]
        self.assertEqual(p.get("sets"), 3, "prescription_overrides.sets must be 3 for dip")
        self.assertEqual(p.get("reps"), 10, "prescription_overrides.reps must be 10 for dip")
        self.assertEqual(
            p.get("rest_between_sets_seconds"), 60,
            "prescription_overrides.rest must be 60s for dip",
        )

    def test_inline_block_without_exercise_id_uses_p0(self):
        """B174: inline blocks without exercise_id still use P0 filters (no regression)."""
        result = self._resolve_heavy_conditioning()
        blocks = result["resolved_session"]["blocks"]
        # compound_pull block has no exercise_id — picked_by must NOT be explicit_exercise_id
        pull_blocks = [b for b in blocks if "compound_pull" in b.get("block_uid", "")]
        self.assertTrue(len(pull_blocks) > 0, "compound_pull block must be present")
        for b in pull_blocks:
            source = b.get("selected_exercises", [{}])[0].get("source", {}) if b.get("selected_exercises") else {}
            picked_by = source.get("picked_by", "")
            self.assertNotIn(
                "explicit_exercise_id", picked_by,
                "compound_pull block must use P0, not explicit_exercise_id",
            )

    def test_explicit_exercise_id_block_uid_source(self):
        """B174: exercise_instances for dip have picked_by containing 'explicit_exercise_id'."""
        result = self._resolve_heavy_conditioning()
        dip_instances = [
            e for e in result["resolved_session"]["exercise_instances"]
            if e["exercise_id"] == "dip"
        ]
        self.assertEqual(len(dip_instances), 1)
        picked_by = dip_instances[0].get("source", {}).get("picked_by", "")
        self.assertIn(
            "explicit_exercise_id", picked_by,
            f"dip must be picked via explicit_exercise_id, got '{picked_by}'",
        )


if __name__ == "__main__":
    unittest.main()
