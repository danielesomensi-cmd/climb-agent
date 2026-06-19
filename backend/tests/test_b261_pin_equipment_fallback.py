"""B261 — Pinned exercise_id must fall back to P0 when equipment-incompatible.

Source: D248 audit, root cause L2 (filter bypassed). An explicit `exercise_id`
pin in a template/inline block used to bypass `pick_best_exercise_p0` entirely
(B174), so the equipment filter never ran for it. Result: `warmup_easy_boulders`
(tagged `equipment_required_any` = climbing surfaces) was forced into a session
at a commercial gym with no wall.

Fix: a pin is honored only if equipment-compatible. Otherwise:
  - non-test pin  -> delegate to P0 with the block's role/domain (may skip if
    zero candidates),
  - test pin      -> skip the block (never substitute a different measurement).

These tests lock both the fallback and the test-substitution guard, plus the
immutability of completed sessions.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from backend.engine.resolve_session import (  # noqa: E402
    resolve_session,
    ex_equipment_required,
    ex_equipment_required_any,
    _pin_equipment_ok,
    _is_test_exercise,
)

EXERCISES_PATH = os.path.join(REPO_ROOT, "backend/catalog/exercises/v1/exercises.json")
SESSIONS_DIR = "backend/catalog/sessions/v1"
TEMPLATES_DIR = "backend/catalog/templates/v1"

CLIMBING_SURFACES = {
    "gym_boulder", "board_kilter", "board_moonboard",
    "board_other", "spraywall", "homewall", "gym_routes",
}

COMMERCIAL_GYM = ["pullup_bar", "dumbbell", "band", "bench"]
WALL_GYM = ["pullup_bar", "gym_boulder", "hangboard"]
NO_HANGBOARD_GYM = ["pullup_bar", "dumbbell", "weight", "bench"]


def _by_id():
    with open(EXERCISES_PATH, "r", encoding="utf-8") as f:
        return {e["id"]: e for e in json.load(f)["exercises"]}


def _needs_climbing(ex):
    eq = set(ex_equipment_required(ex)) | set(ex_equipment_required_any(ex))
    return bool(eq & CLIMBING_SURFACES)


def _resolve(session_id, gym_equipment, gym_id="g1", session_path=None, templates_dir=None):
    state = {
        "context": {"location": "gym", "gym_id": gym_id},
        "equipment": {
            "gyms": [{"gym_id": gym_id, "priority": 1, "equipment": gym_equipment}],
            "home": [],
        },
        "defaults": {"location": "gym"},
    }
    return resolve_session(
        repo_root=REPO_ROOT,
        session_path=session_path or f"{SESSIONS_DIR}/{session_id}.json",
        templates_dir=templates_dir or TEMPLATES_DIR,
        exercises_path=EXERCISES_PATH,
        out_path="",
        user_state_override=state,
        write_output=False,
        user_id=None,
    )


def _blocks(resolved):
    return resolved["resolved_session"]["blocks"]


def _block(resolved, block_id):
    return next((b for b in _blocks(resolved) if b.get("block_id") == block_id), None)


def _all_ids(resolved):
    return [se.get("exercise_id") for b in _blocks(resolved) for se in b.get("selected_exercises", [])]


class TestB261Helpers(unittest.TestCase):
    def test_pin_equipment_ok_honors_required_any(self):
        ex = _by_id()
        # warmup_easy_boulders: equipment_required_any = climbing surfaces
        web = ex["warmup_easy_boulders"]
        self.assertFalse(_pin_equipment_ok(web, COMMERCIAL_GYM))
        self.assertTrue(_pin_equipment_ok(web, ["gym_boulder"]))
        # general_pulse_raise: no equipment -> always ok (universal pin)
        self.assertTrue(_pin_equipment_ok(ex["general_pulse_raise"], []))

    def test_is_test_exercise(self):
        ex = _by_id()
        self.assertTrue(_is_test_exercise(ex["max_hang_7s"]))
        self.assertFalse(_is_test_exercise(ex["warmup_easy_boulders"]))


class TestB261NonTestPin(unittest.TestCase):
    def test_incompatible_climbing_pin_falls_back_to_p0(self):
        # strength_long pins warmup_easy_boulders in climbing_activation.
        resolved = _resolve("strength_long", COMMERCIAL_GYM)
        self.assertEqual(resolved.get("resolution_status"), "success")

        ca = _block(resolved, "climbing_activation")
        self.assertIsNotNone(ca)
        picked = [se.get("exercise_id") for se in ca.get("selected_exercises", [])]
        self.assertNotIn("warmup_easy_boulders", picked,
                         "incompatible climbing pin must not be forced")

        # No climbing-surface exercise anywhere in the resolved session (full repro,
        # with C243 retag already on main).
        leaked = [x for x in _all_ids(resolved) if _needs_climbing(_by_id().get(x, {}))]
        self.assertEqual(leaked, [], f"climbing-surface exercises leaked: {leaked}")

    def test_universal_pin_still_honored(self):
        # general_pulse_raise (no equipment) is pinned in the warmup — must survive.
        resolved = _resolve("strength_long", COMMERCIAL_GYM)
        self.assertIn("general_pulse_raise", _all_ids(resolved))

    def test_compatible_climbing_pin_honored_at_wall_gym(self):
        # Regression: with a wall present the pin is honored verbatim.
        resolved = _resolve("strength_long", WALL_GYM, gym_id="gw")
        ca = _block(resolved, "climbing_activation")
        picked = [se.get("exercise_id") for se in ca.get("selected_exercises", [])]
        self.assertEqual(picked, ["warmup_easy_boulders"])


class TestB261TestPinGuard(unittest.TestCase):
    def test_incompatible_test_pin_skipped_not_substituted(self):
        # test_max_hang_7s pins max_hang_7s (hangboard) in the main block.
        resolved = _resolve("test_max_hang_7s", NO_HANGBOARD_GYM, gym_id="gt")
        self.assertEqual(resolved.get("resolution_status"), "success")

        main = _block(resolved, "main")
        self.assertIsNotNone(main)
        self.assertEqual(main.get("selected_exercises"), [],
                         "incompatible test pin must be skipped, never substituted")
        # The wrong-axis test must not appear in place of the hang test.
        self.assertNotIn("test_hip_flexibility",
                         [se.get("exercise_id") for se in main.get("selected_exercises", [])])

    def test_compatible_test_pin_honored(self):
        # Regression: with a hangboard the test measurement is honored.
        resolved = _resolve("test_max_hang_7s", WALL_GYM, gym_id="gth")
        main = _block(resolved, "main")
        picked = [se.get("exercise_id") for se in main.get("selected_exercises", [])]
        self.assertEqual(picked, ["max_hang_7s"])


class TestB261ZeroCandidateSkip(unittest.TestCase):
    def test_incompatible_pin_with_zero_p0_candidates_skips_gracefully(self):
        # Synthetic: a non-test block pins a climbing exercise AND its P0 fallback
        # (role=technique) has zero candidates at a no-wall gym (all technique
        # drills are wall-gated since C243). Must skip gracefully, no exception.
        tmpdir = tempfile.mkdtemp()
        tpl = {
            "id": "b261_zero",
            "blocks": [
                {"block_id": "warm", "role": ["warmup"], "exercise_id": "general_pulse_raise"},
                {"block_id": "zero_pin", "role": ["technique"],
                 "domain": ["technique_boulder"], "exercise_id": "warmup_easy_boulders"},
            ],
        }
        with open(os.path.join(tmpdir, "b261_zero.json"), "w", encoding="utf-8") as f:
            json.dump(tpl, f)
        sess = {"id": "b261_zero_session", "name": "B261 zero",
                "required_equipment": [], "modules": [{"template_id": "b261_zero"}]}
        sess_path = os.path.join(tmpdir, "b261_zero_session.json")
        with open(sess_path, "w", encoding="utf-8") as f:
            json.dump(sess, f)

        # session_path is resolved relative to repo_root; pass an absolute-ish rel.
        rel_sess = os.path.relpath(sess_path, REPO_ROOT)
        resolved = _resolve("b261_zero_session", COMMERCIAL_GYM, gym_id="gz",
                            session_path=rel_sess, templates_dir=os.path.relpath(tmpdir, REPO_ROOT))

        warm = _block(resolved, "warm")
        zero = _block(resolved, "zero_pin")
        self.assertEqual([se.get("exercise_id") for se in warm.get("selected_exercises", [])],
                         ["general_pulse_raise"], "universal pin still honored")
        self.assertEqual(zero.get("selected_exercises"), [],
                         "incompatible pin with no P0 candidate must skip gracefully")


class TestB261Immutability(unittest.TestCase):
    def test_completed_session_pin_not_stripped(self):
        # A completed session whose cached resolved contains the climbing pin must
        # stay byte-identical across regeneration — the fix must never retroactively
        # strip a pinned exercise from a past/completed session.
        from backend.engine.replanner_v1 import regenerate_preserving_completed

        done_resolved = {"blocks": [{"block_id": "climbing_activation",
                                     "selected_exercises": [{"exercise_id": "warmup_easy_boulders"}]}]}
        old_plan = {"weeks": [{"days": [{
            "date": "2026-01-05",
            "sessions": [{
                "slot": "morning", "status": "done", "session_id": "strength_long",
                "resolved": done_resolved,
            }],
        }]}]}
        new_plan = {"weeks": [{"days": [{
            "date": "2026-01-05",
            "sessions": [{
                "slot": "morning", "status": "planned", "session_id": "strength_long",
            }],
        }]}]}

        before = json.dumps(old_plan["weeks"][0]["days"][0]["sessions"][0], sort_keys=True)
        merged = regenerate_preserving_completed(old_plan, new_plan)
        s = next(x for x in merged["weeks"][0]["days"][0]["sessions"] if x.get("slot") == "morning")
        after = json.dumps(s, sort_keys=True)

        self.assertEqual(s["status"], "done")
        self.assertEqual(before, after, "completed session must be byte-identical")
        ids = [se["exercise_id"] for b in s["resolved"]["blocks"] for se in b["selected_exercises"]]
        self.assertIn("warmup_easy_boulders", ids, "pinned climbing exercise preserved in past session")


if __name__ == "__main__":
    unittest.main()
