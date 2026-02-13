from __future__ import annotations
import json
import os
import sys
import unittest
from copy import deepcopy

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from backend.engine.resolve_session import resolve_session  # noqa: E402


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def make_user_state(
    base_user_state: dict,
    *,
    location: str,
    gym_id: str | None = None,
    home_equipment: list[str] | None = None,
    gym_equipment_override: dict[str, list[str]] | None = None,
):
    us = deepcopy(base_user_state)
    us.setdefault("context", {})
    us["context"]["location"] = location
    us["context"]["gym_id"] = gym_id

    if home_equipment is not None:
        us.setdefault("equipment", {})
        us["equipment"]["home"] = home_equipment

    if gym_equipment_override:
        us.setdefault("equipment", {})
        gyms = us["equipment"].get("gyms", [])
        for g in gyms:
            gid = g.get("gym_id")
            if gid in gym_equipment_override:
                g["equipment"] = gym_equipment_override[gid]
    return us


def make_session_file(
    *,
    session_id: str,
    context_location: str,
    context_gym_id: str | None,
    finger_module_required: bool,
):
    return {
        "id": session_id,
        "version": "1.0",
        "context": {"location": context_location, "gym_id": context_gym_id},
        "modules": [
            {"template_id": "general_warmup", "version": "v1", "required": True},
            {"template_id": "finger_max_strength", "version": "v1", "required": finger_module_required},
            {"template_id": "core_short", "version": "v1", "required": False},
        ],
    }


def make_gym_power_bouldering_session_file(*, session_id: str, context_gym_id: str | None):
    return {
        "id": session_id,
        "version": "1.0",
        "context": {"location": "gym", "gym_id": context_gym_id},
        "modules": [
            {"template_id": "gym_power_bouldering", "version": "v1", "required": True}
        ],
    }


class TestResolverP0Determinism(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_user_state = load_json(os.path.join(REPO_ROOT, "backend", "data", "user_state.json"))

    def assert_filter_trace_present(self, out: dict):
        for b in out["resolved_session"]["blocks"]:
            self.assertIn("filter_trace", b, f"Missing filter_trace: {b.get('block_uid')}")
            ft = b["filter_trace"]
            self.assertIn("p_stage", ft, f"Missing filter_trace.p_stage: {b.get('block_uid')}")
            self.assertIn("counts", ft, f"Missing filter_trace.counts: {b.get('block_uid')}")




    def run_resolve(self, user_state_override: dict, session_obj: dict):
        rel_session_path = os.path.join("catalog", "sessions", "v1", f"__test__{session_obj['id']}.json")
        abs_session_path = os.path.join(REPO_ROOT, rel_session_path)
        write_json(abs_session_path, session_obj)

        try:
            out = resolve_session(
                repo_root=REPO_ROOT,
                session_path=rel_session_path,
                templates_dir="backend/catalog/templates",
                exercises_path="backend/catalog/exercises/v1/exercises.json",
                out_path="output/__test_out.json",
                user_state_override=user_state_override,
                write_output=False,
            )
        finally:
            if os.path.exists(abs_session_path):
                os.remove(abs_session_path)
        return out

    def assert_no_silent_blocks(self, out: dict):
        blocks = out["resolved_session"]["blocks"]
        for b in blocks:
            self.assertIsNotNone(b.get("status"), f"Silent block: {b.get('block_uid')}")

    def test_home_no_hangboard_optional_finger(self):
        us = make_user_state(
            self.base_user_state,
            location="home",
            gym_id=None,
            home_equipment=["pullup_bar", "dumbbell", "band"],  # no hangboard
        )
        sess = make_session_file(
            session_id="home_no_hb",
            context_location="home",
            context_gym_id=None,
            finger_module_required=False,
        )
        out = self.run_resolve(us, sess)
        self.assertEqual(out["resolution_status"], "success")
        self.assert_no_silent_blocks(out)
        self.assert_filter_trace_present(out)


    def test_home_hangboard_required_finger(self):
        us = make_user_state(self.base_user_state, location="home", gym_id=None)
        sess = make_session_file(
            session_id="home_hb",
            context_location="home",
            context_gym_id=None,
            finger_module_required=True,
        )
        out = self.run_resolve(us, sess)
        self.assertEqual(out["resolution_status"], "success")
        self.assert_no_silent_blocks(out)
        self.assert_filter_trace_present(out)


        ids = [x["exercise_id"] for x in out["resolved_session"]["exercise_instances"]]
        self.assertTrue(any(i for i in ids), "No exercises resolved at all.")

    def test_gym_blocx(self):
        us = make_user_state(self.base_user_state, location="gym", gym_id="blocx")
        sess = make_session_file(
            session_id="gym_blocx",
            context_location="gym",
            context_gym_id="blocx",
            finger_module_required=True,
        )
        out = self.run_resolve(us, sess)
        self.assertEqual(out["resolution_status"], "success")
        self.assert_no_silent_blocks(out)
        self.assertEqual(out["context"]["gym_id"], "blocx")

    def test_gym_blocx_plus_pangullich(self):
        gyms = self.base_user_state.get("equipment", {}).get("gyms", [])
        blocx = next((g for g in gyms if g.get("gym_id") == "blocx"), None)
        base_eq = deepcopy(blocx.get("equipment", []) if blocx else [])
        if "pangullich" not in base_eq:
            base_eq.append("pangullich")

        us = make_user_state(
            self.base_user_state,
            location="gym",
            gym_id="blocx",
            gym_equipment_override={"blocx": base_eq},
        )
        sess = make_session_file(
            session_id="gym_pang",
            context_location="gym",
            context_gym_id="blocx",
            finger_module_required=True,
        )
        out = self.run_resolve(us, sess)
        self.assertEqual(out["resolution_status"], "success")
        self.assert_no_silent_blocks(out)
        self.assert_filter_trace_present(out)
        self.assertIn("pangullich", out["context"]["available_equipment"])

    def test_outdoor_optional_finger(self):
        us = make_user_state(self.base_user_state, location="outdoor", gym_id=None)
        sess = make_session_file(
            session_id="outdoor",
            context_location="outdoor",
            context_gym_id=None,
            finger_module_required=False,
        )
        out = self.run_resolve(us, sess)
        self.assertEqual(out["resolution_status"], "success")
        self.assert_no_silent_blocks(out)

    def test_outdoor_performance_day_optional_finger(self):
        us = make_user_state(self.base_user_state, location="outdoor", gym_id=None)
        sess = make_session_file(
            session_id="outdoor_perf",
            context_location="outdoor",
            context_gym_id=None,
            finger_module_required=False,
        )
        sess["intent"] = {"performance_day": True}

        out = self.run_resolve(us, sess)
        self.assertEqual(out["resolution_status"], "success")
        self.assert_no_silent_blocks(out)
        self.assert_filter_trace_present(out)


    def _resolve_gym_power_with_equipment(self, equipment: list[str], session_id: str):
        us = make_user_state(
            self.base_user_state,
            location="gym",
            gym_id="blocx",
            gym_equipment_override={"blocx": equipment},
        )
        sess = make_gym_power_bouldering_session_file(session_id=session_id, context_gym_id="blocx")
        return self.run_resolve(us, sess)

    def _main_block(self, out: dict) -> dict:
        return next(b for b in out["resolved_session"]["blocks"] if b.get("block_uid") == "gym_power_bouldering.main")

    def test_gym_limit_bouldering_selected_with_spraywall(self):
        out = self._resolve_gym_power_with_equipment(["spraywall"], "gym_spraywall")
        self.assertEqual(out["resolution_status"], "success")
        ids = [x["exercise_id"] for x in out["resolved_session"]["exercise_instances"]]
        self.assertIn("gym_limit_bouldering", ids)

    def test_gym_limit_bouldering_selected_with_board_kilter(self):
        out = self._resolve_gym_power_with_equipment(["board_kilter"], "gym_board_kilter")
        self.assertEqual(out["resolution_status"], "success")
        ids = [x["exercise_id"] for x in out["resolved_session"]["exercise_instances"]]
        self.assertIn("gym_limit_bouldering", ids)

    def test_gym_limit_bouldering_selected_with_gym_boulder(self):
        out = self._resolve_gym_power_with_equipment(["gym_boulder"], "gym_gym_boulder")
        self.assertEqual(out["resolution_status"], "success")
        ids = [x["exercise_id"] for x in out["resolved_session"]["exercise_instances"]]
        self.assertIn("gym_limit_bouldering", ids)

    def test_gym_limit_bouldering_skipped_without_required_any_equipment(self):
        out = self._resolve_gym_power_with_equipment(["hangboard"], "gym_no_limit_tools")
        self.assertEqual(out["resolution_status"], "success")
        ids = [x["exercise_id"] for x in out["resolved_session"]["exercise_instances"]]
        self.assertNotIn("gym_limit_bouldering", ids)
        self.assertIn("density_hang_10_10", ids)
        main_block = self._main_block(out)
        self.assertEqual(main_block.get("status"), "selected")
        self.assertEqual(main_block.get("selected_exercises", [])[0].get("exercise_id"), "density_hang_10_10")


if __name__ == "__main__":
    unittest.main()
