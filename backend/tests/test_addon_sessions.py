"""Tests for B83 — add-on mini-sessions (upper body, legs, core)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.engine.resolve_session import resolve_session
from backend.engine.planner_v2 import _SESSION_META
from backend.engine.replanner_v1 import suggest_sessions

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SESSIONS_DIR = "backend/catalog/sessions/v1"
TEMPLATES_DIR = "backend/catalog/templates/v1"
EXERCISES_PATH = "backend/catalog/exercises/v1/exercises.json"

_ADDON_IDS = ("upper_body_weights", "legs_strength", "core_training")


def _make_us(equipment_home=None):
    return {
        "assessment": {
            "profile": {
                "finger_strength": 60, "pulling_strength": 60,
                "power_endurance": 60, "technique": 60,
                "endurance": 60, "body_composition": 60,
            }
        },
        "equipment": {
            "home": equipment_home or [],
            "gyms": [{"gym_id": "g", "name": "g", "equipment": [
                "gym_boulder", "gym_routes", "hangboard", "pullup_bar", "weight",
            ]}],
        },
        "baselines": {},
    }


def _resolve(session_id, us):
    return resolve_session(
        REPO_ROOT,
        os.path.join(SESSIONS_DIR, f"{session_id}.json"),
        TEMPLATES_DIR,
        EXERCISES_PATH,
        "/dev/null",
        user_state_override=us,
        write_output=False,
    )


class TestAddonSessionResolve(unittest.TestCase):

    def test_upper_body_weights_resolves(self):
        """upper_body_weights resolves with bodyweight only."""
        result = _resolve("upper_body_weights", _make_us())
        self.assertEqual(result["resolution_status"], "success")
        exs = result["resolved_session"]["exercise_instances"]
        self.assertGreaterEqual(len(exs), 2)

    def test_upper_body_weights_resolves_with_weight(self):
        """upper_body_weights resolves with weight equipment available."""
        us = _make_us(equipment_home=["weight", "pullup_bar"])
        result = _resolve("upper_body_weights", us)
        self.assertEqual(result["resolution_status"], "success")
        exs = result["resolved_session"]["exercise_instances"]
        self.assertGreaterEqual(len(exs), 2)

    def test_legs_strength_resolves(self):
        """legs_strength resolves correctly."""
        result = _resolve("legs_strength", _make_us())
        self.assertEqual(result["resolution_status"], "success")
        exs = result["resolved_session"]["exercise_instances"]
        self.assertGreaterEqual(len(exs), 2)

    def test_core_training_resolves(self):
        """core_training resolves correctly."""
        result = _resolve("core_training", _make_us())
        self.assertEqual(result["resolution_status"], "success")
        exs = result["resolved_session"]["exercise_instances"]
        self.assertGreaterEqual(len(exs), 2)

    def test_addon_sessions_in_session_meta(self):
        """All three add-on sessions registered in _SESSION_META with climbing=False."""
        for sid in _ADDON_IDS:
            self.assertIn(sid, _SESSION_META, f"{sid} missing from _SESSION_META")
            self.assertFalse(_SESSION_META[sid]["climbing"],
                             f"{sid} should have climbing=False")

    def test_addon_sessions_not_finger(self):
        """None of the add-on sessions has finger=True."""
        for sid in _ADDON_IDS:
            self.assertFalse(_SESSION_META[sid]["finger"],
                             f"{sid} should have finger=False")


class TestAddonSuggestSessions(unittest.TestCase):

    def _make_plan(self, phase_id="base"):
        return {
            "profile_snapshot": {"phase_id": phase_id},
            "weeks": [{"days": [
                {"date": "2026-03-09", "sessions": []},
                {"date": "2026-03-10", "sessions": []},
            ]}],
        }

    def test_addon_sessions_appear_in_suggestions(self):
        """Add-on sessions should appear in suggest_sessions results."""
        plan = self._make_plan()
        suggestions = suggest_sessions(plan, "2026-03-09", "home", max_suggestions=20)
        suggested_ids = {s["session_id"] for s in suggestions}
        for sid in _ADDON_IDS:
            self.assertIn(sid, suggested_ids,
                          f"{sid} should be suggestible regardless of phase")


if __name__ == "__main__":
    unittest.main()
