"""A-ACTIVATION-TIMING: regression tests for the onboarding start_date shift.

Covers:
- `this_monday()` / `next_monday()` / `strict_next_monday()` helpers every
  day of the week.
- `resolve_start_date()` for the 3 user choices.
- `is_week_one_empty()` fallback probe (degenerate + real cases).
- B95 past-day guard still holds after the shift: onboarding mid-week with
  `this_monday()` produces zero sessions scheduled before today.
- `from_phase` regen does NOT retroactively shift `start_date` (preserves
  the original macrocycle anchor — critical invariant).
"""

from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import date, datetime, timedelta

from backend.engine.macrocycle_v1 import generate_macrocycle
from backend.engine.planner_v2 import generate_phase_week
from backend.engine.start_date_utils import (
    is_week_one_empty,
    next_monday,
    resolve_start_date,
    strict_next_monday,
    this_monday,
)


# Fixed ISO week for deterministic assertions: Mon 2026-04-13 → Sun 2026-04-19
MON = date(2026, 4, 13)
TUE = date(2026, 4, 14)
WED = date(2026, 4, 15)
THU = date(2026, 4, 16)
FRI = date(2026, 4, 17)
SAT = date(2026, 4, 18)
SUN = date(2026, 4, 19)


def _minimal_state(availability: dict | None = None) -> dict:
    """Minimal state sufficient for generate_macrocycle + planner probe.

    home-only (no gyms) avoids gym_id wiring; availability defaults to
    Mon/Wed/Fri evenings, home. Override via arg for stress-scenario tests.
    """
    return {
        "goal": {
            "goal_type": "grade_push",
            "discipline": "lead",
            "target_grade": "7a",
            "current_grade": "6b+",
        },
        "assessment": {
            "profile": {
                "finger_strength": 50,
                "pulling_strength": 50,
                "power_endurance": 50,
                "technique": 50,
                "endurance": 50,
            }
        },
        "availability": availability or {
            day: {
                "morning": {"available": False, "preferred_location": "home"},
                "lunch": {"available": False, "preferred_location": "home"},
                "evening": {
                    "available": day in {"mon", "wed", "fri"},
                    "gym_id": None,
                    "preferred_location": "home",
                },
            }
            for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
        },
        "equipment": {"home": ["hangboard", "pullup_bar"], "gyms": []},
        "planning_prefs": {"hard_day_cap_per_week": 3},
        "trips": [],
    }


class TestMondayHelpers(unittest.TestCase):
    """this_monday / next_monday / strict_next_monday — all 7 days."""

    def test_this_monday_every_day(self):
        for d in (MON, TUE, WED, THU, FRI, SAT, SUN):
            with self.subTest(day=d.isoformat()):
                got = this_monday(d)
                got_date = datetime.strptime(got, "%Y-%m-%d").date()
                self.assertEqual(got_date.weekday(), 0)
                self.assertLessEqual(got_date, d)
                self.assertLessEqual((d - got_date).days, 6)

    def test_this_monday_on_monday_returns_same(self):
        self.assertEqual(this_monday(MON), MON.isoformat())

    def test_next_monday_on_monday_returns_same(self):
        # matches backend.api.deps.next_monday same-day semantics
        self.assertEqual(next_monday(MON), MON.isoformat())

    def test_next_monday_on_tuesday_returns_following_monday(self):
        self.assertEqual(next_monday(TUE), (MON + timedelta(days=7)).isoformat())

    def test_next_monday_on_sunday_returns_tomorrow(self):
        self.assertEqual(next_monday(SUN), (SUN + timedelta(days=1)).isoformat())

    def test_strict_next_monday_on_monday_returns_plus_seven(self):
        self.assertEqual(
            strict_next_monday(MON),
            (MON + timedelta(days=7)).isoformat(),
        )

    def test_strict_next_monday_every_day_is_future(self):
        for d in (MON, TUE, WED, THU, FRI, SAT, SUN):
            with self.subTest(day=d.isoformat()):
                got = strict_next_monday(d)
                got_date = datetime.strptime(got, "%Y-%m-%d").date()
                self.assertEqual(got_date.weekday(), 0)
                self.assertGreater(got_date, d)


class TestResolveStartDate(unittest.TestCase):
    """resolve_start_date for all three user choices."""

    def test_today_on_monday(self):
        self.assertEqual(resolve_start_date(MON, "today"), MON.isoformat())

    def test_today_on_wednesday(self):
        self.assertEqual(resolve_start_date(WED, "today"), MON.isoformat())

    def test_today_on_sunday(self):
        # Sun → Monday of current week (6 days back)
        self.assertEqual(resolve_start_date(SUN, "today"), MON.isoformat())

    def test_tomorrow_on_sunday_jumps_to_next_monday(self):
        # Sun+1 = Mon → this_monday of next week
        self.assertEqual(
            resolve_start_date(SUN, "tomorrow"),
            (MON + timedelta(days=7)).isoformat(),
        )

    def test_next_monday_from_monday_is_plus_seven(self):
        self.assertEqual(
            resolve_start_date(MON, "next_monday"),
            (MON + timedelta(days=7)).isoformat(),
        )

    def test_next_monday_from_friday(self):
        self.assertEqual(
            resolve_start_date(FRI, "next_monday"),
            (MON + timedelta(days=7)).isoformat(),
        )

    def test_unknown_choice_raises(self):
        with self.assertRaises(ValueError):
            resolve_start_date(MON, "whenever")


class TestIsWeekOneEmpty(unittest.TestCase):
    """is_week_one_empty probe — degenerate and real cases."""

    def test_empty_macrocycle_returns_true(self):
        state = _minimal_state()
        self.assertTrue(is_week_one_empty(state, {}, MON))

    def test_no_phases_returns_true(self):
        state = _minimal_state()
        self.assertTrue(is_week_one_empty(state, {"phases": []}, MON))

    def test_normal_state_returns_false(self):
        """Mon-onboarded user with Mon/Wed/Fri availability → Week 1 populated."""
        state = _minimal_state()
        mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, MON.isoformat(), 12,
        )
        self.assertFalse(is_week_one_empty(state, mc, MON))

    def test_stress_empty_avail_returns_true(self):
        """User with no availability at all → Week 1 truly empty."""
        avail = {
            day: {
                "morning": {"available": False, "preferred_location": "home"},
                "lunch": {"available": False, "preferred_location": "home"},
                "evening": {"available": False, "preferred_location": "home"},
            }
            for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
        }
        state = _minimal_state(availability=avail)
        mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, MON.isoformat(), 12,
        )
        self.assertTrue(is_week_one_empty(state, mc, MON))


class TestPastDayGuardPostShift(unittest.TestCase):
    """B95 guard: onboarding mid-week with this_monday() → zero past sessions."""

    def _probe_week_one(self, today: date, state: dict, mc: dict) -> list:
        phase1 = mc["phases"][0]
        equipment = state.get("equipment") or {}
        prefs = state.get("planning_prefs") or {}
        probe = generate_phase_week(
            phase_id=phase1["phase_id"],
            domain_weights=phase1.get("domain_weights") or {},
            session_pool=phase1.get("session_pool") or [],
            start_date=phase1.get("start_date") or mc["start_date"],
            availability=state.get("availability"),
            allowed_locations=["home", "gym"],
            hard_cap_per_week=prefs.get("hard_day_cap_per_week", 3),
            planning_prefs=prefs,
            default_gym_id=None,
            gyms=equipment.get("gyms") or [],
            intensity_cap=phase1.get("intensity_cap"),
            home_equipment=equipment.get("home") or [],
            today=today.isoformat(),
            inject_tests=False,
        )
        return probe["weeks"][0]["days"]

    def test_wednesday_onboarding_no_past_sessions(self):
        """User onboarding Wed with start_date=Mon → Mon/Tue days are empty."""
        state = _minimal_state()
        start = this_monday(WED)  # 2026-04-13
        mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, start, 12,
        )
        days = self._probe_week_one(WED, state, mc)
        # days[0] = Mon, days[1] = Tue — both must have zero sessions.
        self.assertEqual(len(days[0].get("sessions") or []), 0)
        self.assertEqual(len(days[1].get("sessions") or []), 0)

    def test_friday_onboarding_no_past_sessions(self):
        state = _minimal_state()
        start = this_monday(FRI)
        mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, start, 12,
        )
        days = self._probe_week_one(FRI, state, mc)
        # days[0..3] = Mon/Tue/Wed/Thu — all past → zero sessions.
        for i in range(4):
            self.assertEqual(
                len(days[i].get("sessions") or []),
                0,
                f"Day {i} (before Fri) must be empty post-shift",
            )


class TestFromPhaseDoesNotShift(unittest.TestCase):
    """Critical invariant: from_phase regen preserves original start_date."""

    def test_regen_from_phase_keeps_original_start(self):
        state = _minimal_state()
        # Onboarding a Wed → start_date = Mon of that week
        original_start = this_monday(WED)  # 2026-04-13 Mon
        mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, original_start, 12,
        )
        state["macrocycle"] = mc

        # Simulate an existing-user regen 3 weeks later (e.g. equipment change).
        # The router passes start=old_mc["start_date"], from_phase="current".
        new_mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, original_start, 12,
            from_phase="base",
        )
        self.assertEqual(
            new_mc["start_date"],
            original_start,
            "from_phase regen must NOT retroactively shift start_date",
        )


class TestFallbackStressScenarios(unittest.TestCase):
    """Threshold T=1 fallback: fires only when Week 1 would be exactly 0.

    Validated against the simulation report (docs/briefs/
    A-ACTIVATION-timing_simulation.md §stress). If the planner ever changes
    placement behaviour for these edge cases, these tests will flag it.
    """

    def _sun_22_mon_to_fri_avail(self) -> dict:
        """stress_0: Sun 22:00 onboarding + only Mon-Fri evening availability.
        With this_monday() and B95 guard, Week 1 = 0 sessions → fallback fires.
        """
        return {
            day: {
                "morning": {"available": False, "preferred_location": "home"},
                "lunch": {"available": False, "preferred_location": "home"},
                "evening": {
                    "available": day in {"mon", "tue", "wed", "thu", "fri"},
                    "gym_id": None,
                    "preferred_location": "home",
                },
            }
            for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
        }

    def test_stress_0_triggers_fallback(self):
        """Sun 22:00 + Mon-Fri avail → Week 1 empty → is_week_one_empty True."""
        state = _minimal_state(availability=self._sun_22_mon_to_fri_avail())
        start = this_monday(SUN)  # 2026-04-13 Mon
        mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, start, 12,
        )
        self.assertTrue(
            is_week_one_empty(state, mc, SUN),
            "Sun-late onboarding with Mon-Fri avail must trigger fallback",
        )

    def test_stress_3_does_not_trigger_fallback(self):
        """Thu onboarding + 5 days/wk availability → Week 1 = 3 sessions → no fallback."""
        avail = {
            day: {
                "morning": {"available": False, "preferred_location": "home"},
                "lunch": {"available": False, "preferred_location": "home"},
                "evening": {
                    "available": day in {"mon", "wed", "fri", "sat", "sun"},
                    "gym_id": None,
                    "preferred_location": "home",
                },
            }
            for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
        }
        state = _minimal_state(availability=avail)
        start = this_monday(THU)
        mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, start, 12,
        )
        self.assertFalse(
            is_week_one_empty(state, mc, THU),
            "Thu onboarding with 5-day avail must NOT trigger fallback (Week 1 has sessions)",
        )


if __name__ == "__main__":
    unittest.main()
