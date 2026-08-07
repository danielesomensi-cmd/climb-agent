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

    def _profile(self, primary="", secondary="", repeater=None):
        a = _make_assessment(primary_weakness=primary, secondary_weakness=secondary)
        if repeater is not None:
            # A269: a value is not a measurement until `tests_source` says so.
            # Every real writer stamps both (onboarding, progression_v1, and the
            # m003 backfill), so the fixture has to as well.
            a["tests"]["repeater_7_3_max_sets_20mm"] = repeater
            a["tests_source"] = {"repeater_7_3_max_sets_20mm": "measured"}
        return compute_assessment_profile(a, GOAL)

    def _baseline(self, repeater=None):
        return self._profile("cant_hold_hard_moves", "", repeater=repeater)

    def test_poor_body_tension_lowers_technique(self):
        baseline = self._baseline()
        with_weakness = self._profile("poor_body_tension", "")
        self.assertLess(with_weakness["technique"], baseline["technique"])

    def test_poor_problem_reading_lowers_technique(self):
        baseline = self._baseline()
        with_weakness = self._profile("poor_problem_reading", "")
        self.assertLess(with_weakness["technique"], baseline["technique"])

    def test_weak_on_slopers_no_longer_moves_finger_strength(self):
        """A271 framing B inverted this.

        The finger penalty lived only in the grade-estimate branch, i.e. exactly
        when the axis is NOT measured — so it was a self-declaration steering a
        domain weight on the axis where the engine knows least. The mapping
        stays in `_AXIS_WEAKNESS_PENALTIES` (it still describes what the
        weakness means, and a future session-pool rule can use it), but nothing
        in the scoring consumes it for this axis any more.
        """
        baseline = self._baseline()
        with_weakness = self._profile("weak_on_slopers", "")
        self.assertEqual(with_weakness["finger_strength"], baseline["finger_strength"])

    def test_poor_dynamic_movement_lowers_pe_when_pe_is_measured(self):
        """A270: the weakness mapping is unchanged, but PE without a repeater is
        a flat neutral 50 that no self-declaration can move."""
        baseline = self._baseline(repeater=24)
        with_weakness = self._profile("poor_dynamic_movement", "", repeater=24)
        self.assertLess(with_weakness["power_endurance"], baseline["power_endurance"])
        # Unmeasured PE stays neutral for both.
        self.assertEqual(self._baseline()["power_endurance"], 50)
        self.assertEqual(self._profile("poor_dynamic_movement", "")["power_endurance"], 50)

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

    def _profile(self, primary, secondary="", repeater=None):
        a = _make_assessment(primary_weakness=primary, secondary_weakness=secondary)
        if repeater is not None:
            # A269: a value is not a measurement until `tests_source` says so.
            # Every real writer stamps both (onboarding, progression_v1, and the
            # m003 backfill), so the fixture has to as well.
            a["tests"]["repeater_7_3_max_sets_20mm"] = repeater
            a["tests_source"] = {"repeater_7_3_max_sets_20mm": "measured"}
        return compute_assessment_profile(a, GOAL)

    def test_pump_too_early_still_lowers_pe_and_endurance(self):
        """Endurance carries its own pump penalty, so it bites regardless. PE
        needs a repeater to have anything to subtract from (A270)."""
        # A271: both axes now need a measurement under them before a
        # self-declaration is allowed to move anything.
        self.assertEqual(
            self._profile("pump_too_early")["endurance"],
            self._profile("cant_hold_hard_moves")["endurance"],
        )
        self.assertLess(
            self._profile("pump_too_early", repeater=24)["endurance"],
            self._profile("cant_hold_hard_moves", repeater=24)["endurance"],
        )
        self.assertLess(
            self._profile("pump_too_early", repeater=24)["power_endurance"],
            self._profile("cant_hold_hard_moves", repeater=24)["power_endurance"],
        )

    def test_fingers_give_out_no_longer_moves_finger_strength(self):
        """A271 framing B — see the sloper test above for the reasoning."""
        neutral = self._profile("cant_hold_hard_moves")
        fingers = self._profile("fingers_give_out")
        self.assertEqual(fingers["finger_strength"], neutral["finger_strength"])

    def test_technique_errors_still_lowers_technique(self):
        neutral = self._profile("cant_hold_hard_moves")
        tech = self._profile("technique_errors")
        self.assertLess(tech["technique"], neutral["technique"])

    def test_cant_manage_rests_lowers_endurance_only_when_it_is_measured(self):
        """A271: the endurance penalty needs something measured under it.

        Unmeasured, it was the only thing moving the axis, and through the
        `< 50` cliff a single dropdown moved `volume_climbing` by 3.5 pp.
        """
        self.assertEqual(
            self._profile("cant_manage_rests")["endurance"],
            self._profile("cant_hold_hard_moves")["endurance"],
        )
        self.assertLess(
            self._profile("cant_manage_rests", repeater=24)["endurance"],
            self._profile("cant_hold_hard_moves", repeater=24)["endurance"],
        )


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
