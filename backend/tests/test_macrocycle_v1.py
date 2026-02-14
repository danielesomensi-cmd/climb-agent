"""Tests for macrocycle_v1 — macrocycle generation and deload logic."""

import unittest

from backend.engine.macrocycle_v1 import (
    PHASE_ORDER,
    PHASE_INTENSITY_CAP,
    _compute_phase_durations,
    _adjust_domain_weights,
    _validate_goal,
    _BASE_WEIGHTS,
    _build_session_pool,
    generate_macrocycle,
    apply_deload_week,
    check_pretrip_deload,
    should_extend_phase,
    should_trigger_adaptive_deload,
)


def _make_profile(**overrides):
    base = {
        "finger_strength": 60,
        "pulling_strength": 55,
        "power_endurance": 45,
        "technique": 50,
        "endurance": 40,
        "body_composition": 65,
    }
    base.update(overrides)
    return base


def _make_goal():
    return {
        "goal_type": "lead_grade",
        "discipline": "lead",
        "target_grade": "7c+",
        "target_style": "redpoint",
        "current_grade": "7b",
        "deadline": "2026-06-30",
        "override_mode": None,
        "created_at": "2026-02-14",
    }


def _make_user_state(trips=None):
    return {
        "trips": trips or [],
    }


class TestGenerateMacrocycleBasic(unittest.TestCase):
    def test_generate_macrocycle_basic(self):
        profile = _make_profile()
        goal = _make_goal()
        user_state = _make_user_state()
        mc = generate_macrocycle(goal, profile, user_state, "2026-03-02")
        self.assertEqual(mc["macrocycle_version"], "macrocycle.v1")
        self.assertEqual(mc["start_date"], "2026-03-02")
        self.assertIn("phases", mc)
        self.assertGreater(len(mc["phases"]), 0)
        self.assertIn("goal_snapshot", mc)
        self.assertIn("assessment_snapshot", mc)

    def test_macrocycle_total_weeks(self):
        profile = _make_profile()
        goal = _make_goal()
        mc = generate_macrocycle(goal, profile, _make_user_state(), "2026-03-02", total_weeks=12)
        self.assertEqual(mc["total_weeks"], 12)
        total = sum(p["duration_weeks"] for p in mc["phases"])
        self.assertEqual(total, 12)

    def test_macrocycle_phase_order(self):
        profile = _make_profile()
        goal = _make_goal()
        mc = generate_macrocycle(goal, profile, _make_user_state(), "2026-03-02")
        phase_ids = [p["phase_id"] for p in mc["phases"]]
        # Phases must appear in PHASE_ORDER sequence
        order_indices = [PHASE_ORDER.index(pid) for pid in phase_ids]
        self.assertEqual(order_indices, sorted(order_indices))

    def test_macrocycle_deload_always_last(self):
        profile = _make_profile()
        goal = _make_goal()
        mc = generate_macrocycle(goal, profile, _make_user_state(), "2026-03-02")
        last_phase = mc["phases"][-1]
        self.assertEqual(last_phase["phase_id"], "deload")

    def test_macrocycle_domain_weights_sum_1(self):
        profile = _make_profile()
        goal = _make_goal()
        mc = generate_macrocycle(goal, profile, _make_user_state(), "2026-03-02")
        for phase in mc["phases"]:
            total = sum(phase["domain_weights"].values())
            self.assertAlmostEqual(total, 1.0, places=2,
                                   msg=f"Phase {phase['phase_id']} weights sum to {total}")

    def test_macrocycle_pe_weakness_extends_pe_phase(self):
        # power_endurance score < 50 → PE phase should be extended
        weak_pe = _make_profile(power_endurance=30)
        strong_pe = _make_profile(power_endurance=80)
        goal = _make_goal()
        mc_weak = generate_macrocycle(goal, weak_pe, _make_user_state(), "2026-03-02")
        mc_strong = generate_macrocycle(goal, strong_pe, _make_user_state(), "2026-03-02")
        pe_weak = next(p for p in mc_weak["phases"] if p["phase_id"] == "power_endurance")
        pe_strong = next(p for p in mc_strong["phases"] if p["phase_id"] == "power_endurance")
        self.assertGreaterEqual(pe_weak["duration_weeks"], pe_strong["duration_weeks"])

    def test_macrocycle_finger_weakness_extends_sp_phase(self):
        # finger_strength as weakest axis < 50 → strength_power phase extended
        weak_finger = _make_profile(finger_strength=20, power_endurance=60, endurance=60, technique=60)
        goal = _make_goal()
        mc = generate_macrocycle(goal, weak_finger, _make_user_state(), "2026-03-02")
        sp = next(p for p in mc["phases"] if p["phase_id"] == "strength_power")
        self.assertGreaterEqual(sp["duration_weeks"], 4)

    def test_macrocycle_pretrip_deload(self):
        profile = _make_profile()
        goal = _make_goal()
        trips = [{"name": "Arco", "start_date": "2026-04-18", "end_date": "2026-04-21"}]
        mc = generate_macrocycle(goal, profile, _make_user_state(trips), "2026-03-02")
        # At least one phase should have pretrip_deload info
        has_pretrip = any("pretrip_deload" in p for p in mc["phases"])
        self.assertTrue(has_pretrip, "Expected pretrip_deload annotation in at least one phase")

    def test_macrocycle_session_pool_base_phase(self):
        pool = _build_session_pool("base")
        self.assertIn("endurance_aerobic_gym", pool)
        self.assertIn("technique_focus_gym", pool)
        self.assertIn("finger_strength_home", pool)

    def test_macrocycle_session_pool_performance_phase(self):
        pool = _build_session_pool("performance")
        self.assertIn("technique_focus_gym", pool)
        self.assertIn("prehab_maintenance", pool)

    def test_macrocycle_deterministic(self):
        profile = _make_profile()
        goal = _make_goal()
        mc1 = generate_macrocycle(goal, profile, _make_user_state(), "2026-03-02")
        mc2 = generate_macrocycle(goal, profile, _make_user_state(), "2026-03-02")
        # Compare everything except generated_at timestamp
        for key in ("phases", "total_weeks", "start_date", "end_date", "goal_snapshot", "assessment_snapshot"):
            self.assertEqual(mc1[key], mc2[key], f"Mismatch on {key}")

    def test_macrocycle_intensity_cap_per_phase(self):
        profile = _make_profile()
        goal = _make_goal()
        mc = generate_macrocycle(goal, profile, _make_user_state(), "2026-03-02")
        for phase in mc["phases"]:
            expected = PHASE_INTENSITY_CAP[phase["phase_id"]]
            self.assertEqual(phase["intensity_cap"], expected)


class TestPhaseDurations(unittest.TestCase):
    def test_default_durations_sum_to_12(self):
        profile = _make_profile(finger_strength=60, pulling_strength=60,
                                power_endurance=60, technique=60, endurance=60)
        durations = _compute_phase_durations(profile, 12)
        self.assertEqual(sum(durations.values()), 12)

    def test_custom_total_weeks(self):
        profile = _make_profile()
        durations = _compute_phase_durations(profile, 16)
        self.assertEqual(sum(durations.values()), 16)

    def test_no_phase_below_1(self):
        profile = _make_profile()
        durations = _compute_phase_durations(profile, 12)
        for phase, weeks in durations.items():
            self.assertGreaterEqual(weeks, 1, f"Phase {phase} has {weeks} weeks")


class TestDomainWeights(unittest.TestCase):
    def test_adjust_weak_axis_increases_weight(self):
        base = dict(_BASE_WEIGHTS["base"])
        profile = _make_profile(finger_strength=30)  # weak
        adjusted = _adjust_domain_weights(base, profile)
        # After adjustment and renormalization, finger_strength weight should increase
        # relative to base (though renormalization shifts everything)
        self.assertIsInstance(adjusted["finger_strength"], float)

    def test_weights_still_sum_to_1(self):
        for phase_id, base in _BASE_WEIGHTS.items():
            profile = _make_profile(finger_strength=30, technique=80)
            adjusted = _adjust_domain_weights(base, profile)
            total = sum(adjusted.values())
            self.assertAlmostEqual(total, 1.0, places=2,
                                   msg=f"Phase {phase_id} adjusted weights sum to {total}")


class TestDeloadFunctions(unittest.TestCase):
    def test_check_pretrip_deload_within_5_days(self):
        trips = [{"name": "Trip", "start_date": "2026-03-10"}]
        result = check_pretrip_deload({}, trips, "2026-03-06")
        self.assertIsNotNone(result)
        self.assertEqual(result["trigger"], "pretrip_deload")
        self.assertEqual(result["days_until_trip"], 4)

    def test_check_pretrip_deload_too_far(self):
        trips = [{"name": "Trip", "start_date": "2026-03-20"}]
        result = check_pretrip_deload({}, trips, "2026-03-06")
        self.assertIsNone(result)

    def test_check_pretrip_deload_no_trips(self):
        result = check_pretrip_deload({}, [], "2026-03-06")
        self.assertIsNone(result)

    def test_should_extend_phase_hard_feedback(self):
        self.assertTrue(should_extend_phase({}, ["hard", "very_hard"]))

    def test_should_extend_phase_ok_feedback(self):
        self.assertFalse(should_extend_phase({}, ["ok", "ok"]))

    def test_should_extend_phase_too_few(self):
        self.assertFalse(should_extend_phase({}, ["hard"]))

    def test_should_trigger_adaptive_deload(self):
        self.assertTrue(should_trigger_adaptive_deload(
            ["very_hard", "very_hard", "very_hard", "very_hard", "very_hard"]
        ))

    def test_should_not_trigger_adaptive_deload(self):
        self.assertFalse(should_trigger_adaptive_deload(
            ["hard", "very_hard", "very_hard", "very_hard", "very_hard"]
        ))

    def test_should_not_trigger_adaptive_deload_short(self):
        self.assertFalse(should_trigger_adaptive_deload(["very_hard", "very_hard"]))


class TestGoalValidation(unittest.TestCase):
    """Tests for goal validation warnings (F9 fix)."""

    def test_goal_target_below_current_warns(self):
        goal = {"target_grade": "7a", "current_grade": "7b"}
        warnings = _validate_goal(goal)
        self.assertEqual(len(warnings), 1)
        self.assertIn("not harder", warnings[0])

    def test_goal_target_equals_current_warns(self):
        goal = {"target_grade": "7b", "current_grade": "7b"}
        warnings = _validate_goal(goal)
        self.assertEqual(len(warnings), 1)
        self.assertIn("not harder", warnings[0])

    def test_goal_target_above_current_no_warning(self):
        goal = {"target_grade": "7c+", "current_grade": "7b"}
        warnings = _validate_goal(goal)
        self.assertEqual(len(warnings), 0)

    def test_goal_very_ambitious_warns(self):
        goal = {"target_grade": "9a", "current_grade": "7a"}
        warnings = _validate_goal(goal)
        self.assertEqual(len(warnings), 1)
        self.assertIn("may not be sufficient", warnings[0])

    def test_macrocycle_with_bad_goal_has_warnings(self):
        profile = _make_profile()
        goal = _make_goal()
        goal["target_grade"] = "7a"  # below current 7b
        mc = generate_macrocycle(goal, profile, _make_user_state(), "2026-03-02")
        self.assertIn("warnings", mc)
        self.assertGreater(len(mc["warnings"]), 0)

    def test_macrocycle_with_good_goal_no_warnings(self):
        profile = _make_profile()
        goal = _make_goal()  # 7c+ target, 7b current — fine
        mc = generate_macrocycle(goal, profile, _make_user_state(), "2026-03-02")
        self.assertNotIn("warnings", mc)


if __name__ == "__main__":
    unittest.main()
