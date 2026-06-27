"""B263 — Device-specific prescription must not bleed onto a substituted exercise.

Source: D248 audit, display residual. A device-anchored block (finger_max_strength)
carries hangboard-tuned prescription (notes "Prefer 20mm half crimp… Rest fully
2.5–4 min", `hang_seconds_range`, `intensity_pct_of_total_load_range`). When the
hangboard exercise is equipment-filtered out and P0 substitutes a non-finger
exercise (e.g. archer_pullup), those device params used to bleed onto the
substitute's card.

Fix (B-display): in both prescription-merge paths, when the block carries
device-specific params but the selected exercise is not a finger/device exercise,
strip the device params and fall back to the exercise's own notes.
"""
from __future__ import annotations

import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from backend.engine.resolve_session import (  # noqa: E402
    resolve_session,
    _is_device_modality_exercise,
    _strip_device_prescription,
    _DEVICE_PRESCRIPTION_FIELDS,
)

EXERCISES_PATH = os.path.join(REPO_ROOT, "backend/catalog/exercises/v1/exercises.json")

NO_HANGBOARD_GYM = ["pullup_bar", "dumbbell", "bench"]
HANGBOARD_GYM = ["hangboard", "pullup_bar"]

DEVICE_NOTE_MARKER = "20mm half crimp"


def _resolve_strength_long(gym_equipment, gym_id="g1"):
    state = {
        "context": {"location": "gym", "gym_id": gym_id},
        "equipment": {"gyms": [{"gym_id": gym_id, "priority": 1, "equipment": gym_equipment}], "home": []},
        "bodyweight_kg": 70,
        "defaults": {"location": "gym"},
    }
    return resolve_session(
        repo_root=REPO_ROOT,
        session_path="backend/catalog/sessions/v1/strength_long.json",
        templates_dir="backend/catalog/templates/v1",
        exercises_path=EXERCISES_PATH,
        out_path="", user_state_override=state, write_output=False, user_id=None,
    )


def _main_prescription(resolved):
    main = next((b for b in resolved["resolved_session"]["blocks"] if b["block_id"] == "main"), None)
    assert main is not None
    se = (main.get("selected_exercises") or [{}])[0]
    return se.get("exercise_id"), (se.get("prescription") or {})


def _has_device_bleed(presc):
    notes = " ".join(presc.get("notes") or [])
    field_bleed = any(k in presc for k in _DEVICE_PRESCRIPTION_FIELDS)
    return DEVICE_NOTE_MARKER in notes or field_bleed


class TestB263Helpers(unittest.TestCase):
    def test_is_device_modality_by_domain(self):
        self.assertTrue(_is_device_modality_exercise({"domain": ["finger_max_strength"]}))
        self.assertTrue(_is_device_modality_exercise({"domain": ["finger_strength"]}))
        self.assertFalse(_is_device_modality_exercise({"domain": ["strength_general"]}))

    def test_is_device_modality_by_equipment(self):
        self.assertTrue(_is_device_modality_exercise({"equipment_required": ["hangboard"]}))
        self.assertTrue(_is_device_modality_exercise({"equipment_required_any": ["loading_pin"]}))
        self.assertFalse(_is_device_modality_exercise({"equipment_required": ["pullup_bar"]}))

    def test_strip_no_op_for_device_exercise(self):
        block = {"hang_seconds_range": [7], "notes": ["Prefer 20mm half crimp"]}
        merged = dict(block)
        _strip_device_prescription(merged, block, {"notes": ["x"]}, {"domain": ["finger_max_strength"]})
        self.assertIn("hang_seconds_range", merged)  # device exercise → untouched

    def test_strip_no_op_for_generic_block(self):
        block = {"sets_range": [3, 5], "rest_seconds_range": [120, 180]}
        merged = dict(block)
        _strip_device_prescription(merged, block, {}, {"domain": ["strength_general"]})
        self.assertEqual(merged, block)  # no device fields → untouched

    def test_strip_removes_device_params_on_mismatch(self):
        block = {"hang_seconds_range": [7], "intensity_pct_of_total_load_range": [0.9],
                 "sets_range": [4], "notes": ["Prefer 20mm half crimp baseline"]}
        merged = dict(block)
        _strip_device_prescription(merged, block, {"notes": ["Do a pull-up"]},
                                   {"domain": ["strength_general"], "equipment_required": ["pullup_bar"]})
        self.assertNotIn("hang_seconds_range", merged)
        self.assertNotIn("intensity_pct_of_total_load_range", merged)
        self.assertIn("sets_range", merged)              # generic field kept
        self.assertEqual(merged["notes"], ["Do a pull-up"])  # exercise notes restored

    def test_strip_drops_notes_when_exercise_has_none(self):
        block = {"hang_seconds_range": [7], "notes": ["Prefer 20mm half crimp"]}
        merged = dict(block)
        _strip_device_prescription(merged, block, {}, {"domain": ["strength_general"]})
        self.assertNotIn("notes", merged)

    def test_d250_dip_substitute_no_finger_bleed(self):
        """D250: a Dip (push, strength_general, bodyweight_only) substituted into the
        finger_max_strength main block must not inherit the hangboard notes
        ("Prefer 20mm half crimp… Rest fully 2.5–4 min") nor the device fields.
        Reproduces the exact production symptom faithfully (real finger block notes
        + real Dip defaults)."""
        finger_block = {
            "sets_range": [5, 8],
            "hang_seconds_range": [5, 10],
            "rest_seconds_range": [150, 240],
            "intensity_pct_of_total_load_range": [0.85, 0.95],
            "notes": [
                "Target: high quality efforts, no grinding. Stop if form breaks.",
                "Prefer 20mm half crimp baseline when available; override only if needed.",
                "Rest fully (2.5–4 min).",
            ],
        }
        dip_defaults = {"sets": 3, "reps": 4, "rest_between_sets_seconds": 120,
                        "notes": "Can use parallel bars or rings."}
        merged = {**dip_defaults, **finger_block}  # block notes win the naive merge
        dip_ex = {"id": "dip", "domain": ["strength_general"], "pattern": "push",
                  "equipment_required": [], "load_model": "bodyweight_only"}
        _strip_device_prescription(merged, finger_block, dip_defaults, dip_ex)
        notes = " ".join(merged.get("notes") or []) if isinstance(merged.get("notes"), list) else (merged.get("notes") or "")
        self.assertNotIn("20mm half crimp", notes)
        self.assertNotIn("Rest fully", notes)
        self.assertEqual(merged["notes"], "Can use parallel bars or rings.")
        for k in _DEVICE_PRESCRIPTION_FIELDS:
            self.assertNotIn(k, merged)


class TestB263Integration(unittest.TestCase):
    def test_substitute_has_no_device_bleed(self):
        resolved = _resolve_strength_long(NO_HANGBOARD_GYM)
        ex_id, presc = _main_prescription(resolved)
        self.assertFalse(_is_device_modality_exercise({"domain": ["strength_general"]}))  # sanity
        self.assertFalse(_has_device_bleed(presc),
                         f"device prescription bled onto substitute {ex_id}: {presc.get('notes')}")

    def test_correct_device_exercise_keeps_guidance(self):
        resolved = _resolve_strength_long(HANGBOARD_GYM, gym_id="gh")
        ex_id, presc = _main_prescription(resolved)
        # Correct hangboard exercise → "20mm half crimp" guidance + device fields stay.
        notes = " ".join(presc.get("notes") or [])
        self.assertIn(DEVICE_NOTE_MARKER, notes, f"guidance wrongly stripped from {ex_id}")
        self.assertTrue(any(k in presc for k in _DEVICE_PRESCRIPTION_FIELDS))

    def test_deterministic(self):
        a = _main_prescription(_resolve_strength_long(NO_HANGBOARD_GYM))
        b = _main_prescription(_resolve_strength_long(NO_HANGBOARD_GYM))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
