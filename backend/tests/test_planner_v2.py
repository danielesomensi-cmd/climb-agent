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
               "technique": 50, "endurance": 40}
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
        gyms=[{"gym_id": "blocx", "equipment": ["spraywall", "board_kilter", "hangboard", "gym_boulder", "gym_routes", "dumbbell", "pullup_bar"]}],
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


class TestPlannerV2AntiRepetition(unittest.TestCase):
    """Tests for anti-repetition constraint (max_per_week)."""

    def test_no_session_exceeds_max_per_week(self):
        """No session should appear more than its max_per_week limit."""
        plan = generate_phase_week(**_make_kwargs("base",
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 3}))
        from collections import Counter
        from backend.engine.planner_v2 import _SESSION_META
        counts = Counter(s["session_id"] for d in plan["weeks"][0]["days"] for s in d["sessions"])
        for sid, count in counts.items():
            max_pw = _SESSION_META.get(sid, {}).get("max_per_week", 1)
            self.assertLessEqual(count, max_pw,
                f"{sid} appears {count}x but max_per_week={max_pw}")

    def test_endurance_aerobic_allowed_twice(self):
        """endurance_aerobic_gym should appear up to 2x in base phase."""
        plan = generate_phase_week(**_make_kwargs("base",
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 3}))
        count = sum(1 for d in plan["weeks"][0]["days"] for s in d["sessions"]
                    if s["session_id"] == "endurance_aerobic_gym")
        self.assertLessEqual(count, 2, "endurance_aerobic_gym should not exceed 2x")
        self.assertGreaterEqual(count, 1, "endurance_aerobic_gym should appear at least 1x in base")

    def test_anti_repetition_across_phases(self):
        """Anti-repetition should work for all phases, not just base."""
        for phase_id in ("strength_power", "power_endurance", "performance"):
            plan = generate_phase_week(**_make_kwargs(phase_id,
                planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 3}))
            from collections import Counter
            from backend.engine.planner_v2 import _SESSION_META
            counts = Counter(s["session_id"] for d in plan["weeks"][0]["days"] for s in d["sessions"])
            for sid, count in counts.items():
                max_pw = _SESSION_META.get(sid, {}).get("max_per_week", 1)
                self.assertLessEqual(count, max_pw,
                    f"[{phase_id}] {sid} appears {count}x but max_per_week={max_pw}")


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


class TestPlannerV2ClimbingFirst(unittest.TestCase):
    """Tests for climbing-first session ordering (F11 fix)."""

    def test_no_evening_only_complementary(self):
        """No day should have only a complementary session in the evening slot
        while primary climbing sessions are still unplaced.
        Only checks days where non-evening slots are available (Bug 1 fix
        makes unmentioned slots unavailable when explicit slots exist)."""
        # Use availability with all slots available on every active day
        all_slots_avail = {
            "mon": {"morning": {"available": True, "locations": ["gym", "home"]},
                    "lunch": {"available": True, "locations": ["gym", "home"]},
                    "evening": {"available": True, "locations": ["gym", "home"]}},
            "tue": {"morning": {"available": True, "locations": ["gym", "home"]},
                    "lunch": {"available": True, "locations": ["gym", "home"]},
                    "evening": {"available": True, "locations": ["gym", "home"]}},
            "wed": {"morning": {"available": True, "locations": ["gym", "home"]},
                    "lunch": {"available": True, "locations": ["gym", "home"]},
                    "evening": {"available": True, "locations": ["gym", "home"]}},
            "thu": {"morning": {"available": True, "locations": ["home"]},
                    "lunch": {"available": True, "locations": ["home"]},
                    "evening": {"available": True, "locations": ["home"]}},
            "fri": {"morning": {"available": True, "locations": ["gym", "home"]},
                    "lunch": {"available": True, "locations": ["gym", "home"]},
                    "evening": {"available": True, "locations": ["gym", "home"]}},
            "sat": {"morning": {"available": True, "locations": ["gym", "home"]},
                    "lunch": {"available": True, "locations": ["gym", "home"]},
                    "evening": {"available": True, "locations": ["gym", "home"]}},
            "sun": {"available": False},
        }
        for phase_id in ("base", "strength_power", "power_endurance", "performance"):
            plan = generate_phase_week(**_make_kwargs(phase_id,
                availability=all_slots_avail,
                planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 3}))
            days = plan["weeks"][0]["days"]
            for d in days:
                if not d["sessions"]:
                    continue
                for s in d["sessions"]:
                    explains = s.get("explain", [])
                    # Complementary sessions should prefer lunch, not evening
                    if "pass2:complementary" in explains:
                        self.assertNotEqual(s["slot"], "evening",
                            f"{phase_id}: complementary {s['session_id']} placed in evening on {d['weekday']}")


class TestPlannerV2FingerMaintenance(unittest.TestCase):
    """Tests for finger_maintenance_home in Base phase (F3 fix)."""

    def test_base_phase_has_finger_sessions(self):
        plan = generate_phase_week(**_make_kwargs("base",
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 3}))
        days = plan["weeks"][0]["days"]
        finger_sessions = [s for d in days for s in d["sessions"] if s["tags"]["finger"]]
        self.assertGreater(len(finger_sessions), 0,
                           "Base phase has no finger sessions")

    def test_finger_maintenance_is_medium_intensity(self):
        plan = generate_phase_week(**_make_kwargs("base",
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 3}))
        days = plan["weeks"][0]["days"]
        finger_sessions = [s for d in days for s in d["sessions"]
                          if s["tags"]["finger"] and s["session_id"] == "finger_maintenance_home"]
        self.assertGreater(len(finger_sessions), 0,
                           "No finger_maintenance_home in Base phase")
        for s in finger_sessions:
            self.assertEqual(s["intensity"], "medium",
                             f"finger_maintenance_home should be medium, got {s['intensity']}")


class TestPlannerV2PoolCycling(unittest.TestCase):
    """Tests for pool cycling and distribution (F2/F13 fix)."""

    def test_target_training_days_respected(self):
        """With target=6, at least 5 days should have sessions (non-deload)."""
        plan = generate_phase_week(**_make_kwargs("base",
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 3}))
        days = plan["weeks"][0]["days"]
        days_with_sessions = sum(1 for d in days if d["sessions"])
        self.assertGreaterEqual(days_with_sessions, 5,
                                f"Only {days_with_sessions} days with sessions, expected ≥5")

    def test_sessions_distributed_not_concentrated(self):
        """Sessions should not all be in the first 3 days."""
        plan = generate_phase_week(**_make_kwargs("base",
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 3}))
        days = plan["weeks"][0]["days"]
        first_3_sessions = sum(1 for d in days[:3] if d["sessions"])
        last_4_sessions = sum(1 for d in days[3:] if d["sessions"])
        self.assertGreater(last_4_sessions, 0,
                           "All sessions concentrated in first 3 days")

    def test_hard_days_have_spacing(self):
        """Hard sessions should not be on consecutive days."""
        plan = generate_phase_week(**_make_kwargs("strength_power",
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 3}))
        days = plan["weeks"][0]["days"]
        hard_offsets = []
        for i, d in enumerate(days):
            if any(s["tags"]["hard"] for s in d["sessions"]):
                hard_offsets.append(i)
        for prev, cur in zip(hard_offsets, hard_offsets[1:]):
            self.assertGreater(cur - prev, 1,
                               f"Consecutive hard days at offset {prev} and {cur}")

    def test_pool_cycles_when_small(self):
        """Even a small pool should produce sessions across the week."""
        plan = generate_phase_week(**_make_kwargs("power_endurance",
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 3}))
        days = plan["weeks"][0]["days"]
        days_with_sessions = sum(1 for d in days if d["sessions"])
        self.assertGreaterEqual(days_with_sessions, 5,
                                f"Only {days_with_sessions} days with sessions, expected ≥5")

    def test_two_pass_labels_present(self):
        """Plan should have both pass1 and pass2 labels (when complementary is needed)."""
        plan = generate_phase_week(**_make_kwargs("strength_power",
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 3}))
        days = plan["weeks"][0]["days"]
        all_explains = []
        for d in days:
            for s in d["sessions"]:
                all_explains.extend(s.get("explain", []))
        has_pass1 = any("pass1" in e for e in all_explains)
        has_pass2 = any("pass2" in e for e in all_explains)
        self.assertTrue(has_pass1, "No pass1 (primary) sessions found")
        self.assertTrue(has_pass2, "No pass2 (complementary) sessions found")


class TestPlannerV2PretripDeload(unittest.TestCase):
    """Tests for pre-trip deload (F8 fix)."""

    def test_pretrip_dates_block_hard_sessions(self):
        """Hard sessions should not be placed on pretrip deload dates."""
        # Mark Wed-Fri as pretrip dates
        pretrip = ["2026-03-04", "2026-03-05", "2026-03-06"]
        plan = generate_phase_week(**_make_kwargs("strength_power", pretrip_dates=pretrip))
        days = plan["weeks"][0]["days"]
        for d in days:
            if d["date"] in pretrip:
                for s in d["sessions"]:
                    self.assertFalse(s["tags"]["hard"],
                        f"Hard session {s['session_id']} on pretrip date {d['date']}")

    def test_pretrip_dates_marked_in_plan(self):
        """Days in pretrip window should have pretrip_deload=True flag."""
        pretrip = ["2026-03-04", "2026-03-05"]
        plan = generate_phase_week(**_make_kwargs("base", pretrip_dates=pretrip))
        days = plan["weeks"][0]["days"]
        for d in days:
            if d["date"] in pretrip:
                self.assertTrue(d.get("pretrip_deload"),
                    f"Missing pretrip_deload flag on {d['date']}")
            else:
                self.assertNotIn("pretrip_deload", d)

    def test_no_pretrip_dates_no_flags(self):
        """Without pretrip_dates, no days should have the flag."""
        plan = generate_phase_week(**_make_kwargs("base"))
        for d in plan["weeks"][0]["days"]:
            self.assertNotIn("pretrip_deload", d)


class TestPlannerV2TestSessions(unittest.TestCase):
    """Tests for test session scheduling (NEW-F3a)."""

    def test_last_week_base_has_test_sessions(self):
        """Last week of base: only repeater (endurance axis) — finger/pulling gated (B191/D92)."""
        # Use 7-day availability: the expanded base pool (6 primaries) needs more room
        # for pass 3 to inject test sessions without violating finger/hard spacing.
        full_avail = {wd: {"evening": {"available": True, "locations": ["gym", "home"]}}
                      for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
        plan = generate_phase_week(**_make_kwargs("base", is_last_week_of_phase=True,
            hard_cap_per_week=5, availability=full_avail,
            planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 5}))
        all_sessions = [s for d in plan["weeks"][0]["days"] for s in d["sessions"]]
        session_ids = {s["session_id"] for s in all_sessions}
        # B191/D92: finger not stimulated by Base → NOT scheduled
        self.assertNotIn("test_max_hang_7s", session_ids,
                          "Base phase must NOT schedule finger strength test (D92)")
        # Repeater IS stimulated by Base (ARC/endurance volume) → scheduled
        self.assertIn("test_repeater_7_3", session_ids,
                       "Last week of base phase should have test_repeater_7_3")

    def test_last_week_strength_power_has_test_sessions(self):
        """Last week of strength_power phase should include test sessions."""
        plan = generate_phase_week(**_make_kwargs("strength_power", is_last_week_of_phase=True,
            hard_cap_per_week=5,
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 5}))
        all_sessions = [s for d in plan["weeks"][0]["days"] for s in d["sessions"]]
        session_ids = {s["session_id"] for s in all_sessions}
        self.assertIn("test_max_hang_7s", session_ids,
                       "Last week of strength_power should have test_max_hang_7s")

    def test_non_last_week_no_test_session(self):
        """Non-last weeks should NOT have test sessions."""
        plan = generate_phase_week(**_make_kwargs("base", is_last_week_of_phase=False))
        all_sessions = [s for d in plan["weeks"][0]["days"] for s in d["sessions"]]
        test_sessions = [s for s in all_sessions if s["session_id"].startswith("test_")]
        self.assertEqual(len(test_sessions), 0,
                         "Non-last week should not have test sessions")

    def test_deload_phase_no_test_session(self):
        """Deload phase should never have test sessions."""
        plan = generate_phase_week(**_make_kwargs("deload", is_last_week_of_phase=True))
        all_sessions = [s for d in plan["weeks"][0]["days"] for s in d["sessions"]]
        test_sessions = [s for s in all_sessions if s["session_id"].startswith("test_")]
        self.assertEqual(len(test_sessions), 0,
                         "Deload phase should never have test sessions")

    def test_test_sessions_respect_finger_spacing(self):
        """Injected test sessions must not violate 48h finger gap."""
        plan = generate_phase_week(**_make_kwargs("base", is_last_week_of_phase=True,
            hard_cap_per_week=5,
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 5}))
        days = plan["weeks"][0]["days"]
        finger_dates = []
        for d in days:
            if any(s["tags"]["finger"] for s in d["sessions"]):
                finger_dates.append(datetime.strptime(d["date"], "%Y-%m-%d").date())
        for prev, cur in zip(finger_dates, finger_dates[1:]):
            self.assertGreater((cur - prev).days, 1,
                               f"Finger spacing violated: {prev} and {cur}")

    def test_test_session_has_pass3_explain(self):
        """Test sessions should have pass3:test_session in explain."""
        plan = generate_phase_week(**_make_kwargs("base", is_last_week_of_phase=True,
            hard_cap_per_week=5,
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 5}))
        all_sessions = [s for d in plan["weeks"][0]["days"] for s in d["sessions"]]
        test_sessions = [s for s in all_sessions if s["session_id"].startswith("test_")]
        self.assertGreater(len(test_sessions), 0, "No test sessions found")
        for ts in test_sessions:
            self.assertIn("pass3:test_session", ts.get("explain", []),
                          f"Test session {ts['session_id']} missing pass3 label")

    def test_test_sessions_have_test_tag(self):
        """Pass 3 test sessions must have tags.test = True for frontend guided UI."""
        plan = generate_phase_week(**_make_kwargs("base", is_last_week_of_phase=True,
            hard_cap_per_week=5,
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 5}))
        all_sessions = [s for d in plan["weeks"][0]["days"] for s in d["sessions"]]
        test_sessions = [s for s in all_sessions if s["session_id"].startswith("test_")]
        self.assertGreater(len(test_sessions), 0, "No test sessions found")
        for ts in test_sessions:
            self.assertTrue(ts["tags"].get("test"),
                            f"Test session {ts['session_id']} missing tags.test=True")

    def test_non_test_sessions_no_test_tag(self):
        """Regular sessions must NOT have tags.test."""
        plan = generate_phase_week(**_make_kwargs("base"))
        all_sessions = [s for d in plan["weeks"][0]["days"] for s in d["sessions"]]
        for s in all_sessions:
            if not s["session_id"].startswith("test_"):
                self.assertFalse(s["tags"].get("test"),
                                 f"Non-test session {s['session_id']} should not have tags.test")


class TestPlannerV2TestFreshness(unittest.TestCase):
    """B128: skip recently completed tests on macrocycle regeneration."""

    _full_avail = {wd: {"evening": {"available": True, "locations": ["gym", "home"]}}
                   for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    _test_kwargs = dict(
        is_last_week_of_phase=True,
        hard_cap_per_week=5,
        availability=_full_avail,
        planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 5},
    )

    def _session_ids(self, plan):
        return {s["session_id"] for d in plan["weeks"][0]["days"] for s in d["sessions"]}

    def test_all_tests_skipped_when_all_fresh(self):
        """All 3 tests completed 5 days ago → none scheduled."""
        recent = {"finger": "2026-02-25", "repeater": "2026-02-25", "pulling": "2026-02-25"}
        plan = generate_phase_week(**_make_kwargs("base", **self._test_kwargs,
            recent_test_dates=recent))
        sids = self._session_ids(plan)
        test_sids = {s for s in sids if s.startswith("test_")}
        self.assertEqual(test_sids, set(),
                         f"All tests are fresh — none should be scheduled, got {test_sids}")

    def test_partial_skip_only_fresh_tests(self):
        """Finger fresh, repeater stale → finger skipped, repeater scheduled."""
        recent = {"finger": "2026-02-25", "repeater": "2026-01-01"}
        plan = generate_phase_week(**_make_kwargs("base", **self._test_kwargs,
            recent_test_dates=recent))
        sids = self._session_ids(plan)
        self.assertNotIn("test_max_hang_5s", sids,
                         "Finger test is fresh — should be skipped")
        self.assertIn("test_repeater_7_3", sids,
                       "Repeater test is stale — should be scheduled")

    def test_no_recent_dates_all_tests_scheduled(self):
        """No recent_test_dates (None) → repeater scheduled; finger gated by phase (B191/D92)."""
        plan = generate_phase_week(**_make_kwargs("base", **self._test_kwargs,
            recent_test_dates=None))
        sids = self._session_ids(plan)
        self.assertNotIn("test_max_hang_5s", sids,
                          "Base phase must NOT schedule finger strength test (D92)")
        self.assertIn("test_repeater_7_3", sids)

    def test_empty_recent_dates_all_tests_scheduled(self):
        """Empty dict → repeater scheduled; finger gated by phase (B191/D92)."""
        plan = generate_phase_week(**_make_kwargs("base", **self._test_kwargs,
            recent_test_dates={}))
        sids = self._session_ids(plan)
        self.assertNotIn("test_max_hang_5s", sids,
                          "Base phase must NOT schedule finger strength test (D92)")
        self.assertIn("test_repeater_7_3", sids)

    def test_scheduled_but_not_completed_reschedules(self):
        """Test was scheduled but NOT completed — no date in baselines/tests.
        Only pulling has a date; repeater has no entry → must be rescheduled.
        Finger has no date but Base phase doesn't target it → still gated (B191/D92)."""
        recent = {"pulling": "2026-02-25"}  # finger and repeater: no entry
        plan = generate_phase_week(**_make_kwargs("base", **self._test_kwargs,
            recent_test_dates=recent))
        sids = self._session_ids(plan)
        self.assertNotIn("test_max_hang_5s", sids,
                          "Finger test gated by Base phase (D92) even without completion date")
        self.assertIn("test_repeater_7_3", sids,
                       "Repeater test has no completion date — must be rescheduled")

    def test_short_phase_edge_case_2_weeks(self):
        """Short phase (2 weeks): test completed day 1 (Mon), last week starts day 8.
        Delta = 7 days < 14 → tests should be skipped."""
        # Phase starts 2026-02-24 (Mon), test done that day.
        # Last week starts 2026-03-03 (Mon), 7 days later.
        recent = {
            "finger": "2026-02-24",
            "repeater": "2026-02-24",
            "pulling": "2026-02-24",
        }
        plan = generate_phase_week(**_make_kwargs("base", **self._test_kwargs,
            start_date="2026-03-03", recent_test_dates=recent))
        sids = self._session_ids(plan)
        test_sids = {s for s in sids if s.startswith("test_")}
        self.assertEqual(test_sids, set(),
                         f"Tests completed 7 days ago in 2-week phase — should be skipped, got {test_sids}")

    def test_stale_at_exactly_42_days(self):
        """B138: Test completed exactly 42 days before week start — stale.
        In Base phase: repeater (stale) → rescheduled; finger (gated) → not scheduled (B191/D92)."""
        # 2026-03-02 minus 42 days = 2026-01-19
        recent = {"finger": "2026-01-19", "repeater": "2026-01-19", "pulling": "2026-01-19"}
        plan = generate_phase_week(**_make_kwargs("base", **self._test_kwargs,
            recent_test_dates=recent))
        sids = self._session_ids(plan)
        self.assertNotIn("test_max_hang_5s", sids,
                          "Finger gated by Base phase (D92) regardless of freshness")
        self.assertIn("test_repeater_7_3", sids,
                       "Repeater exactly 42 days old in Base phase — should be rescheduled")

    def test_fresh_at_41_days(self):
        """B138: Test completed 41 days before week start → still fresh, should be skipped."""
        # 2026-03-02 minus 41 days = 2026-01-20
        recent = {"finger": "2026-01-20", "repeater": "2026-01-20", "pulling": "2026-01-20"}
        plan = generate_phase_week(**_make_kwargs("base", **self._test_kwargs,
            start_date="2026-03-02", recent_test_dates=recent))
        sids = self._session_ids(plan)
        test_sids = {s for s in sids if s.startswith("test_")}
        self.assertEqual(test_sids, set(),
                         f"Tests completed 13 days ago — should be skipped, got {test_sids}")

    def test_inject_tests_explicit_bypasses_freshness(self):
        """B210: inject_tests=True (explicit user intent) bypasses the freshness window."""
        recent = {"finger": "2026-02-25", "repeater": "2026-02-25", "pulling": "2026-02-25"}
        plan = generate_phase_week(**_make_kwargs("base",
            is_last_week_of_phase=False, inject_tests=True,
            hard_cap_per_week=5, availability=self._full_avail,
            planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 5},
            recent_test_dates=recent))
        sids = self._session_ids(plan)
        test_sids = {s for s in sids if s.startswith("test_")}
        self.assertNotEqual(test_sids, set(),
                            "B210: inject_tests=True must schedule tests even when all recently tested")


class TestPlannerV2PhaseAwareGating(unittest.TestCase):
    """B191/D92: phase-aware test scheduling — only tests stimulated by the phase are scheduled."""

    _full_avail = {wd: {"evening": {"available": True, "locations": ["gym", "home"]}}
                   for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    _common = dict(
        is_last_week_of_phase=True,
        hard_cap_per_week=5,
        availability=_full_avail,
        planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 5},
        recent_test_dates=None,
    )

    def _session_ids(self, plan):
        return {s["session_id"] for d in plan["weeks"][0]["days"] for s in d["sessions"]}

    def _skipped(self, plan):
        return plan.get("skipped_tests", [])

    def test_base_phase_only_repeater(self):
        """Base last week: only repeater scheduled; finger + pulling gated."""
        plan = generate_phase_week(**_make_kwargs("base", **self._common))
        sids = self._session_ids(plan)
        self.assertNotIn("test_max_hang_5s", sids,
                          "Base phase must NOT schedule finger test (axis not stimulated)")
        self.assertIn("test_repeater_7_3", sids,
                       "Base phase MUST schedule repeater test (endurance axis stimulated)")
        self.assertNotIn("test_max_weighted_pullup", sids)
        self.assertNotIn("test_pullup_bw", sids)

    def test_strength_power_all_three_tests(self):
        """Strength_power last week: all three tests scheduled."""
        plan = generate_phase_week(**_make_kwargs("strength_power", **self._common))
        sids = self._session_ids(plan)
        self.assertIn("test_max_hang_7s", sids,
                       "Strength_power must schedule finger test")
        self.assertIn("test_repeater_7_3", sids,
                       "Strength_power must schedule repeater test")

    def test_power_endurance_no_tests(self):
        """Power_endurance last week: no tests (Pass 3 only fires for base/strength_power)."""
        plan = generate_phase_week(**_make_kwargs("power_endurance", **self._common))
        sids = self._session_ids(plan)
        test_sids = {s for s in sids if s.startswith("test_")}
        self.assertEqual(test_sids, set(),
                         f"PE phase doesn't trigger Pass 3 — no tests expected, got {test_sids}")

    def test_performance_no_tests(self):
        """Performance last week: no tests (Pass 3 doesn't run for performance phase)."""
        plan = generate_phase_week(**_make_kwargs("performance", **self._common))
        sids = self._session_ids(plan)
        test_sids = {s for s in sids if s.startswith("test_")}
        self.assertEqual(test_sids, set(),
                         f"Performance phase should have no tests, got {test_sids}")

    def test_skipped_tests_populated_base(self):
        """skipped_tests contains finger + pulling entries for base phase."""
        plan = generate_phase_week(**_make_kwargs("base", **self._common))
        skipped = self._skipped(plan)
        axes = {e["axis"] for e in skipped}
        self.assertIn("finger", axes,
                       "skipped_tests must contain finger entry for base phase")
        self.assertIn("pulling", axes,
                       "skipped_tests must contain pulling entry for base phase")
        self.assertNotIn("repeater", axes,
                          "repeater must NOT be in skipped_tests for base phase")

    def test_skipped_tests_empty_non_pass3(self):
        """skipped_tests is empty when Pass 3 doesn't run (non-last week)."""
        plan = generate_phase_week(**_make_kwargs("base", is_last_week_of_phase=False))
        self.assertEqual(plan.get("skipped_tests", []), [],
                         "skipped_tests must be empty when Pass 3 doesn't run")

    def test_skipped_tests_reason_contains_d92(self):
        """Each skipped entry has a reason string referencing D92."""
        plan = generate_phase_week(**_make_kwargs("base", **self._common))
        for entry in plan.get("skipped_tests", []):
            self.assertIn("D92", entry["reason"],
                           f"skipped entry {entry['axis']} missing D92 reference")

    def test_maintenance_cap_12_weeks(self):
        """Axis untested for 12+ weeks in base phase → maintenance retest fires."""
        # finger untested since >12 weeks before 2026-03-02
        old_date = "2025-12-01"  # ~13 weeks before 2026-03-02
        common_no_recent = {k: v for k, v in self._common.items() if k != "recent_test_dates"}
        plan = generate_phase_week(**_make_kwargs("base", **common_no_recent,
            recent_test_dates={"finger": old_date, "repeater": old_date, "pulling": old_date}))
        sids = self._session_ids(plan)
        self.assertIn("test_max_hang_7s", sids,
                       "Finger untested 12+ weeks → maintenance retest must fire even in base phase")

    def test_under_maintenance_cap_still_gated(self):
        """Axis untested for 8 weeks in base phase → still gated (under 12-week cap)."""
        # 8 weeks = 56 days before 2026-03-02 → 2026-01-05
        common_no_recent = {k: v for k, v in self._common.items() if k != "recent_test_dates"}
        plan = generate_phase_week(**_make_kwargs("base", **common_no_recent,
            recent_test_dates={"finger": "2026-01-05"}))
        sids = self._session_ids(plan)
        self.assertNotIn("test_max_hang_5s", sids,
                          "8 weeks untested in base — still under cap, must remain gated")


class TestPlannerV2LoadScore(unittest.TestCase):
    """Tests for B4 — load score and weekly load summary."""

    def test_sessions_have_estimated_load_score(self):
        """Every session entry must have estimated_load_score."""
        plan = generate_phase_week(**_make_kwargs("base"))
        for d in plan["weeks"][0]["days"]:
            for s in d["sessions"]:
                self.assertIn("estimated_load_score", s,
                              f"Session {s['session_id']} missing load score")
                self.assertIsInstance(s["estimated_load_score"], int)

    def test_load_score_matches_intensity(self):
        """Load score must match the intensity-to-load mapping."""
        mapping = {"low": 20, "medium": 40, "high": 65, "max": 85}
        for phase_id in ("base", "strength_power", "power_endurance", "performance"):
            plan = generate_phase_week(**_make_kwargs(phase_id))
            for d in plan["weeks"][0]["days"]:
                for s in d["sessions"]:
                    expected = mapping.get(s["intensity"], 40)
                    self.assertEqual(s["estimated_load_score"], expected,
                        f"Phase {phase_id}: {s['session_id']} intensity={s['intensity']} "
                        f"expected load={expected}, got {s['estimated_load_score']}")

    def test_weekly_load_summary_present(self):
        """Week plan must have weekly_load_summary with planned_load."""
        plan = generate_phase_week(**_make_kwargs("base"))
        self.assertIn("weekly_load_summary", plan)
        summary = plan["weekly_load_summary"]
        self.assertIn("planned_load", summary)
        self.assertIn("total_load", summary)  # backward compat
        self.assertIn("hard_days_count", summary)
        self.assertIn("recovery_days_count", summary)

    def test_weekly_load_summary_correct_total(self):
        """planned_load must equal sum of all session load scores."""
        plan = generate_phase_week(**_make_kwargs("strength_power"))
        expected_total = sum(
            s.get("estimated_load_score", 0)
            for d in plan["weeks"][0]["days"]
            for s in d["sessions"]
        )
        self.assertEqual(plan["weekly_load_summary"]["planned_load"], expected_total)
        self.assertEqual(plan["weekly_load_summary"]["total_load"], expected_total)

    def test_planned_load_equals_total_load_at_generation(self):
        """B164: at generation, planned_load == total_load."""
        plan = generate_phase_week(**_make_kwargs("base"))
        summary = plan["weekly_load_summary"]
        self.assertEqual(summary["planned_load"], summary["total_load"])

    def test_deload_week_low_load(self):
        """Deload week should have low total load."""
        plan = generate_phase_week(**_make_kwargs("deload"))
        summary = plan["weekly_load_summary"]
        self.assertEqual(summary["hard_days_count"], 0)
        # All deload sessions are low intensity, max 20 per session, max 5 sessions (B160c)
        self.assertLessEqual(summary["planned_load"], 20 * 5)
        self.assertLessEqual(summary["total_load"], 20 * 5)


class TestPlannerV2OtherActivity(unittest.TestCase):
    """Tests for B41 — other activities in availability."""

    def test_other_activity_allows_sessions_no_hard(self):
        """Day with _day_meta.other_activity=True still gets sessions (no hard) and the flag."""
        avail = _base_availability()
        avail["wed"]["_day_meta"] = {"other_activity": True, "other_activity_name": "Trail running"}
        plan = generate_phase_week(**_make_kwargs("strength_power", availability=avail))
        days = plan["weeks"][0]["days"]
        wed = next(d for d in days if d["weekday"] == "wed")
        # B276: emitted as a per-slot list.
        self.assertTrue(wed.get("other_activities"), "Missing other_activities list")
        self.assertEqual(wed["other_activities"][0].get("name"), "Trail running")
        # Sessions are allowed, but no hard sessions on this day
        for s in wed["sessions"]:
            self.assertFalse(s["tags"]["hard"],
                             f"Hard session {s['session_id']} on other-activity day")

    def test_other_activity_reduce_after(self):
        """Day after other-activity with reduce_intensity_after=True gets no hard sessions and the flag."""
        avail = _base_availability()
        avail["wed"]["_day_meta"] = {
            "other_activity": True,
            "reduce_intensity_after": True,
        }
        plan = generate_phase_week(**_make_kwargs("strength_power", availability=avail))
        days = plan["weeks"][0]["days"]
        thu = next(d for d in days if d["weekday"] == "thu")
        self.assertTrue(thu.get("prev_other_activity_reduce"),
                        "Missing prev_other_activity_reduce flag on day after")
        for s in thu["sessions"]:
            meta = {"hard": s["tags"]["hard"]}
            self.assertFalse(meta["hard"],
                             f"Hard session {s['session_id']} on intensity-reduced day")

    def test_other_activity_no_reduce(self):
        """Day after other-activity without reduce flag gets normal sessions (hard allowed)."""
        avail = _base_availability()
        avail["wed"]["_day_meta"] = {"other_activity": True}
        plan = generate_phase_week(**_make_kwargs("strength_power", availability=avail))
        days = plan["weeks"][0]["days"]
        thu = next(d for d in days if d["weekday"] == "thu")
        self.assertNotIn("prev_other_activity_reduce", thu,
                         "Should NOT have reduce flag when not requested")

    def test_per_slot_other_sport_blocks_slot(self):
        """Slot with preferred_location='other_sport' is unavailable for climbing but other slots work."""
        avail = _base_availability()
        # Mark Wed evening as other_sport (circus)
        avail["wed"]["evening"] = {
            "available": True, "preferred_location": "other_sport",
            "other_activity_name": "Circus",
        }
        plan = generate_phase_week(**_make_kwargs("base", availability=avail))
        days = plan["weeks"][0]["days"]
        wed = next(d for d in days if d["weekday"] == "wed")
        # B276: the other activity should be in the per-slot list
        self.assertTrue(wed.get("other_activities"), "Missing other_activities list")
        self.assertEqual(wed["other_activities"][0].get("name"), "Circus")
        self.assertEqual(wed["other_activities"][0].get("slot"), "evening")
        # No session should be in the evening slot (blocked by other_sport)
        for s in wed["sessions"]:
            self.assertNotEqual(s["slot"], "evening",
                                "Climbing session placed in other_sport slot")


class TestEquipmentAwarePlacement(unittest.TestCase):
    """E2E tests: planner respects required_equipment when choosing location."""

    def _gym_home_avail(self):
        """All days: evening slot, both gym and home viable, prefer home."""
        avail = {}
        for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
            avail[wd] = {
                "evening": {"available": True, "locations": ["gym", "home"],
                            "preferred_location": "home"},
            }
        return avail

    def _full_gym(self):
        return [{"gym_id": "test_gym", "equipment": [
            "hangboard", "gym_boulder", "gym_routes", "dumbbell",
            "pullup_bar", "campus_board", "kettlebell", "band",
        ]}]

    def test_pullup_test_at_gym_when_home_lacks_pullup_bar(self):
        """test_max_weighted_pullup requires pullup_bar.
        Home has NO pullup_bar → planner must place it at gym.
        B128: pass pulling_baseline to route to weighted test."""
        from backend.engine.planner_v2 import generate_test_week
        plan = generate_test_week(
            start_date="2026-03-02",
            availability=self._gym_home_avail(),
            allowed_locations=["gym", "home"],
            gyms=self._full_gym(),
            default_gym_id="test_gym",
            home_equipment=["band", "dumbbell"],  # NO pullup_bar (A193: hangboard would imply pullup_bar)
            pulling_baseline={"max_total_load_kg": 100},
        )
        for day in plan["weeks"][0]["days"]:
            for s in day["sessions"]:
                if s["session_id"] == "test_max_weighted_pullup":
                    self.assertEqual(s["location"], "gym",
                                     "pullup test should be at gym when home lacks pullup_bar")
                    return
        self.fail("test_max_weighted_pullup not found in test week")

    def test_pullup_test_at_home_when_home_has_pullup_bar(self):
        """test_max_weighted_pullup requires pullup_bar.
        Home HAS pullup_bar + preference is home → planner places it at home.
        B128: pass pulling_baseline to route to weighted test."""
        from backend.engine.planner_v2 import generate_test_week
        plan = generate_test_week(
            start_date="2026-03-02",
            availability=self._gym_home_avail(),
            allowed_locations=["gym", "home"],
            gyms=self._full_gym(),
            default_gym_id="test_gym",
            pulling_baseline={"max_total_load_kg": 100},
            home_equipment=["hangboard", "band", "dumbbell", "pullup_bar"],  # HAS pullup_bar
        )
        for day in plan["weeks"][0]["days"]:
            for s in day["sessions"]:
                if s["session_id"] == "test_max_weighted_pullup":
                    self.assertEqual(s["location"], "home",
                                     "pullup test should be at home when home has pullup_bar and preference is home")
                    return
        self.fail("test_max_weighted_pullup not found in test week")

    def test_hangboard_sessions_at_gym_when_home_lacks_hangboard(self):
        """Sessions requiring hangboard should go to gym when home has none."""
        from backend.engine.planner_v2 import generate_test_week
        plan = generate_test_week(
            start_date="2026-03-02",
            availability=self._gym_home_avail(),
            allowed_locations=["gym", "home"],
            gyms=self._full_gym(),
            default_gym_id="test_gym",
            home_equipment=["band", "dumbbell"],  # NO hangboard
        )
        hangboard_sessions = {"test_max_hang_5s", "test_repeater_7_3"}
        for day in plan["weeks"][0]["days"]:
            for s in day["sessions"]:
                if s["session_id"] in hangboard_sessions:
                    self.assertEqual(s["location"], "gym",
                                     f"{s['session_id']} should be at gym when home lacks hangboard")

    def test_phase_week_respects_gym_equipment(self):
        """pulling_strength_gym requires pullup_bar — gym has it implicitly."""
        plan = generate_phase_week(**_make_kwargs(
            "strength_power",
            availability=self._gym_home_avail(),
            gyms=self._full_gym(),
            default_gym_id="test_gym",
            home_equipment=["hangboard", "band"],  # NO pullup_bar
        ))
        for day in plan["weeks"][0]["days"]:
            for s in day["sessions"]:
                if s["session_id"] == "pulling_strength_gym":
                    self.assertEqual(s["location"], "gym",
                                     "pulling_strength_gym needs pullup_bar → must be at gym")

    def test_no_equipment_info_falls_back_to_allow_all(self):
        """When no home_equipment or gyms are given, all placements should work (backwards compat)."""
        plan = generate_phase_week(**_make_kwargs("base"))
        total_sessions = sum(
            len(d["sessions"]) for d in plan["weeks"][0]["days"]
        )
        self.assertGreater(total_sessions, 0, "Should generate sessions even without equipment info")


class TestPlannerV2HomewallExpansion(unittest.TestCase):
    """B137: Users with homewall should get climbing sessions assigned on home days."""

    _WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

    def _home_only_avail(self):
        """All days prefer home."""
        avail = {}
        for wd in self._WEEKDAYS:
            avail[wd] = {"evening": {"available": True, "preferred_location": "home"}}
        return avail

    def test_homewall_gets_climbing_sessions_at_home(self):
        """User with homewall should get boulder climbing sessions on home days."""
        from backend.engine.planner_v2 import _SESSION_META
        plan = generate_phase_week(**_make_kwargs(
            "base",
            availability=self._home_only_avail(),
            home_equipment=["hangboard", "pullup_bar", "homewall"],
            gyms=[],
            default_gym_id=None,
        ))
        all_sids = [
            s["session_id"]
            for d in plan["weeks"][0]["days"]
            for s in d["sessions"]
        ]
        climbing_sids = [
            sid for sid in all_sids
            if _SESSION_META.get(sid, {}).get("climbing")
            and "gym_boulder" in _SESSION_META.get(sid, {}).get("required_equipment", [])
        ]
        self.assertGreater(len(climbing_sids), 0,
                           f"Homewall user should get gym_boulder sessions at home. Got: {all_sids}")
        # All sessions should be location=home
        for d in plan["weeks"][0]["days"]:
            for s in d["sessions"]:
                self.assertEqual(s["location"], "home",
                                 f"All sessions should be at home, got {s['location']} for {s['session_id']}")

    def test_no_homewall_no_climbing_at_home(self):
        """User WITHOUT homewall should NOT get climbing sessions at home."""
        from backend.engine.planner_v2 import _SESSION_META
        plan = generate_phase_week(**_make_kwargs(
            "base",
            availability=self._home_only_avail(),
            home_equipment=["hangboard", "pullup_bar"],
            gyms=[],
            default_gym_id=None,
        ))
        all_sids = [
            s["session_id"]
            for d in plan["weeks"][0]["days"]
            for s in d["sessions"]
        ]
        climbing_boulder_sids = [
            sid for sid in all_sids
            if "gym_boulder" in _SESSION_META.get(sid, {}).get("required_equipment", [])
        ]
        self.assertEqual(len(climbing_boulder_sids), 0,
                         f"Without homewall, no gym_boulder sessions at home. Got: {climbing_boulder_sids}")

    def test_route_sessions_not_at_home_with_homewall(self):
        """Even with homewall, gym_routes sessions should NOT appear at home."""
        from backend.engine.planner_v2 import _SESSION_META
        plan = generate_phase_week(**_make_kwargs(
            "base",
            availability=self._home_only_avail(),
            home_equipment=["hangboard", "pullup_bar", "homewall"],
            gyms=[],
            default_gym_id=None,
        ))
        all_sids = [
            s["session_id"]
            for d in plan["weeks"][0]["days"]
            for s in d["sessions"]
        ]
        route_sids = [
            sid for sid in all_sids
            if "gym_routes" in _SESSION_META.get(sid, {}).get("required_equipment", [])
        ]
        self.assertEqual(len(route_sids), 0,
                         f"Route sessions should never appear at home. Got: {route_sids}")


class TestPlannerV2B208NarrowExpansion(unittest.TestCase):
    """B208: _expand_session_locations only triggers for wall-surface sessions.

    Reproduces Daniele 2026-04-17: finger_maintenance_gym (req=["hangboard"])
    was silently re-routed to a home slot because every required_equipment
    item existed at home, even though the session is authored as gym-only and
    its warmup template assumes a gym wall surface.
    """

    def test_finger_maintenance_gym_with_hangboard_at_home_stays_at_gym(self):
        """User has a gym AND hangboard at home: finger_maintenance_gym must
        be placed at the gym slot, never at the home slot."""
        # Both gym and home days available; home day prefers home.
        availability = {
            "mon": {"evening": {"available": True, "preferred_location": "gym",
                                "gym_id": "blocx"}},
            "wed": {"evening": {"available": True, "preferred_location": "gym",
                                "gym_id": "blocx"}},
            "fri": {"evening": {"available": True, "preferred_location": "home"}},
            "sat": {"morning": {"available": True, "preferred_location": "gym",
                                "gym_id": "blocx"}},
        }
        plan = generate_phase_week(**_make_kwargs(
            "power_endurance",
            availability=availability,
            home_equipment=["hangboard", "pullup_bar", "band", "dumbbell"],
            gyms=[{"gym_id": "blocx", "priority": 1,
                   "equipment": ["gym_boulder", "gym_routes", "hangboard",
                                 "pullup_bar", "dumbbell"]}],
            default_gym_id="blocx",
        ))
        for day in plan["weeks"][0]["days"]:
            for ss in day.get("sessions", []):
                if ss["session_id"] == "finger_maintenance_gym":
                    self.assertEqual(ss["location"], "gym",
                                     f"finger_maintenance_gym must stay at gym "
                                     f"when home has only hangboard (no wall). "
                                     f"Got: {ss['location']} on {day['date']}")

    def test_hangboard_only_user_no_gym_does_not_get_finger_maintenance_gym_at_home(self):
        """User has hangboard at home and no gym: finger_maintenance_gym is NOT
        re-routed to home; only finger_maintenance_home is scheduled (or no
        finger-maintenance session at all)."""
        availability = {wd: {"evening": {"available": True,
                                         "preferred_location": "home"}}
                        for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
        plan = generate_phase_week(**_make_kwargs(
            "power_endurance",
            availability=availability,
            home_equipment=["hangboard", "pullup_bar", "band"],
            gyms=[],
            default_gym_id=None,
        ))
        session_ids = [
            ss["session_id"]
            for day in plan["weeks"][0]["days"]
            for ss in day.get("sessions", [])
        ]
        self.assertNotIn("finger_maintenance_gym", session_ids,
                         "finger_maintenance_gym must never be scheduled "
                         "when the user has no wall at home and no gym. "
                         f"Got: {session_ids}")


class TestPlannerV2B84GymSelection(unittest.TestCase):
    """B84 — Bug A: gym selection iterates all gyms by priority until one has equipment."""

    def _routes_avail(self):
        """Three gym-available days, no specific gym_id (empty string)."""
        return {
            "mon": {"evening": {"available": True, "preferred_location": "gym", "gym_id": ""}},
            "wed": {"evening": {"available": True, "preferred_location": "gym", "gym_id": ""}},
            "fri": {"evening": {"available": True, "preferred_location": "gym", "gym_id": ""}},
            "sat": {"morning": {"available": True, "preferred_location": "gym", "gym_id": ""}},
        }

    def test_routes_session_placed_at_gym2_when_gym1_lacks_routes(self):
        """Bug A: gym1 (priority 1) has no gym_routes; gym2 (priority 2) has gym_routes.
        A session requiring gym_routes must be placed at gym2, not skipped."""
        gyms = [
            {"gym_id": "gym_no_routes", "priority": 1,
             "equipment": ["gym_boulder", "hangboard", "pullup_bar"]},
            {"gym_id": "gym_with_routes", "priority": 2,
             "equipment": ["gym_boulder", "hangboard", "gym_routes", "pullup_bar"]},
        ]
        # Pool with gym_routes-requiring sessions
        pool = ["endurance_aerobic_gym", "power_endurance_gym", "route_endurance_gym",
                "technique_focus_gym", "prehab_maintenance"]
        plan = generate_phase_week(
            phase_id="base",
            domain_weights={"finger_strength": 0.3, "power_endurance": 0.3, "endurance": 0.4},
            session_pool=pool,
            start_date="2026-03-02",
            availability=self._routes_avail(),
            allowed_locations=["gym"],
            hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
            gyms=gyms,
        )
        days = plan["weeks"][0]["days"]
        routes_sessions = [
            s for d in days for s in d["sessions"]
            if s["session_id"] in {"endurance_aerobic_gym", "power_endurance_gym", "route_endurance_gym"}
        ]
        self.assertGreater(len(routes_sessions), 0,
                           "At least one gym_routes session must be placed when gym2 has gym_routes")
        for s in routes_sessions:
            self.assertEqual(s["gym_id"], "gym_with_routes",
                             f"{s['session_id']} must be placed at gym_with_routes, not {s['gym_id']}")

    def test_routes_session_gym_id_assigned_correctly(self):
        """Bug A: when gym_id is empty in slot, _select_gym_id must pick the gym
        that has the required equipment, not always the first by priority."""
        gyms = [
            {"gym_id": "cheap_gym", "priority": 1,
             "equipment": ["gym_boulder"]},
            {"gym_id": "full_gym", "priority": 2,
             "equipment": ["gym_boulder", "gym_routes", "hangboard", "pullup_bar"]},
        ]
        pool = ["route_endurance_gym", "technique_focus_gym", "prehab_maintenance"]
        plan = generate_phase_week(
            phase_id="base",
            domain_weights={"endurance": 0.5, "technique": 0.3, "finger_strength": 0.2},
            session_pool=pool,
            start_date="2026-03-02",
            availability=self._routes_avail(),
            allowed_locations=["gym"],
            hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
            gyms=gyms,
        )
        days = plan["weeks"][0]["days"]
        for d in days:
            for s in d["sessions"]:
                if s["session_id"] == "route_endurance_gym":
                    self.assertEqual(s["gym_id"], "full_gym",
                                     "route_endurance_gym must be assigned to full_gym (has gym_routes)")
                    return
        # If route_endurance_gym not placed, technique_focus_gym is fine (gym_boulder only)
        # The test still passes as long as NO route session ended up at cheap_gym


class TestPlannerV2B201PreferredGymRouting(unittest.TestCase):
    """B201 — power_endurance_gym is a soft preference for gyms with gym_routes.

    PE session has required_equipment=[gym_boulder] and
    preferred_equipment=[gym_routes]. Both gyms satisfy required, only one
    satisfies preferred → planner must pick the route-gym (without dropping
    sessions when no gym has routes).
    """

    def _gym_avail(self):
        return {
            "mon": {"evening": {"available": True, "preferred_location": "gym", "gym_id": ""}},
            "wed": {"evening": {"available": True, "preferred_location": "gym", "gym_id": ""}},
            "fri": {"evening": {"available": True, "preferred_location": "gym", "gym_id": ""}},
            "sat": {"morning": {"available": True, "preferred_location": "gym", "gym_id": ""}},
        }

    def test_pe_prefers_gym_with_routes_when_multiple_gyms(self):
        """BKL (priority 1, boulder only) vs Melloblocco (priority 2, boulder + routes).
        Both satisfy required_equipment=gym_boulder for PE; only Melloblocco satisfies
        preferred_equipment=gym_routes → PE must be assigned to Melloblocco even
        though BKL has higher priority."""
        gyms = [
            {"gym_id": "bkl", "priority": 1,
             "equipment": ["gym_boulder", "hangboard", "pullup_bar"]},
            {"gym_id": "melloblocco", "priority": 2,
             "equipment": ["gym_boulder", "gym_routes", "hangboard", "pullup_bar"]},
        ]
        pool = ["power_endurance_gym", "technique_focus_gym",
                "prehab_maintenance", "flexibility_full"]
        plan = generate_phase_week(
            phase_id="power_endurance",
            domain_weights={"power_endurance": 0.6, "technique": 0.2, "finger_strength": 0.2},
            session_pool=pool,
            start_date="2026-03-02",
            availability=self._gym_avail(),
            allowed_locations=["gym"],
            hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
            gyms=gyms,
        )
        days = plan["weeks"][0]["days"]
        pe_sessions = [
            s for d in days for s in d["sessions"]
            if s["session_id"] == "power_endurance_gym"
        ]
        self.assertGreater(len(pe_sessions), 0,
                           "PE session must be placed when both gyms can host it")
        for s in pe_sessions:
            self.assertEqual(
                s["gym_id"], "melloblocco",
                f"PE session must prefer the route-gym (got {s['gym_id']})",
            )

    def test_pe_still_placed_when_no_gym_has_routes(self):
        """When no gym has gym_routes, PE must still be placed on the
        boulder-only gym (soft preference, never drops the session)."""
        gyms = [
            {"gym_id": "bkl", "priority": 1,
             "equipment": ["gym_boulder", "hangboard", "pullup_bar"]},
        ]
        pool = ["power_endurance_gym", "technique_focus_gym",
                "prehab_maintenance", "flexibility_full"]
        plan = generate_phase_week(
            phase_id="power_endurance",
            domain_weights={"power_endurance": 0.6, "technique": 0.2, "finger_strength": 0.2},
            session_pool=pool,
            start_date="2026-03-02",
            availability=self._gym_avail(),
            allowed_locations=["gym"],
            hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
            gyms=gyms,
        )
        days = plan["weeks"][0]["days"]
        pe_sessions = [
            s for d in days for s in d["sessions"]
            if s["session_id"] == "power_endurance_gym"
        ]
        self.assertGreater(len(pe_sessions), 0,
                           "PE session must still be placed when no gym has routes (soft preference)")
        for s in pe_sessions:
            self.assertEqual(s["gym_id"], "bkl")

    def test_preferred_equipment_no_effect_with_single_gym(self):
        """Single gym with routes → PE assigned to it (baseline check, no regression)."""
        gyms = [
            {"gym_id": "only_gym", "priority": 1,
             "equipment": ["gym_boulder", "gym_routes", "hangboard", "pullup_bar"]},
        ]
        pool = ["power_endurance_gym", "technique_focus_gym", "prehab_maintenance"]
        plan = generate_phase_week(
            phase_id="power_endurance",
            domain_weights={"power_endurance": 0.6, "technique": 0.2, "finger_strength": 0.2},
            session_pool=pool,
            start_date="2026-03-02",
            availability=self._gym_avail(),
            allowed_locations=["gym"],
            hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
            gyms=gyms,
        )
        pe_sessions = [
            s for d in plan["weeks"][0]["days"] for s in d["sessions"]
            if s["session_id"] == "power_endurance_gym"
        ]
        self.assertGreater(len(pe_sessions), 0)
        for s in pe_sessions:
            self.assertEqual(s["gym_id"], "only_gym")


class TestPlannerV2B84ClimbingFallback(unittest.TestCase):
    """B84 — Bug B: fallback to gym_boulder climbing when pool sessions all require gym_routes."""

    def _gym_no_routes_avail(self):
        return {
            "mon": {"evening": {"available": True, "preferred_location": "gym"}},
            "wed": {"evening": {"available": True, "preferred_location": "gym"}},
            "fri": {"evening": {"available": True, "preferred_location": "gym"}},
            "sat": {"morning": {"available": True, "preferred_location": "gym"}},
        }

    def _gym_no_routes(self):
        return [{"gym_id": "no_routes_gym", "priority": 1,
                 "equipment": ["gym_boulder", "hangboard", "pullup_bar"]}]

    def test_fallback_climbing_placed_when_pool_needs_gym_routes(self):
        """Bug B: pool only has gym_routes sessions; gym has no gym_routes.
        Pass 1.5 must place technique_focus_gym or easy_climbing_deload instead."""
        pool = ["endurance_aerobic_gym", "power_endurance_gym", "route_endurance_gym",
                "prehab_maintenance", "flexibility_full"]
        plan = generate_phase_week(
            phase_id="base",
            domain_weights={"endurance": 0.5, "power_endurance": 0.3, "finger_strength": 0.2},
            session_pool=pool,
            start_date="2026-03-02",
            availability=self._gym_no_routes_avail(),
            allowed_locations=["gym"],
            hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
            gyms=self._gym_no_routes(),
        )
        days = plan["weeks"][0]["days"]
        climbing_fallback_ids = {"technique_focus_gym", "easy_climbing_deload"}
        fallback_sessions = [
            s for d in days for s in d["sessions"]
            if s["session_id"] in climbing_fallback_ids
        ]
        self.assertGreater(len(fallback_sessions), 0,
                           "Pass 1.5 must place a fallback climbing session when pool needs gym_routes "
                           "but gym only has gym_boulder")

    def test_fallback_not_triggered_when_gym_has_routes(self):
        """Bug B negative: when gym has gym_routes, pool sessions are placed normally
        and fallback must NOT fire (no spurious extra sessions)."""
        pool = ["endurance_aerobic_gym", "route_endurance_gym",
                "prehab_maintenance", "flexibility_full"]
        gyms_with_routes = [{"gym_id": "full_gym", "priority": 1,
                              "equipment": ["gym_boulder", "gym_routes", "hangboard", "pullup_bar"]}]
        plan = generate_phase_week(
            phase_id="base",
            domain_weights={"endurance": 0.5, "power_endurance": 0.3, "finger_strength": 0.2},
            session_pool=pool,
            start_date="2026-03-02",
            availability=self._gym_no_routes_avail(),
            allowed_locations=["gym"],
            hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
            gyms=gyms_with_routes,
        )
        days = plan["weeks"][0]["days"]
        all_sessions = [s for d in days for s in d["sessions"]]
        # Pool sessions should be placed, not fallbacks
        pool_placed = [s for s in all_sessions if s["session_id"] in {"endurance_aerobic_gym", "route_endurance_gym"}]
        self.assertGreater(len(pool_placed), 0,
                           "When gym has gym_routes, pool routes sessions must be placed normally")
        # Verify no fallback session snuck in via pass 1.5
        fallback_sessions = [s for s in all_sessions
                             if s["session_id"] in {"technique_focus_gym", "easy_climbing_deload"}
                             and "pass1.5" in " ".join(s.get("explain", []))]
        self.assertEqual(len(fallback_sessions), 0,
                         "Fallback must not fire when gym has gym_routes — pool sessions should cover it")

    def test_fallback_respects_intensity_cap(self):
        """Bug B: fallback must respect phase intensity cap.
        In deload phase (cap=low), technique_focus_gym (medium) must NOT be placed;
        easy_climbing_deload (low) CAN be placed."""
        pool = ["endurance_aerobic_gym", "route_endurance_gym", "deload_recovery"]
        plan = generate_phase_week(
            phase_id="deload",
            domain_weights={"endurance": 1.0},
            session_pool=pool,
            start_date="2026-03-02",
            availability=self._gym_no_routes_avail(),
            allowed_locations=["gym"],
            hard_cap_per_week=0,
            planning_prefs={"target_training_days_per_week": 3, "hard_day_cap_per_week": 0},
            gyms=self._gym_no_routes(),
            intensity_cap="low",
        )
        days = plan["weeks"][0]["days"]
        for d in days:
            for s in d["sessions"]:
                self.assertNotEqual(s["session_id"], "technique_focus_gym",
                                    "technique_focus_gym (medium) must not be placed in deload (cap=low)")


class TestPlannerV2B87GymNameLookup(unittest.TestCase):
    """B87 — gym lookup by name fallback.

    Gyms in user_state have no gym_id field (only 'name').
    The availability editor stores g.name as gym_id in slot data.
    So slot may have gym_id="Cocuqe" while gym dict is {name:"Cocuqe"}.
    _equipment_for_location must match by name when gym_id field is absent.
    """

    def _two_gyms(self):
        """Gym A (priority 1, gym_boulder only) + Cocuqe (priority 2, gym_routes only)."""
        return [
            {"gym_id": "gym_a", "name": "Gym A", "priority": 1, "equipment": ["gym_boulder", "pullup_bar"]},
            {"gym_id": "cocuqe", "name": "Cocuqe", "priority": 2, "equipment": ["gym_routes", "pullup_bar"]},
        ]

    def _cocuqe_avail(self):
        """Thu/Fri/Sat/Sun gym slots (gym_id='cocuqe'); Mon/Tue/Wed explicitly unavailable."""
        slot = {"available": True, "preferred_location": "gym", "gym_id": "cocuqe"}
        off = {"available": False, "preferred_location": "home", "gym_id": None}
        return {
            "mon": {"morning": off, "lunch": off, "evening": off},
            "tue": {"morning": off, "lunch": off, "evening": off},
            "wed": {"morning": off, "lunch": off, "evening": off},
            "thu": {"evening": slot},
            "fri": {"evening": slot},
            "sat": {"evening": slot},
            "sun": {"evening": slot},
        }

    def test_routes_placed_when_gym_referenced_by_name(self):
        """With two gyms (Gym A has gym_boulder prio-1; Cocuqe has gym_routes prio-2),
        slots referencing 'Cocuqe' by name must yield routes sessions placed."""
        pool = [
            "endurance_aerobic_gym", "route_endurance_gym",
            "technique_focus_gym", "prehab_maintenance", "flexibility_full",
        ]
        plan = generate_phase_week(
            phase_id="base",
            domain_weights={"endurance": 0.5, "technique": 0.3, "finger_strength": 0.2},
            session_pool=pool,
            start_date="2026-03-05",
            availability=self._cocuqe_avail(),
            allowed_locations=["gym"],
            hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
            gyms=self._two_gyms(),
        )
        days = plan["weeks"][0]["days"]
        routes_sessions = [
            s for d in days for s in d["sessions"]
            if s["session_id"] in {"endurance_aerobic_gym", "route_endurance_gym"}
        ]
        self.assertGreater(len(routes_sessions), 0,
                           "Routes sessions must be placed when slot explicitly references Cocuqe (gym_routes)")

    def test_session_entry_has_gym_name_when_referenced_by_name(self):
        """Session entries on Cocuqe days must carry gym_id='Cocuqe', not Gym A."""
        pool = [
            "endurance_aerobic_gym", "route_endurance_gym",
            "technique_focus_gym", "prehab_maintenance", "flexibility_full",
        ]
        plan = generate_phase_week(
            phase_id="base",
            domain_weights={"endurance": 0.5, "technique": 0.3, "finger_strength": 0.2},
            session_pool=pool,
            start_date="2026-03-05",
            availability=self._cocuqe_avail(),
            allowed_locations=["gym"],
            hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
            gyms=self._two_gyms(),
        )
        days = plan["weeks"][0]["days"]
        for d in days:
            for s in d["sessions"]:
                if s.get("location") == "gym":
                    self.assertEqual(s["gym_id"], "cocuqe",
                                     f"Session on Cocuqe day must have gym_id='cocuqe', got '{s['gym_id']}'")

    def test_gym_a_boulder_session_not_placed_on_cocuqe_day(self):
        """technique_focus_gym requires gym_boulder which Cocuqe lacks.
        It must NOT be placed even though Gym A (priority 1) has gym_boulder —
        because the slot explicitly targets Cocuqe."""
        pool = [
            "technique_focus_gym", "endurance_aerobic_gym", "prehab_maintenance",
        ]
        plan = generate_phase_week(
            phase_id="base",
            domain_weights={"technique": 0.5, "endurance": 0.3, "finger_strength": 0.2},
            session_pool=pool,
            start_date="2026-03-05",
            availability=self._cocuqe_avail(),
            allowed_locations=["gym"],
            hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
            gyms=self._two_gyms(),
        )
        days = plan["weeks"][0]["days"]
        for d in days:
            for s in d["sessions"]:
                self.assertNotEqual(
                    s["session_id"], "technique_focus_gym",
                    "technique_focus_gym (requires gym_boulder) must NOT be placed when slot targets Cocuqe (gym_routes only)",
                )


class TestPlannerV2MultiSlotDay(unittest.TestCase):
    """B121: planner must fill all available slots including multi-slot days."""

    def _multi_slot_availability(self):
        """Mon eve(home), Tue eve(gym), Wed eve(gym), Thu lunch(home)+eve(gym). Fri-Sun rest."""
        return {
            "mon": {"evening": {"available": True, "locations": ["home"]}},
            "tue": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
            "wed": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
            "thu": {
                "lunch": {"available": True, "locations": ["home"]},
                "evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"},
            },
        }

    def _make_multi_kwargs(self, target_days=6, **overrides):
        kw = dict(
            availability=self._multi_slot_availability(),
            planning_prefs={"target_training_days_per_week": target_days, "hard_day_cap_per_week": 3},
            home_equipment=["hangboard", "pullup_bar"],
        )
        kw.update(overrides)
        return _make_kwargs("base", **kw)

    def test_two_slots_both_filled_when_target_allows(self):
        """Day with 2 slots + target allows both → 2 sessions planned."""
        plan = generate_phase_week(**self._make_multi_kwargs(target_days=6))
        days = plan["weeks"][0]["days"]
        thu = days[3]  # Thursday (offset 3)
        self.assertEqual(len(thu["sessions"]), 2,
                         f"Thu should have 2 sessions but has {len(thu['sessions'])}: "
                         f"{[s['session_id'] for s in thu['sessions']]}")
        slots_used = {s["slot"] for s in thu["sessions"]}
        self.assertEqual(slots_used, {"lunch", "evening"},
                         "Thu should use both lunch and evening slots")

    def test_two_slots_target_allows_only_one(self):
        """Day with 2 slots, target=4 → no need for extra slots, 4 sessions across 4 days."""
        plan = generate_phase_week(**self._make_multi_kwargs(target_days=4))
        days = plan["weeks"][0]["days"]
        total = sum(len(d["sessions"]) for d in days)
        self.assertEqual(total, 4, f"Should have exactly 4 sessions, got {total}")
        thu = days[3]
        self.assertEqual(len(thu["sessions"]), 1)

    def test_all_slots_filled_target_still_higher(self):
        """All 5 slots filled, target=6 → graceful degradation (5 sessions)."""
        plan = generate_phase_week(**self._make_multi_kwargs(target_days=6))
        days = plan["weeks"][0]["days"]
        total = sum(len(d["sessions"]) for d in days)
        self.assertEqual(total, 5,
                         f"Should fill all 5 available slots, got {total}")

    def test_single_slot_per_day_no_regression(self):
        """Single slot per day → no behavior change (regression check)."""
        single_slot_avail = {
            "mon": {"evening": {"available": True, "locations": ["home"]}},
            "tue": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
            "wed": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
            "thu": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
        }
        plan = generate_phase_week(**self._make_multi_kwargs(
            target_days=4,
            availability=single_slot_avail,
        ))
        days = plan["weeks"][0]["days"]
        total = sum(len(d["sessions"]) for d in days)
        self.assertEqual(total, 4)
        for d in days:
            self.assertLessEqual(len(d["sessions"]), 1)

    def test_mixed_single_and_multi_slot_days(self):
        """Mix of single-slot and multi-slot days fills correctly."""
        avail = {
            "mon": {
                "morning": {"available": True, "locations": ["home"]},
                "evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"},
            },
            "tue": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
            "wed": {
                "lunch": {"available": True, "locations": ["home"]},
                "evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"},
            },
            "thu": {"evening": {"available": True, "locations": ["home"]}},
        }
        plan = generate_phase_week(**self._make_multi_kwargs(
            target_days=6,
            availability=avail,
        ))
        days = plan["weeks"][0]["days"]
        total = sum(len(d["sessions"]) for d in days)
        self.assertEqual(total, 6,
                         f"Should fill all 6 available slots, got {total}")

    def test_extra_slot_session_is_not_hard(self):
        """Sessions placed in extra slots (pass 2.2) must NOT be hard."""
        plan = generate_phase_week(**self._make_multi_kwargs(target_days=6))
        days = plan["weeks"][0]["days"]
        for d in days:
            if len(d["sessions"]) > 1:
                for s in d["sessions"]:
                    if "pass2.2" in str(s.get("explain", [])):
                        self.assertFalse(
                            s["tags"].get("hard", False),
                            f"Extra-slot session {s['session_id']} must not be hard",
                        )

    def test_extra_slot_different_from_first(self):
        """Extra slot session uses a different time slot than the first."""
        plan = generate_phase_week(**self._make_multi_kwargs(target_days=6))
        days = plan["weeks"][0]["days"]
        for d in days:
            if len(d["sessions"]) > 1:
                slots = [s["slot"] for s in d["sessions"]]
                self.assertEqual(len(slots), len(set(slots)),
                                 f"Duplicate slots on same day: {slots}")


# ---------------------------------------------------------------------------
# D150: Availability compliance tests
# ---------------------------------------------------------------------------

class TestD150AvailabilityCompliance(unittest.TestCase):
    """D150: Planner must respect availability grid as hard constraint."""

    def _make_kwargs(self, phase_id="base", **overrides):
        profile = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
                    "technique": 50, "endurance": 40}
        base_weights = _BASE_WEIGHTS[phase_id]
        domain_weights = _adjust_domain_weights(base_weights, profile)
        session_pool = _build_session_pool(phase_id)
        defaults = dict(
            phase_id=phase_id,
            domain_weights=domain_weights,
            session_pool=session_pool,
            start_date="2026-03-30",
            allowed_locations=["home", "gym"],
            hard_cap_per_week=3,
            default_gym_id="gym1",
            gyms=[{"gym_id": "gym1", "equipment": ["hangboard", "gym_boulder", "gym_routes", "pullup_bar"]}],
        )
        defaults.update(overrides)
        return defaults

    def test_unavailable_days_are_always_rest(self):
        """Days with no availability slot must always be Rest."""
        avail = {
            "mon": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "gym1"}},
            "tue": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "gym1"}},
            "wed": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "gym1"}},
            "thu": {"evening": {"available": True, "preferred_location": "home"}},
            "fri": {"evening": {"available": True, "preferred_location": "home"}},
            # sat and sun: absent → rest
        }
        plan = generate_phase_week(
            **self._make_kwargs(
                availability=avail,
                planning_prefs={"target_training_days_per_week": 5, "hard_day_cap_per_week": 3},
            )
        )
        days = plan["weeks"][0]["days"]
        sat = days[5]
        sun = days[6]
        self.assertEqual(sat["weekday"], "sat")
        self.assertEqual(sun["weekday"], "sun")
        self.assertEqual(len(sat["sessions"]), 0, "Saturday (no availability) must have no sessions")
        self.assertEqual(len(sun["sessions"]), 0, "Sunday (no availability) must have no sessions")

    def test_available_days_receive_sessions(self):
        """Days with availability should be eligible for session assignment."""
        avail = {
            "mon": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "gym1"}},
            "tue": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "gym1"}},
            "wed": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "gym1"}},
            "thu": {"evening": {"available": True, "preferred_location": "home"}},
            "fri": {"evening": {"available": True, "preferred_location": "home"}},
        }
        plan = generate_phase_week(
            **self._make_kwargs(
                availability=avail,
                planning_prefs={"target_training_days_per_week": 5, "hard_day_cap_per_week": 3},
                home_equipment=["hangboard"],
            )
        )
        days = plan["weeks"][0]["days"]
        days_with_sessions = [d for d in days[:5] if d["sessions"]]
        self.assertGreaterEqual(len(days_with_sessions), 3,
                                "At least 3 of the 5 available days should have sessions")

    def test_sessions_dont_overflow_to_unavailable_days(self):
        """If more sessions than available days, cap at available days."""
        avail = {
            "mon": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "gym1"}},
            "tue": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "gym1"}},
            # Only 2 available days, phase wants more sessions
        }
        plan = generate_phase_week(
            **self._make_kwargs(
                availability=avail,
                planning_prefs={"target_training_days_per_week": 5, "hard_day_cap_per_week": 3},
            )
        )
        days = plan["weeks"][0]["days"]
        for d in days:
            if d["weekday"] not in ("mon", "tue"):
                self.assertEqual(len(d["sessions"]), 0,
                                 f"{d['weekday']} has no availability but got sessions: "
                                 f"{[s['session_id'] for s in d['sessions']]}")

    def test_session_location_matches_availability(self):
        """Gym sessions only on gym-available days, home sessions on home days."""
        avail = {
            "mon": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "gym1"}},
            "thu": {"evening": {"available": True, "preferred_location": "home"}},
        }
        plan = generate_phase_week(
            **self._make_kwargs(
                availability=avail,
                planning_prefs={"target_training_days_per_week": 2, "hard_day_cap_per_week": 2},
                home_equipment=["hangboard"],
            )
        )
        days = plan["weeks"][0]["days"]
        thu = days[3]
        for s in thu["sessions"]:
            self.assertIn(s.get("location"), ("home", None),
                          f"Thursday is home-only but got location={s.get('location')}")

    def test_empty_dict_days_dont_steal_from_real_days(self):
        """D150-T9: Integration — empty dict days must not receive sessions
        while real available days are dropped by capping."""
        avail = {
            "mon": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "gym1"}},
            "tue": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "gym1"}},
            "wed": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "gym1"}},
            "thu": {"evening": {"available": True, "preferred_location": "home"}},
            "fri": {"evening": {"available": True, "preferred_location": "home"}},
            "sat": {},   # empty dict — frontend bug artifact
            "sun": {},   # empty dict — frontend bug artifact
        }
        plan = generate_phase_week(
            **self._make_kwargs(
                availability=avail,
                planning_prefs={"target_training_days_per_week": 5, "hard_day_cap_per_week": 3},
                home_equipment=["hangboard"],
            )
        )
        days = plan["weeks"][0]["days"]
        sat = days[5]
        sun = days[6]
        self.assertEqual(len(sat["sessions"]), 0,
                         f"Saturday (empty dict) must be rest, got: {[s['session_id'] for s in sat['sessions']]}")
        self.assertEqual(len(sun["sessions"]), 0,
                         f"Sunday (empty dict) must be rest, got: {[s['session_id'] for s in sun['sessions']]}")
        # Thu and Fri should NOT be dropped
        thu = days[3]
        fri = days[4]
        thu_fri_sessions = len(thu["sessions"]) + len(fri["sessions"])
        self.assertGreaterEqual(thu_fri_sessions, 1,
                                "Thu/Fri (real availability) should not be dropped in favor of empty-dict days")


class TestB157TemporarySkipBudget(unittest.TestCase):
    """B157: temporary skips (hard_gap, finger_gap) must NOT burn primary_uses budget.

    Root cause: the Pass 1 circular rotation exhausted its budget on
    day-specific constraint skips, preventing sessions from being placed
    on later days where the constraints were satisfied.
    """

    @staticmethod
    def _daniele_availability():
        """6 gym days + 1 home day — real-world S&P availability."""
        return {
            "mon": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "bkl"}},
            "tue": {"evening": {"available": True, "preferred_location": "home"}},
            "wed": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "cocque"}},
            "thu": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "cocque"}},
            "fri": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "work"}},
            "sat": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "cocque"}},
            "sun": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "cocque"}},
        }

    @staticmethod
    def _daniele_gyms():
        return [
            {"gym_id": "bkl", "name": "BKL", "equipment": ["gym_boulder", "spraywall", "hangboard", "campus_board", "pullup_bar"]},
            {"gym_id": "cocque", "name": "Cocque", "equipment": ["gym_boulder", "gym_routes", "hangboard", "campus_board", "pullup_bar"]},
            {"gym_id": "work", "name": "Work", "equipment": ["gym_boulder", "hangboard", "pullup_bar"]},
        ]

    def test_sp_6gym_produces_3_hard_sessions(self):
        """With 6 gym days and hard_cap=4, S&P must place ≥3 hard sessions."""
        from backend.engine.planner_v2 import _SESSION_META
        kwargs = _make_kwargs(
            "strength_power",
            availability=self._daniele_availability(),
            gyms=self._daniele_gyms(),
            default_gym_id="bkl",
            hard_cap_per_week=4,
            planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 4},
            home_equipment=["hangboard", "pullup_bar", "dumbbell", "band"],
        )
        plan = generate_phase_week(**kwargs)
        days = plan["weeks"][0]["days"]
        all_sessions = [s for d in days for s in d["sessions"]]
        hard = [s for s in all_sessions if _SESSION_META.get(s["session_id"], {}).get("hard")]
        hard_ids = [s["session_id"] for s in hard]
        self.assertGreaterEqual(len(hard), 3,
                                f"S&P with 6 gym days should have ≥3 hard sessions, got {len(hard)}: {hard_ids}")
        # strength_long must be among them — it was previously blocked by budget exhaustion
        self.assertIn("strength_long", hard_ids,
                       f"strength_long should be placed on a later day, got: {hard_ids}")

    def test_sp_6gym_strength_long_placed(self):
        """B162: strength_long must be placed somewhere in the week.
        Exact day may shift when route_endurance_gym is added to S&P pool."""
        from backend.engine.planner_v2 import _SESSION_META
        kwargs = _make_kwargs(
            "strength_power",
            availability=self._daniele_availability(),
            gyms=self._daniele_gyms(),
            default_gym_id="bkl",
            hard_cap_per_week=4,
            planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 4},
            home_equipment=["hangboard", "pullup_bar", "dumbbell", "band"],
        )
        plan = generate_phase_week(**kwargs)
        days = plan["weeks"][0]["days"]
        all_ids = [s["session_id"] for d in days for s in d["sessions"]]
        self.assertIn("strength_long", all_ids,
                       f"Expected strength_long placed in week, got: {all_ids}")

    def test_2_day_availability_permanent_skips_still_work(self):
        """With only 2 available days, hard_cap and max_per_week still limit correctly."""
        from backend.engine.planner_v2 import _SESSION_META
        avail = {
            "mon": {"evening": {"available": True, "locations": ["gym", "home"]}},
            "thu": {"evening": {"available": True, "locations": ["gym", "home"]}},
        }
        kwargs = _make_kwargs(
            "strength_power",
            availability=avail,
            hard_cap_per_week=2,
            planning_prefs={"target_training_days_per_week": 2, "hard_day_cap_per_week": 2},
        )
        plan = generate_phase_week(**kwargs)
        days = plan["weeks"][0]["days"]
        all_sessions = [s for d in days for s in d["sessions"]]
        hard = [s for s in all_sessions if _SESSION_META.get(s["session_id"], {}).get("hard")]
        self.assertLessEqual(len(hard), 2,
                              f"hard_cap=2 must be respected, got {len(hard)} hard sessions")
        # Each session should appear at most once (max_per_week=1 default)
        ids = [s["session_id"] for s in all_sessions]
        for sid in ids:
            max_pw = _SESSION_META.get(sid, {}).get("max_per_week", 1)
            self.assertLessEqual(ids.count(sid), max_pw,
                                  f"{sid} placed {ids.count(sid)} times, max_per_week={max_pw}")

    def test_hard_cap_2_permanent_skip_respected(self):
        """When hard_cap=2 and 2 hard sessions are placed, no more hard sessions appear."""
        from backend.engine.planner_v2 import _SESSION_META
        kwargs = _make_kwargs(
            "strength_power",
            hard_cap_per_week=2,
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 2},
        )
        plan = generate_phase_week(**kwargs)
        days = plan["weeks"][0]["days"]
        all_sessions = [s for d in days for s in d["sessions"]]
        hard = [s for s in all_sessions if _SESSION_META.get(s["session_id"], {}).get("hard")]
        self.assertLessEqual(len(hard), 2,
                              f"hard_cap=2 must be respected even with temporary skip fix, "
                              f"got {len(hard)}: {[s['session_id'] for s in hard]}")


class TestB160PerfLimitBoulder(unittest.TestCase):
    """B160: PERF phase must include limit_boulder_gym for ≥2 hard climbing."""

    def test_perf_has_2_hard_climbing_with_4_gym_days(self):
        from backend.engine.planner_v2 import _SESSION_META
        avail = {
            "mon": {"evening": {"available": True, "preferred_location": "gym"}},
            "wed": {"evening": {"available": True, "preferred_location": "gym"}},
            "fri": {"evening": {"available": True, "preferred_location": "gym"}},
            "sat": {"evening": {"available": True, "preferred_location": "gym"}},
        }
        kwargs = _make_kwargs(
            "performance",
            availability=avail,
            hard_cap_per_week=4,
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 4},
        )
        plan = generate_phase_week(**kwargs)
        days = plan["weeks"][0]["days"]
        all_sessions = [s for d in days for s in d["sessions"]]
        hard_climbing = [
            s for s in all_sessions
            if _SESSION_META.get(s["session_id"], {}).get("hard")
            and _SESSION_META.get(s["session_id"], {}).get("climbing")
        ]
        self.assertGreaterEqual(
            len(hard_climbing), 2,
            f"PERF with 4 gym days should have ≥2 hard climbing, got "
            f"{len(hard_climbing)}: {[s['session_id'] for s in hard_climbing]}",
        )

    def test_limit_boulder_in_perf_pool(self):
        from backend.engine.macrocycle_v1 import _SESSION_POOL, _SESSION_POOL_BOULDER
        self.assertIn("limit_boulder_gym", _SESSION_POOL["performance"])
        self.assertIn("limit_boulder_gym", _SESSION_POOL_BOULDER["performance"])


class TestB161CrossWeekGap(unittest.TestCase):
    """B161: cross-week hard_gap and finger_gap enforcement."""

    @staticmethod
    def _make_prev_plan(hard_on_sunday=False, finger_on_sunday=False,
                         hard_on_saturday=False):
        """Build a minimal prev_week_plan with sessions on specific days."""
        days = []
        for i in range(7):
            sessions = []
            if i == 6 and hard_on_sunday:
                sessions.append({"session_id": "power_contact_gym",
                                 "tags": {"hard": True, "finger": False}})
            if i == 6 and finger_on_sunday:
                sessions.append({"session_id": "strength_long",
                                 "tags": {"hard": True, "finger": True}})
            if i == 5 and hard_on_saturday:
                sessions.append({"session_id": "limit_boulder_gym",
                                 "tags": {"hard": True, "finger": False}})
            days.append({"sessions": sessions})
        return {"weeks": [{"days": days}]}

    def test_hard_sunday_blocks_hard_monday(self):
        """Hard on Sun (prev week) → no hard on Mon (current week)."""
        from backend.engine.planner_v2 import _SESSION_META
        prev = self._make_prev_plan(hard_on_sunday=True)
        plan = generate_phase_week(**_make_kwargs(
            "strength_power", prev_week_plan=prev,
        ))
        mon = plan["weeks"][0]["days"][0]
        mon_hard = [s for s in mon["sessions"]
                    if _SESSION_META.get(s["session_id"], {}).get("hard")]
        self.assertEqual(len(mon_hard), 0,
                          f"Mon should have no hard session (Sun was hard), got: "
                          f"{[s['session_id'] for s in mon_hard]}")

    def test_hard_saturday_allows_hard_monday(self):
        """Hard on Sat (prev week) → hard on Mon OK (gap=2 > 1)."""
        from backend.engine.planner_v2 import _SESSION_META
        prev = self._make_prev_plan(hard_on_saturday=True)
        plan = generate_phase_week(**_make_kwargs(
            "strength_power", prev_week_plan=prev,
        ))
        mon = plan["weeks"][0]["days"][0]
        mon_hard = [s for s in mon["sessions"]
                    if _SESSION_META.get(s["session_id"], {}).get("hard")]
        self.assertGreater(len(mon_hard), 0,
                            "Mon should have hard session (Sat gap=2 is sufficient)")

    def test_finger_sunday_blocks_finger_monday(self):
        """Finger on Sun (prev week) → no finger on Mon (current week)."""
        from backend.engine.planner_v2 import _SESSION_META
        prev = self._make_prev_plan(finger_on_sunday=True)
        plan = generate_phase_week(**_make_kwargs(
            "strength_power", prev_week_plan=prev,
        ))
        mon = plan["weeks"][0]["days"][0]
        mon_finger = [s for s in mon["sessions"]
                      if _SESSION_META.get(s["session_id"], {}).get("finger")]
        self.assertEqual(len(mon_finger), 0,
                          f"Mon should have no finger session (Sun was finger), got: "
                          f"{[s['session_id'] for s in mon_finger]}")

    def test_no_prev_week_no_constraint(self):
        """First week (no prev): Mon can have hard session."""
        from backend.engine.planner_v2 import _SESSION_META
        plan = generate_phase_week(**_make_kwargs(
            "strength_power", prev_week_plan=None,
        ))
        mon = plan["weeks"][0]["days"][0]
        # Should have at least some session on Mon (not blocked)
        self.assertGreater(len(mon["sessions"]), 0)

    def test_regression_existing_tests_pass(self):
        """Passing prev_week_plan=None should not change existing behavior."""
        plan = generate_phase_week(**_make_kwargs("base", prev_week_plan=None))
        self.assertEqual(plan["plan_version"], "planner.v2")


class TestB209MaxHang7sInjection(unittest.TestCase):
    def test_b209_new_user_test_week_schedules_7s(self):
        """B209: onboarding 'Do a test week first' must schedule test_max_hang_7s, not 5s."""
        full_avail = {wd: {"evening": {"available": True, "locations": ["gym", "home"]}}
                      for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
        plan = generate_phase_week(**_make_kwargs(
            "base",
            inject_tests=True,
            is_last_week_of_phase=True,
            availability=full_avail,
            hard_cap_per_week=5,
            planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 5},
        ))
        session_ids = {s["session_id"] for d in plan["weeks"][0]["days"] for s in d["sessions"]}
        self.assertIn("test_max_hang_7s", session_ids,
                      "B209: planner must schedule test_max_hang_7s (D85 design authority)")
        self.assertNotIn("test_max_hang_5s", session_ids,
                         "B209: legacy 5s session must NOT be scheduled by the planner")


class TestB210Freshness(unittest.TestCase):
    """B210: freshness check must not block new-user finger tests."""

    @staticmethod
    def _full_avail():
        return {wd: {"evening": {"available": True, "locations": ["gym", "home"]}}
                for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}

    def test_b210_finger_freshness_ignores_estimated_at(self):
        """Onboarding estimate must not feed recent_test_dates — planner schedules finger test."""
        # week.py (B210 Change 1) no longer passes estimated_at into recent_test_dates,
        # so a new user with only an onboarding estimate reaches the planner with no finger entry.
        plan = generate_phase_week(**_make_kwargs(
            "base",
            inject_tests=True,
            is_last_week_of_phase=True,
            availability=self._full_avail(),
            hard_cap_per_week=5,
            planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 5},
            recent_test_dates={},  # new user — no real test yet
        ))
        session_ids = {s["session_id"] for d in plan["weeks"][0]["days"] for s in d["sessions"]}
        self.assertIn("test_max_hang_7s", session_ids,
                      "B210: new user with only onboarding estimate must get finger test scheduled")

    def test_b210_inject_tests_bypasses_freshness_window(self):
        """inject_tests=True must bypass the 42-day freshness window (explicit user intent)."""
        seven_days_ago = (datetime.strptime("2026-03-02", "%Y-%m-%d").toordinal() - 7)
        recent_finger = datetime.fromordinal(seven_days_ago).strftime("%Y-%m-%d")
        plan = generate_phase_week(**_make_kwargs(
            "base",
            inject_tests=True,
            is_last_week_of_phase=True,
            availability=self._full_avail(),
            hard_cap_per_week=5,
            planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 5},
            recent_test_dates={"finger": recent_finger},  # within 42-day window
        ))
        session_ids = {s["session_id"] for d in plan["weeks"][0]["days"] for s in d["sessions"]}
        self.assertIn("test_max_hang_7s", session_ids,
                      "B210: inject_tests=True must override freshness window for finger test")


if __name__ == "__main__":
    unittest.main()
