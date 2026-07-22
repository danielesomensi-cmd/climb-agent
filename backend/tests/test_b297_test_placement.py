"""B297 (D211-F9) — test placement no longer loses tests silently.

Pass 3 design after B297:
- pass 1 (historical, untouched): tests replace an existing session;
- pass 2 (new): a REQUIRED test that pass 1 could not place may occupy an
  empty available day (volume +1 by design); optional tests stay replace-only;
- every test that remains unplaced lands in skipped_tests with
  reason="no_placement_slot" instead of vanishing.
"""

import unittest

from backend.engine.planner_v2 import generate_phase_week
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _build_session_pool, _adjust_domain_weights

_PROFILE = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
            "technique": 50, "endurance": 40}

_GYM = {"gym_id": "blocx", "equipment": ["spraywall", "board_kilter", "hangboard",
                                         "gym_boulder", "gym_routes", "dumbbell", "pullup_bar"]}


def _avail(days):
    return {wd: {"evening": {"available": True, "locations": ["gym", "home"]}}
            for wd in days}


def _kwargs(phase_id="strength_power", *, days, target_days, **overrides):
    domain_weights = _adjust_domain_weights(_BASE_WEIGHTS[phase_id], _PROFILE)
    defaults = dict(
        phase_id=phase_id,
        domain_weights=domain_weights,
        session_pool=_build_session_pool(phase_id),
        start_date="2026-03-02",
        availability=_avail(days),
        allowed_locations=["home", "gym"],
        hard_cap_per_week=3,
        planning_prefs={"target_training_days_per_week": target_days, "hard_day_cap_per_week": 3},
        default_gym_id="blocx",
        gyms=[_GYM],
        is_last_week_of_phase=True,
        recent_test_dates=None,
    )
    defaults.update(overrides)
    return defaults


def _sessions(plan):
    return [s for d in plan["weeks"][0]["days"] for s in d["sessions"]]


def _session_ids(plan):
    return {s["session_id"] for s in _sessions(plan)}


def _skipped(plan):
    return plan.get("skipped_tests", [])


def _placement_skips(plan):
    return [e for e in _skipped(plan) if e.get("reason") == "no_placement_slot"]


class TestB297EmptyDayPlacement(unittest.TestCase):
    def test_required_test_uses_empty_available_day(self):
        """1 training day, full availability: pass 1 can serve one test by
        replacement; the second REQUIRED test must land on an empty day."""
        plan = generate_phase_week(**_kwargs(
            days=("mon", "tue", "wed", "thu", "fri", "sat", "sun"), target_days=1))
        sids = _session_ids(plan)
        self.assertIn("test_max_hang_7s", sids)
        self.assertIn("test_repeater_7_3", sids,
                      "required repeater must be placed on an empty available day (pass 2)")
        empty_day_entries = [s for s in _sessions(plan)
                             if "pass3:test_session_empty_day" in (s.get("explain") or [])]
        self.assertTrue(empty_day_entries,
                        "at least one test must carry the pass-2 provenance label")
        # A required test placed by pass 2 must never be lost AND reported.
        required_skipped = [e for e in _placement_skips(plan) if e.get("required")]
        self.assertEqual(required_skipped, [])

    def test_optional_test_stays_replace_only(self):
        """The pulling test (required=False) must NOT be added on an empty day:
        with a single replaceable session it goes to skipped_tests instead."""
        plan = generate_phase_week(**_kwargs(
            days=("mon", "tue", "wed", "thu", "fri", "sat", "sun"), target_days=1))
        skips = _placement_skips(plan)
        pulling = [e for e in skips if e.get("axis") == "pulling"]
        self.assertTrue(pulling, f"pulling test must be reported unplaced, got {skips}")
        self.assertFalse(pulling[0]["required"])
        optional_on_empty = [s for s in _sessions(plan)
                             if "pass3:test_session_empty_day" in (s.get("explain") or [])
                             and "pullup" in s["session_id"]]
        self.assertEqual(optional_on_empty, [])

    def test_unplaced_required_recorded_when_no_available_day(self):
        """Availability = 1 day only: the second required test has nowhere to
        go — it must be recorded, not silently dropped (the original F9 bug)."""
        plan = generate_phase_week(**_kwargs(days=("mon",), target_days=1))
        skips = _placement_skips(plan)
        self.assertTrue(any(e.get("required") for e in skips),
                        f"a required test must be reported unplaced, got {_skipped(plan)}")
        for e in skips:
            self.assertEqual(e["reason"], "no_placement_slot")
            self.assertIn("test_id", e)
            self.assertIn("axis", e)

    def test_empty_day_placement_respects_finger_spacing(self):
        """Two adjacent available days: after the finger test takes one, the
        adjacent empty day violates the 48h finger gap — the second finger
        test must be skipped+reported, not placed."""
        plan = generate_phase_week(**_kwargs(days=("mon", "tue"), target_days=1))
        sessions = _sessions(plan)
        finger_days = [d["date"] for d in plan["weeks"][0]["days"]
                       if any(s.get("tags", {}).get("finger") for s in d["sessions"])]
        # Never two finger days on adjacent dates
        self.assertLessEqual(len(finger_days), 1,
                             f"adjacent finger tests violate the 48h gap: {finger_days}")
        self.assertTrue(_placement_skips(plan),
                        "the test that could not respect spacing must be reported")

    def test_pass2_respects_hard_cap(self):
        """hard_cap 1 with a hard session already planned: pass 2 must not
        push a hard test onto an empty day above the cap."""
        plan = generate_phase_week(**_kwargs(
            days=("mon", "tue", "wed", "thu", "fri", "sat", "sun"),
            target_days=1, hard_cap_per_week=1,
            planning_prefs={"target_training_days_per_week": 1, "hard_day_cap_per_week": 1}))
        hard_days = sum(
            1 for d in plan["weeks"][0]["days"]
            if any(s.get("tags", {}).get("hard") for s in d["sessions"])
        )
        self.assertLessEqual(hard_days, 1, "pass 2 must respect the weekly hard cap")

    def test_deterministic(self):
        kwargs = _kwargs(days=("mon", "tue", "wed", "thu", "fri", "sat", "sun"), target_days=1)
        plan1 = generate_phase_week(**kwargs)
        plan2 = generate_phase_week(**kwargs)
        plan1.pop("generated_at", None)
        plan2.pop("generated_at", None)
        self.assertEqual(plan1, plan2)

    def test_replacement_weeks_have_no_placement_skips_for_required(self):
        """Regression: a week with enough replaceable sessions keeps the
        historical replace-only behaviour — no pass-2 entries, no required
        test in skipped_tests."""
        plan = generate_phase_week(**_kwargs(
            days=("mon", "tue", "wed", "thu", "fri", "sat", "sun"), target_days=4,
            hard_cap_per_week=5,
            planning_prefs={"target_training_days_per_week": 7, "hard_day_cap_per_week": 5}))
        sids = _session_ids(plan)
        self.assertIn("test_max_hang_7s", sids)
        self.assertIn("test_repeater_7_3", sids)
        required_skipped = [e for e in _placement_skips(plan) if e.get("required")]
        self.assertEqual(required_skipped, [])


if __name__ == "__main__":
    unittest.main()
