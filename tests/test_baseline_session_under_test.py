import json
import os
import unittest
from copy import deepcopy

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
from catalog.engine.resolve_session import resolve_session  # noqa: E402

def load_json(rel_path: str):
    with open(os.path.join(REPO_ROOT, rel_path), "r", encoding="utf-8") as f:
        return json.load(f)

def get_session_path():
    return load_json("config/session_under_test.json")["session_path"]

def run_case(location: str, gym_id: str | None):
    base_us = load_json("data/user_state.json")
    us = deepcopy(base_us)
    us.setdefault("context", {})
    us["context"]["location"] = location
    us["context"]["gym_id"] = gym_id
    return resolve_session(
        repo_root=REPO_ROOT,
        session_path=get_session_path(),
        templates_dir="catalog/templates",
        exercises_path="catalog/exercises/v1/exercises.json",
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

    def test_home_hangboard(self):
        out = run_case("home", None)
        self.assertEqual(out.get("resolution_status"), "success")
        self.assertEqual(out.get("context", {}).get("location"), "home")
        self.assert_instruction_only(out, "general_warmup.pulse_raise", must_have_keys=("options","duration_min_range"))
        self.assert_instruction_only(out, "general_warmup.mobility", must_have_keys=("focus","duration_min_range"))
        self.assertEqual(out.get("context", {}).get("location"), "home")
        self.assert_instruction_only(out, "general_warmup.pulse_raise", must_have_keys=("options","duration_min_range"))
        self.assert_instruction_only(out, "general_warmup.mobility", must_have_keys=("focus","duration_min_range"))
        self.assert_selected(out, "finger_max_strength.warmup_specific")
        self.assert_selected(out, "finger_max_strength.main")
        self.assert_selected(out, "finger_max_strength.cooldown_prehab_light")
        self.assert_selected(out, "core_short.main")

    def test_gym_blocx(self):
        out = run_case("gym", "blocx")
        self.assertEqual(out.get("resolution_status"), "success")
        self.assert_selected(out, "finger_max_strength.warmup_specific")
        self.assert_selected(out, "finger_max_strength.main")
        self.assert_selected(out, "finger_max_strength.cooldown_prehab_light")
        self.assert_selected(out, "core_short.main")
        self.assertEqual(out.get("context", {}).get("gym_id"), "blocx")

if __name__ == "__main__":
    unittest.main()
