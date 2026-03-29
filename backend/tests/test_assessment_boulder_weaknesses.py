"""Tests for A-B3: boulder-specific weakness values in assessment_v1."""

import unittest

from backend.engine.assessment_v1 import compute_assessment_profile


def _make_assessment(primary_weakness="", secondary_weakness=""):
    return {
        "body": {"weight_kg": 70.0, "height_cm": 175},
        "experience": {"climbing_years": 3, "structured_training_years": 1},
        "grades": {
            "lead_max_rp": "7a",
            "lead_max_os": "6b+",
            "boulder_max_rp": "6B+",
        },
        "tests": {},
        "self_eval": {
            "primary_weakness": primary_weakness,
            "secondary_weakness": secondary_weakness,
        },
    }


GOAL = {
    "goal_type": "lead_grade",
    "discipline": "lead",
    "target_grade": "7c",
    "current_grade": "7a",
}


class TestBoulderWeaknessAccepted(unittest.TestCase):
    """New boulder weakness values must be accepted without error."""

    def test_poor_body_tension_accepted(self):
        a = _make_assessment(primary_weakness="poor_body_tension")
        compute_assessment_profile(a, GOAL)

    def test_poor_dynamic_movement_accepted(self):
        a = _make_assessment(primary_weakness="poor_dynamic_movement")
        compute_assessment_profile(a, GOAL)

    def test_weak_on_slopers_accepted(self):
        a = _make_assessment(primary_weakness="weak_on_slopers")
        compute_assessment_profile(a, GOAL)

    def test_poor_problem_reading_accepted(self):
        a = _make_assessment(primary_weakness="poor_problem_reading")
        compute_assessment_profile(a, GOAL)


class TestBoulderWeaknessAxisMapping(unittest.TestCase):
    """Verify each boulder weakness affects the correct axis."""

    def _profile(self, primary="", secondary=""):
        a = _make_assessment(primary_weakness=primary, secondary_weakness=secondary)
        return compute_assessment_profile(a, GOAL)

    def _baseline(self):
        return self._profile("cant_hold_hard_moves", "")

    def test_poor_body_tension_lowers_technique(self):
        baseline = self._baseline()
        with_weakness = self._profile("poor_body_tension", "")
        self.assertLess(with_weakness["technique"], baseline["technique"])

    def test_poor_problem_reading_lowers_technique(self):
        baseline = self._baseline()
        with_weakness = self._profile("poor_problem_reading", "")
        self.assertLess(with_weakness["technique"], baseline["technique"])

    def test_weak_on_slopers_lowers_finger_strength(self):
        baseline = self._baseline()
        with_weakness = self._profile("weak_on_slopers", "")
        self.assertLess(with_weakness["finger_strength"], baseline["finger_strength"])

    def test_poor_dynamic_movement_lowers_pe(self):
        baseline = self._baseline()
        with_weakness = self._profile("poor_dynamic_movement", "")
        self.assertLess(with_weakness["power_endurance"], baseline["power_endurance"])

    def test_poor_dynamic_movement_lowers_technique(self):
        baseline = self._baseline()
        with_weakness = self._profile("poor_dynamic_movement", "")
        self.assertLess(with_weakness["technique"], baseline["technique"])

    def test_secondary_weakness_has_smaller_effect(self):
        primary = self._profile("poor_body_tension", "")
        secondary = self._profile("cant_hold_hard_moves", "poor_body_tension")
        # secondary penalty (-5) is less than primary (-10)
        self.assertGreater(secondary["technique"], primary["technique"])


class TestExistingWeaknessesUnchanged(unittest.TestCase):
    """Existing lead weaknesses must produce identical results (zero regression)."""

    def _profile(self, primary, secondary=""):
        a = _make_assessment(primary_weakness=primary, secondary_weakness=secondary)
        return compute_assessment_profile(a, GOAL)

    def test_pump_too_early_still_lowers_pe_and_endurance(self):
        neutral = self._profile("cant_hold_hard_moves")
        pump = self._profile("pump_too_early")
        self.assertLess(pump["power_endurance"], neutral["power_endurance"])
        self.assertLess(pump["endurance"], neutral["endurance"])

    def test_fingers_give_out_still_lowers_finger_strength(self):
        neutral = self._profile("cant_hold_hard_moves")
        fingers = self._profile("fingers_give_out")
        self.assertLess(fingers["finger_strength"], neutral["finger_strength"])

    def test_technique_errors_still_lowers_technique(self):
        neutral = self._profile("cant_hold_hard_moves")
        tech = self._profile("technique_errors")
        self.assertLess(tech["technique"], neutral["technique"])

    def test_cant_manage_rests_still_lowers_endurance(self):
        neutral = self._profile("cant_hold_hard_moves")
        rests = self._profile("cant_manage_rests")
        self.assertLess(rests["endurance"], neutral["endurance"])


class TestUnknownWeaknessIgnored(unittest.TestCase):
    """Unknown weakness values should be silently ignored (no crash)."""

    def test_unknown_primary_no_error(self):
        a = _make_assessment(primary_weakness="totally_unknown_value")
        profile = compute_assessment_profile(a, GOAL)
        for v in profile.values():
            self.assertGreaterEqual(v, 0)
            self.assertLessEqual(v, 100)

    def test_empty_weakness_no_error(self):
        a = _make_assessment(primary_weakness="", secondary_weakness="")
        profile = compute_assessment_profile(a, GOAL)
        for v in profile.values():
            self.assertGreaterEqual(v, 0)
            self.assertLessEqual(v, 100)


if __name__ == "__main__":
    unittest.main()
