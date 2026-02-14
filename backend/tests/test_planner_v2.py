"""Tests for planner_v2 — phase-aware weekly planner."""

import unittest
from datetime import datetime

from backend.engine.planner_v2 import generate_phase_week
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _build_session_pool, _adjust_domain_weights


def _base_availability():
    return {
        "mon": {"evening": {"available": True, "locations": ["gym", "home"]}},
        "tue": {"evening": {"available": True, "locations": ["gym", "home"]}},
        "wed": {"evening": {"available": True, "locations": ["gym", "home"]}},
        "thu": {"morning": {"available": True, "locations": ["home"]}},
        "fri": {"evening": {"available": True, "locations": ["gym", "home"]}},
        "sat": {"morning": {"available": True, "locations": ["gym", "home"]}},
        "sun": {"available": False},
    }


def _make_kwargs(phase_id="base", **overrides):
    profile = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
               "technique": 50, "endurance": 40, "body_composition": 65}
    base_weights = _BASE_WEIGHTS[phase_id]
    domain_weights = _adjust_domain_weights(base_weights, profile)
    session_pool = _build_session_pool(phase_id)
    defaults = dict(
        phase_id=phase_id,
        domain_weights=domain_weights,
        session_pool=session_pool,
        start_date="2026-03-02",
        availability=_base_availability(),
        allowed_locations=["home", "gym"],
        hard_cap_per_week=3,
        planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
        default_gym_id="blocx",
        gyms=[{"gym_id": "blocx", "equipment": ["spraywall", "board_kilter", "hangboard"]}],
    )
    defaults.update(overrides)
    return defaults


class TestPlannerV2Basic(unittest.TestCase):
    def test_generate_base_phase_week(self):
        plan = generate_phase_week(**_make_kwargs("base"))
        self.assertEqual(plan["plan_version"], "planner.v2")
        self.assertIn("weeks", plan)
        self.assertEqual(len(plan["weeks"]), 1)
        week = plan["weeks"][0]
        self.assertEqual(week["phase"], "base")
        self.assertEqual(len(week["days"]), 7)

    def test_generate_strength_power_week(self):
        plan = generate_phase_week(**_make_kwargs("strength_power"))
        week = plan["weeks"][0]
        self.assertEqual(week["phase"], "strength_power")
        all_sessions = [s for d in week["days"] for s in d["sessions"]]
        self.assertGreater(len(all_sessions), 0)

    def test_phase_id_in_session_entries(self):
        plan = generate_phase_week(**_make_kwargs("base"))
        for day in plan["weeks"][0]["days"]:
            for s in day["sessions"]:
                self.assertEqual(s["phase_id"], "base")


class TestPlannerV2DomainWeights(unittest.TestCase):
    def test_domain_weights_in_snapshot(self):
        plan = generate_phase_week(**_make_kwargs("base"))
        snapshot = plan["profile_snapshot"]
        self.assertIn("domain_weights", snapshot)
        total = sum(snapshot["domain_weights"].values())
        self.assertAlmostEqual(total, 1.0, places=2)


class TestPlannerV2Constraints(unittest.TestCase):
    def test_hard_day_cap_respected(self):
        plan = generate_phase_week(**_make_kwargs("strength_power", hard_cap_per_week=2))
        days = plan["weeks"][0]["days"]
        hard_count = sum(1 for d in days for s in d["sessions"] if s["tags"]["hard"])
        self.assertLessEqual(hard_count, 2)

    def test_no_consecutive_finger_days(self):
        plan = generate_phase_week(**_make_kwargs("strength_power"))
        days = plan["weeks"][0]["days"]
        finger_dates = []
        for d in days:
            if any(s["tags"]["finger"] for s in d["sessions"]):
                finger_dates.append(datetime.strptime(d["date"], "%Y-%m-%d").date())
        for prev, cur in zip(finger_dates, finger_dates[1:]):
            self.assertGreater((cur - prev).days, 1,
                               f"Consecutive finger days: {prev} and {cur}")

    def test_no_consecutive_max_intensity_days(self):
        plan = generate_phase_week(**_make_kwargs("strength_power"))
        days = plan["weeks"][0]["days"]
        max_dates = []
        for d in days:
            if any(s.get("intensity") == "max" for s in d["sessions"]):
                max_dates.append(datetime.strptime(d["date"], "%Y-%m-%d").date())
        for prev, cur in zip(max_dates, max_dates[1:]):
            self.assertGreater((cur - prev).days, 1,
                               f"Consecutive max-intensity days: {prev} and {cur}")


class TestPlannerV2Deload(unittest.TestCase):
    def test_deload_week_no_hard_sessions(self):
        plan = generate_phase_week(**_make_kwargs("deload"))
        days = plan["weeks"][0]["days"]
        for d in days:
            for s in d["sessions"]:
                self.assertFalse(s["tags"].get("hard", False),
                                 f"Hard session {s['session_id']} in deload week")

    def test_deload_factor(self):
        plan = generate_phase_week(**_make_kwargs("deload"))
        week = plan["weeks"][0]
        self.assertEqual(week["targets"]["deload_factor"], 0.5)

    def test_deload_phase_tag(self):
        plan = generate_phase_week(**_make_kwargs("deload"))
        self.assertEqual(plan["weeks"][0]["phase"], "deload")


class TestPlannerV2PhaseMapping(unittest.TestCase):
    def test_base_phase_uses_base_sessions(self):
        plan = generate_phase_week(**_make_kwargs("base"))
        base_pool = set(_build_session_pool("base"))
        for d in plan["weeks"][0]["days"]:
            for s in d["sessions"]:
                self.assertIn(s["session_id"], base_pool,
                              f"Session {s['session_id']} not in base pool")

    def test_performance_phase_uses_performance_sessions(self):
        plan = generate_phase_week(**_make_kwargs("performance"))
        perf_pool = set(_build_session_pool("performance"))
        for d in plan["weeks"][0]["days"]:
            for s in d["sessions"]:
                self.assertIn(s["session_id"], perf_pool,
                              f"Session {s['session_id']} not in performance pool")


class TestPlannerV2IntensityCap(unittest.TestCase):
    def test_base_phase_no_max_intensity(self):
        plan = generate_phase_week(**_make_kwargs("base"))
        for d in plan["weeks"][0]["days"]:
            for s in d["sessions"]:
                self.assertNotEqual(s.get("intensity"), "max",
                                    f"Max intensity session {s['session_id']} in base phase")

    def test_deload_only_low_intensity(self):
        plan = generate_phase_week(**_make_kwargs("deload"))
        for d in plan["weeks"][0]["days"]:
            for s in d["sessions"]:
                self.assertEqual(s.get("intensity"), "low",
                                 f"Non-low intensity {s['session_id']} in deload")


class TestPlannerV2Deterministic(unittest.TestCase):
    def test_deterministic_output(self):
        kwargs = _make_kwargs("base")
        plan_a = generate_phase_week(**kwargs)
        plan_b = generate_phase_week(**kwargs)
        for key in ("weeks", "start_date", "profile_snapshot"):
            self.assertEqual(plan_a[key], plan_b[key], f"Mismatch on {key}")


class TestPlannerV2LunchSlots(unittest.TestCase):
    def test_lunch_slot_used_when_available(self):
        avail = {
            "mon": {
                "morning": {"available": False},
                "lunch": {"available": True, "locations": ["home"]},
                "evening": {"available": False},
            },
            "tue": {"available": False},
            "wed": {"available": False},
            "thu": {"available": False},
            "fri": {"available": False},
            "sat": {"available": False},
            "sun": {"available": False},
        }
        plan = generate_phase_week(**_make_kwargs("base", availability=avail))
        mon = next(d for d in plan["weeks"][0]["days"] if d["weekday"] == "mon")
        if mon["sessions"]:
            self.assertEqual(mon["sessions"][0]["slot"], "lunch")


if __name__ == "__main__":
    unittest.main()
