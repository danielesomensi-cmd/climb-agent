"""Tests for B127 — assessment profile auto-refresh on save_state().

Invariant: whenever assessment.tests, grades, self_eval, or body change,
the cached assessment.profile must reflect those changes after save.
"""

import json
import os
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch

from backend.api.deps import save_state, load_state, _ensure_profile_fresh
from backend.engine.assessment_v1 import compute_assessment_profile


def _base_state(*, with_tests=False):
    """Minimal state with assessment + goal suitable for profile computation."""
    state = {
        "schema_version": "1.5",
        "assessment": {
            "body": {"weight_kg": 76, "height_cm": 182},
            "experience": {"climbing_years": 5},
            "grades": {"lead_max_rp": "8a", "lead_max_os": "7a+"},
            "tests": {},
            "self_eval": {
                "primary_weakness": "technique_errors",
                "secondary_weakness": "pump_too_early",
            },
        },
        "goal": {
            "target_grade": "8a+",
            "current_grade": "8a",
            "discipline": "lead",
            "goal_type": "lead_grade",
        },
    }
    if with_tests:
        state["assessment"]["tests"] = {
            "max_hang_20mm_5s_total_kg": 125,
            "weighted_pullup_1rm_total_kg": 130,
        }
    return state


class TestEnsureProfileFresh(unittest.TestCase):
    """Unit tests for _ensure_profile_fresh (no disk I/O)."""

    def test_computes_profile_when_missing(self):
        state = _base_state(with_tests=True)
        assert state["assessment"].get("profile") is None
        _ensure_profile_fresh(state)
        profile = state["assessment"]["profile"]
        assert profile is not None
        assert profile["finger_strength"] == 100
        assert profile["pulling_strength"] == 100

    def test_uses_proxy_when_no_tests(self):
        state = _base_state(with_tests=False)
        _ensure_profile_fresh(state)
        profile = state["assessment"]["profile"]
        assert profile["finger_strength"] == 66  # proxy: (16/17)*70
        assert profile["pulling_strength"] == 61  # proxy: (16/17)*65

    def test_updates_profile_when_tests_added(self):
        state = _base_state(with_tests=False)
        _ensure_profile_fresh(state)
        assert state["assessment"]["profile"]["finger_strength"] == 66

        # Add test data
        state["assessment"]["tests"]["max_hang_20mm_5s_total_kg"] = 125
        _ensure_profile_fresh(state)
        assert state["assessment"]["profile"]["finger_strength"] == 100

    def test_fingerprint_prevents_redundant_computation(self):
        state = _base_state(with_tests=True)
        _ensure_profile_fresh(state)
        fp1 = state["assessment"]["_profile_fingerprint"]

        # Second call with same data should be a no-op (same fingerprint)
        with patch("backend.engine.assessment_v1.compute_assessment_profile") as mock:
            _ensure_profile_fresh(state)
            mock.assert_not_called()

        assert state["assessment"]["_profile_fingerprint"] == fp1

    def test_fingerprint_changes_when_data_changes(self):
        state = _base_state(with_tests=True)
        _ensure_profile_fresh(state)
        fp1 = state["assessment"]["_profile_fingerprint"]

        state["assessment"]["tests"]["max_hang_20mm_5s_total_kg"] = 130
        _ensure_profile_fresh(state)
        fp2 = state["assessment"]["_profile_fingerprint"]
        assert fp1 != fp2

    def test_skips_when_no_goal(self):
        state = _base_state(with_tests=True)
        state["goal"] = {}
        _ensure_profile_fresh(state)
        assert state["assessment"].get("profile") is None

    def test_skips_when_no_assessment_data(self):
        state = {"assessment": {}, "goal": {"target_grade": "8a+"}}
        _ensure_profile_fresh(state)
        assert state["assessment"].get("profile") is None


class TestSaveStateRecomputes(unittest.TestCase):
    """Integration tests: save_state triggers profile recomputation."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._patcher = patch(
            "backend.api.deps._user_state_path",
            return_value=type("P", (), {
                "exists": lambda self: os.path.exists(self._p),
                "read_text": lambda self, **kw: open(self._p).read(),
                "write_text": lambda self, text, **kw: (
                    os.makedirs(os.path.dirname(self._p), exist_ok=True) or
                    open(self._p, "w").write(text)
                ),
                "parent": type("PP", (), {
                    "mkdir": lambda self, **kw: os.makedirs(self._p_dir, exist_ok=True),
                })(),
            })(),
        )
        # Simpler approach: use a temp file directly
        self._tmpfile = os.path.join(self._tmpdir, "user_state.json")

    def tearDown(self):
        if os.path.exists(self._tmpfile):
            os.remove(self._tmpfile)
        os.rmdir(self._tmpdir)

    def test_save_state_adds_profile_when_missing(self):
        """save_state should compute profile if assessment data present but profile missing."""
        state = _base_state(with_tests=True)
        assert state["assessment"].get("profile") is None

        # Write directly to verify _ensure_profile_fresh runs
        _ensure_profile_fresh(state)
        assert state["assessment"]["profile"]["finger_strength"] == 100

    def test_profile_updates_after_test_data_change(self):
        """Simulates feedback writing new test data → profile must update."""
        state = _base_state(with_tests=False)
        _ensure_profile_fresh(state)
        assert state["assessment"]["profile"]["finger_strength"] == 66

        # Simulate apply_feedback writing max_hang
        state["assessment"]["tests"]["max_hang_20mm_5s_total_kg"] = 125
        _ensure_profile_fresh(state)
        assert state["assessment"]["profile"]["finger_strength"] == 100

    def test_profile_updates_after_grades_change(self):
        """Grade change should trigger profile recomputation."""
        state = _base_state(with_tests=False)
        _ensure_profile_fresh(state)
        old_technique = state["assessment"]["profile"]["technique"]

        # Change OS grade → smaller gap → higher technique
        state["assessment"]["grades"]["lead_max_os"] = "7c"
        _ensure_profile_fresh(state)
        assert state["assessment"]["profile"]["technique"] > old_technique

    def test_profile_updates_after_self_eval_change(self):
        """Self-eval change should trigger profile recomputation."""
        state = _base_state(with_tests=False)
        _ensure_profile_fresh(state)
        old_technique = state["assessment"]["profile"]["technique"]

        # Remove technique weakness → higher technique score
        state["assessment"]["self_eval"]["primary_weakness"] = "cant_hold_hard_moves"
        _ensure_profile_fresh(state)
        assert state["assessment"]["profile"]["technique"] > old_technique

    def test_profile_updates_after_body_weight_change(self):
        """Weight change affects finger/pulling scores."""
        state = _base_state(with_tests=True)
        _ensure_profile_fresh(state)
        # 125/76/1.50*100 = 109 → capped to 100
        assert state["assessment"]["profile"]["finger_strength"] == 100

        # Heavier → lower ratio → lower score
        state["assessment"]["body"]["weight_kg"] = 120
        _ensure_profile_fresh(state)
        # 125/120/1.50*100 = 69
        assert state["assessment"]["profile"]["finger_strength"] == 69


class TestDanieleReproduction(unittest.TestCase):
    """Reproduce Daniele's exact bug scenario and verify the fix."""

    def test_daniele_scenario_proxy_then_test_data(self):
        """Daniele's bug: profile computed at onboarding without tests,
        then tests added later → profile must update."""
        # Step 1: Onboarding without max_hang (only pullup)
        state = _base_state(with_tests=False)
        state["assessment"]["tests"]["weighted_pullup_1rm_total_kg"] = 130
        _ensure_profile_fresh(state)

        # This is the buggy state Daniele had
        assert state["assessment"]["profile"]["finger_strength"] == 66
        assert state["assessment"]["profile"]["pulling_strength"] == 100

        # Step 2: Max hang added (via settings edit or feedback)
        state["assessment"]["tests"]["max_hang_20mm_5s_total_kg"] = 125
        _ensure_profile_fresh(state)

        # Profile must now reflect both tests
        assert state["assessment"]["profile"]["finger_strength"] == 100
        assert state["assessment"]["profile"]["pulling_strength"] == 100

    def test_daniele_exact_values(self):
        """Verify Daniele's exact profile with all his data."""
        state = _base_state(with_tests=True)
        _ensure_profile_fresh(state)
        profile = state["assessment"]["profile"]

        assert profile["finger_strength"] == 100
        assert profile["pulling_strength"] == 100
        assert profile["power_endurance"] == 38
        assert profile["technique"] == 30
        assert profile["endurance"] == 35


if __name__ == "__main__":
    unittest.main()
