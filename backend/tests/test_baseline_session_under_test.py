from __future__ import annotations
import json
import os
import unittest
from copy import deepcopy

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.engine.resolve_session import resolve_session  # noqa: E402

def load_json(rel_path: str):
    with open(os.path.join(REPO_ROOT, rel_path), "r", encoding="utf-8") as f:
        return json.load(f)

def get_session_path():
    return "backend/catalog/sessions/v1/strength_long.json"

def run_case(location: str, gym_id: str | None):
    base_us = load_json("backend/tests/fixtures/test_user_state.json")
    us = deepcopy(base_us)
    us.setdefault("context", {})
    us["context"]["location"] = location
    us["context"]["gym_id"] = gym_id
    return resolve_session(
        repo_root=REPO_ROOT,
        session_path=get_session_path(),
        templates_dir="backend/catalog/templates",
        exercises_path="backend/catalog/exercises/v1/exercises.json",
        out_path="tmp/__test_out.json",
        user_state_override=us,
        write_output=False,
    )

class TestBaselineSessionUnderTest(unittest.TestCase):
    def assert_selected(self, out, uid: str):
        blocks = {b["block_uid"]: b for b in out["resolved_session"]["blocks"]}
        self.assertIn(uid, blocks, f"Missing {uid}")
        self.assertEqual(blocks[uid].get("status"), "selected", f"{uid} not selected")
        self.assertIn("filter_trace", blocks[uid], f"{uid} missing filter_trace")

    def assert_instruction_only(self, out, uid: str, must_have_keys=()):
        blocks = {b["block_uid"]: b for b in out["resolved_session"]["blocks"]}
        self.assertIn(uid, blocks, f"Missing {uid}")
        b = blocks[uid]
        self.assertEqual(b.get("status"), "selected", f"{uid} not selected")
        self.assertEqual(b.get("selected_exercises"), [], f"{uid} should have no selected_exercises")
        self.assertIn("filter_trace", b, f"{uid} missing filter_trace")
        self.assertIn("instructions", b, f"{uid} missing instructions")
        for k in must_have_keys:
            self.assertIn(k, b["instructions"], f"{uid} instructions missing key: {k}")


    def assert_has_suggested_load(self, out, exercise_id: str):
        insts = out.get("resolved_session", {}).get("exercise_instances", [])
        inst = next((x for x in insts if x.get("exercise_id") == exercise_id), None)
        self.assertIsNotNone(inst, f"Missing exercise_instance for {exercise_id}")
        self.assertIn("suggested", inst, f"{exercise_id} missing suggested")
        sug = inst.get("suggested") or {}
        self.assertIn("target_total_load_kg", sug)
        self.assertTrue(("added_weight_kg" in sug) or ("assistance_kg" in sug))

    def test_gym_blocx(self):
        """strength_long v2 at Blocx gym: warmup_climbing + finger_max + core_standard + antagonist + cooldown."""
        out = run_case("gym", "blocx")
        self.assertEqual(out.get("resolution_status"), "success")
        # Warmup climbing template
        self.assert_instruction_only(out, "warmup_climbing.pulse_raise", must_have_keys=("options", "duration_min_range"))
        self.assert_instruction_only(out, "warmup_climbing.mobility", must_have_keys=("focus", "duration_min_range"))
        self.assert_selected(out, "warmup_climbing.upper_activation")
        # Finger max strength template
        self.assert_selected(out, "finger_max_strength.warmup_specific")
        self.assert_selected(out, "finger_max_strength.main")
        self.assert_selected(out, "finger_max_strength.cooldown_prehab_light")
        # Core standard template
        self.assert_selected(out, "core_standard.core_main")
        # Antagonist prehab template
        self.assert_selected(out, "antagonist_prehab.antagonist_push")
        self.assert_selected(out, "antagonist_prehab.shoulder_prehab")
        # Cooldown stretch template
        self.assert_selected(out, "cooldown_stretch.forearm_wrist")
        self.assert_selected(out, "cooldown_stretch.hip_flexibility")
        self.assert_selected(out, "cooldown_stretch.general_flexibility")
        self.assertEqual(out.get("context", {}).get("gym_id"), "blocx")
        # Verify a finger strength exercise is selected in the main block
        insts = out.get("resolved_session", {}).get("exercise_instances", [])
        finger_ids = {"max_hang_5s", "max_hang_7s", "max_hang_ladder", "max_hang_10s", "horst_7_53",
                      "min_edge_hang", "one_arm_hang_assisted", "grip_transitions_half_to_open"}
        selected = [x for x in insts if x.get("exercise_id") in finger_ids]
        self.assertTrue(len(selected) > 0, f"No finger strength exercise selected. IDs: {[x['exercise_id'] for x in insts]}")
        # If any selected exercise has intensity_pct, it should have suggested load
        with_pct = [x for x in selected if (x.get("attributes") or {}).get("intensity_pct")]
        for x in with_pct:
            self.assertIn("suggested", x, f"{x['exercise_id']} has intensity_pct but no suggested load")

    def test_gym_blocx_location(self):
        """strength_long v2 forces gym location (session context overrides user_state)."""
        out = run_case("gym", "blocx")
        self.assertEqual(out.get("context", {}).get("location"), "gym")

if __name__ == "__main__":
    unittest.main()
