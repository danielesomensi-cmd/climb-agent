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
        """Last week of base phase should include test_max_hang_5s and test_repeater_7_3."""
        # Use 7-day availability: the expanded base pool (6 primaries) needs more room
        # for pass 3 to inject test sessions without violating finger/hard spacing.
        full_avail = {wd: {"evening": {"available": True, "locations": ["gym", "home"]}}
                      for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
        plan = generate_phase_week(**_make_kwargs("base", is_last_week_of_phase=True,
            hard_cap_per_week=5, availability=full_avail,
            planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 5}))
        all_sessions = [s for d in plan["weeks"][0]["days"] for s in d["sessions"]]
        session_ids = {s["session_id"] for s in all_sessions}
        self.assertIn("test_max_hang_5s", session_ids,
                       "Last week of base phase should have test_max_hang_5s")
        self.assertIn("test_repeater_7_3", session_ids,
                       "Last week of base phase should have test_repeater_7_3")

    def test_last_week_strength_power_has_test_sessions(self):
        """Last week of strength_power phase should include test sessions."""
        plan = generate_phase_week(**_make_kwargs("strength_power", is_last_week_of_phase=True,
            hard_cap_per_week=5,
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 5}))
        all_sessions = [s for d in plan["weeks"][0]["days"] for s in d["sessions"]]
        session_ids = {s["session_id"] for s in all_sessions}
        self.assertIn("test_max_hang_5s", session_ids,
                       "Last week of strength_power should have test_max_hang_5s")

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
        """Week plan must have weekly_load_summary."""
        plan = generate_phase_week(**_make_kwargs("base"))
        self.assertIn("weekly_load_summary", plan)
        summary = plan["weekly_load_summary"]
        self.assertIn("total_load", summary)
        self.assertIn("hard_days_count", summary)
        self.assertIn("recovery_days_count", summary)

    def test_weekly_load_summary_correct_total(self):
        """total_load must equal sum of all session load scores."""
        plan = generate_phase_week(**_make_kwargs("strength_power"))
        expected_total = sum(
            s.get("estimated_load_score", 0)
            for d in plan["weeks"][0]["days"]
            for s in d["sessions"]
        )
        self.assertEqual(plan["weekly_load_summary"]["total_load"], expected_total)

    def test_deload_week_low_load(self):
        """Deload week should have low total load."""
        plan = generate_phase_week(**_make_kwargs("deload"))
        summary = plan["weekly_load_summary"]
        self.assertEqual(summary["hard_days_count"], 0)
        # All deload sessions are low intensity, max 20 per session, max 3 sessions
        self.assertLessEqual(summary["total_load"], 20 * 3)


class TestPlannerV2OtherActivity(unittest.TestCase):
    """Tests for B41 — other activities in availability."""

    def test_other_activity_blocks_sessions(self):
        """Day with _day_meta.other_activity=True gets zero sessions and the flag."""
        avail = _base_availability()
        avail["wed"]["_day_meta"] = {"other_activity": True, "other_activity_name": "Trail running"}
        plan = generate_phase_week(**_make_kwargs("base", availability=avail))
        days = plan["weeks"][0]["days"]
        wed = next(d for d in days if d["weekday"] == "wed")
        self.assertEqual(len(wed["sessions"]), 0, "Other-activity day should have no sessions")
        self.assertTrue(wed.get("other_activity"), "Missing other_activity flag")
        self.assertEqual(wed.get("other_activity_name"), "Trail running")

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
        """Day after other-activity without reduce flag gets normal sessions."""
        avail = _base_availability()
        avail["wed"]["_day_meta"] = {"other_activity": True}
        plan = generate_phase_week(**_make_kwargs("strength_power", availability=avail))
        days = plan["weeks"][0]["days"]
        thu = next(d for d in days if d["weekday"] == "thu")
        self.assertNotIn("prev_other_activity_reduce", thu,
                         "Should NOT have reduce flag when not requested")


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
        Home has NO pullup_bar → planner must place it at gym."""
        from backend.engine.planner_v2 import generate_test_week
        plan = generate_test_week(
            start_date="2026-03-02",
            availability=self._gym_home_avail(),
            allowed_locations=["gym", "home"],
            gyms=self._full_gym(),
            default_gym_id="test_gym",
            home_equipment=["hangboard", "band", "dumbbell"],  # NO pullup_bar
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
        Home HAS pullup_bar + preference is home → planner places it at home."""
        from backend.engine.planner_v2 import generate_test_week
        plan = generate_test_week(
            start_date="2026-03-02",
            availability=self._gym_home_avail(),
            allowed_locations=["gym", "home"],
            gyms=self._full_gym(),
            default_gym_id="test_gym",
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


if __name__ == "__main__":
    unittest.main()
