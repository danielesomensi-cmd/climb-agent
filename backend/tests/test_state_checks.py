"""Tests for backend.engine.state_checks — dirty-state detection."""

import unittest

from backend.engine.state_checks import DIRTY_STATE_THRESHOLD, is_macrocycle_stale


def _profile(fs=50, ps=50, pe=50, tech=50, end=50, bc=50):
    return {
        "finger_strength": fs,
        "pulling_strength": ps,
        "power_endurance": pe,
        "technique": tech,
        "endurance": end,
        "body_composition": bc,
    }


def _state(profile=None, snapshot=None, *, has_macrocycle=True):
    s = {}
    if profile is not None:
        s["assessment"] = {"profile": profile}
    if has_macrocycle:
        mc = {"macrocycle_version": "macrocycle.v1"}
        if snapshot is not None:
            mc["assessment_snapshot"] = snapshot
        s["macrocycle"] = mc
    return s


class TestIsMacrocycleStale(unittest.TestCase):
    # --- True cases (stale) ---

    def test_stale_single_axis_at_threshold(self):
        """Exactly DIRTY_STATE_THRESHOLD delta → stale."""
        snap = _profile(fs=50)
        prof = _profile(fs=50 + DIRTY_STATE_THRESHOLD)
        self.assertTrue(is_macrocycle_stale(_state(prof, snap)))

    def test_stale_single_axis_above_threshold(self):
        snap = _profile(end=30)
        prof = _profile(end=50)
        self.assertTrue(is_macrocycle_stale(_state(prof, snap)))

    def test_stale_negative_delta(self):
        """Axis went *down* by >= threshold → still stale."""
        snap = _profile(ps=60)
        prof = _profile(ps=60 - DIRTY_STATE_THRESHOLD)
        self.assertTrue(is_macrocycle_stale(_state(prof, snap)))

    def test_stale_multiple_axes(self):
        snap = _profile(fs=40, tech=40)
        prof = _profile(fs=50, tech=50)
        self.assertTrue(is_macrocycle_stale(_state(prof, snap)))

    # --- False cases (not stale) ---

    def test_not_stale_identical(self):
        p = _profile()
        self.assertFalse(is_macrocycle_stale(_state(p, p)))

    def test_not_stale_small_delta(self):
        snap = _profile(fs=50)
        prof = _profile(fs=50 + DIRTY_STATE_THRESHOLD - 1)
        self.assertFalse(is_macrocycle_stale(_state(prof, snap)))

    def test_not_stale_all_axes_just_below(self):
        """Every axis differs by threshold-1 → still not stale."""
        d = DIRTY_STATE_THRESHOLD - 1
        snap = _profile(50, 50, 50, 50, 50, 50)
        prof = _profile(50 + d, 50 - d, 50 + d, 50 - d, 50 + d, 50 - d)
        self.assertFalse(is_macrocycle_stale(_state(prof, snap)))

    # --- Edge cases (missing data) ---

    def test_false_when_no_macrocycle(self):
        state = _state(_profile(), has_macrocycle=False)
        self.assertFalse(is_macrocycle_stale(state))

    def test_false_when_no_snapshot(self):
        state = _state(_profile(), snapshot=None)
        self.assertFalse(is_macrocycle_stale(state))

    def test_false_when_no_profile(self):
        state = _state(profile=None, snapshot=_profile())
        self.assertFalse(is_macrocycle_stale(state))

    def test_false_on_empty_state(self):
        self.assertFalse(is_macrocycle_stale({}))

    def test_threshold_constant_is_five(self):
        self.assertEqual(DIRTY_STATE_THRESHOLD, 5)


if __name__ == "__main__":
    unittest.main()
