"""B322 — the home-location dead end that deleted a user's climbing week.

Found in production: a boulderer signed up with a fully equipped gym,
`home_enabled=false` and an empty home kit, then never touched the location
control in the availability step — which defaulted every slot to "home". The
planner treats `preferred_location` as binding, so every gym session was
dropped and the week came out as stretching, core and prehab. Zero climbing,
`hard_days_count=0`, `unmet_stimulus=['pulling']`. The user opened /today once
and never came back.

Three defects, covered here:
  1. `_pick_location` dropped a session when the preference could not host it,
     with no fallback — even when "home" was not a place the user could train.
  2. `equipment.home_enabled` was written by the wizard and read by nobody.
  3. `_validate_goal` compared a lead-converted target against a Font
     current_grade, so the goal sanity checks never ran for boulder users.

The binding half of the preference is a feature, not a bug (UI batch 1b): a
user who really does train at home on Tuesday must not be sent to the gym.
That promise is re-pinned here so the fallback can never grow into it.
"""

import unittest

from backend.engine.macrocycle_v1 import (
    _BASE_WEIGHTS,
    _adjust_domain_weights,
    _build_session_pool,
    _validate_goal,
)
from backend.engine.planner_v2 import allowed_locations_for, generate_phase_week

_CLIMBING_SESSION_MARKERS = ("boulder", "climb", "route", "technique", "power", "endurance")


def _profile():
    return {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
            "technique": 50, "endurance": 40}


def _make_kwargs(phase_id="base", **overrides):
    domain_weights = _adjust_domain_weights(_BASE_WEIGHTS[phase_id], _profile())
    defaults = dict(
        phase_id=phase_id,
        domain_weights=domain_weights,
        session_pool=_build_session_pool(phase_id, discipline="boulder"),
        start_date="2026-08-03",
        availability=None,
        allowed_locations=["home", "gym"],
        hard_cap_per_week=3,
        planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
        default_gym_id="blocx",
        gyms=[{"gym_id": "blocx", "equipment": [
            "gym_boulder", "spraywall", "board_kilter", "hangboard", "pullup_bar",
        ]}],
    )
    defaults.update(overrides)
    return defaults


def _avail_prefer(preferred, days=("tue", "wed", "thu", "fri")):
    avail = {}
    for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
        if wd in days:
            avail[wd] = {"evening": {"available": True, "locations": ["home", "gym"],
                                     "preferred_location": preferred}}
        else:
            avail[wd] = {"available": False}
    return avail


def _sessions(plan):
    return [s for day in plan["weeks"][0]["days"] for s in day["sessions"]]


class TestHomeDeadEndFallback(unittest.TestCase):
    """Defect 1: an unusable home preference must not delete the week."""

    def test_empty_home_kit_falls_back_to_gym(self):
        """The prod case: prefers home everywhere, owns nothing at home."""
        plan = generate_phase_week(**_make_kwargs(
            availability=_avail_prefer("home"), home_equipment=[],
        ))
        sessions = _sessions(plan)
        self.assertTrue(sessions, "no sessions placed at all")
        self.assertTrue(
            any(s["location"] == "gym" for s in sessions),
            "every session stayed at a home the user cannot train in",
        )

    def test_empty_home_kit_gets_actual_climbing(self):
        """Falling back is only worth anything if the climbing comes back."""
        plan = generate_phase_week(**_make_kwargs(
            availability=_avail_prefer("home"), home_equipment=[],
        ))
        climbing = [
            s for s in _sessions(plan)
            if any(m in s["session_id"] for m in _CLIMBING_SESSION_MARKERS)
        ]
        self.assertTrue(climbing, "week still contains no climbing session")

    def test_home_excluded_by_home_enabled_false(self):
        """home_enabled=false reaches the planner as allowed_locations=['gym']."""
        plan = generate_phase_week(**_make_kwargs(
            availability=_avail_prefer("home"),
            allowed_locations=["gym"],
            home_equipment=[],
        ))
        sessions = _sessions(plan)
        self.assertTrue(sessions, "no sessions placed at all")
        for s in sessions:
            self.assertEqual(s["location"], "gym", f"{s['session_id']} placed outside the gym")


class TestPreferenceStaysBinding(unittest.TestCase):
    """The other half: a real home preference is still honoured (UI batch 1b)."""

    def test_equipped_home_keeps_sessions_at_home(self):
        plan = generate_phase_week(**_make_kwargs(
            availability=_avail_prefer("home"),
            home_equipment=["hangboard", "pullup_bar", "dumbbell", "resistance_band"],
        ))
        for s in _sessions(plan):
            self.assertEqual(
                s["location"], "home",
                f"{s['session_id']} was moved to the gym despite an equipped home",
            )

    def test_unknown_home_kit_keeps_sessions_at_home(self):
        """home_equipment=None means 'unknown', not 'empty' — stay binding."""
        plan = generate_phase_week(**_make_kwargs(
            availability=_avail_prefer("home"), home_equipment=None,
        ))
        for s in _sessions(plan):
            self.assertEqual(s["location"], "home", f"{s['session_id']} moved to the gym")

    def test_mixed_preferences_each_day_respected(self):
        avail = {}
        for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
            if wd in ("mon", "wed"):
                avail[wd] = {"evening": {"available": True, "locations": ["home", "gym"],
                                         "preferred_location": "gym"}}
            elif wd in ("tue", "thu"):
                avail[wd] = {"evening": {"available": True, "locations": ["home", "gym"],
                                         "preferred_location": "home"}}
            else:
                avail[wd] = {"available": False}
        plan = generate_phase_week(**_make_kwargs(
            availability=avail, home_equipment=["hangboard", "pullup_bar", "dumbbell"],
        ))
        for day in plan["weeks"][0]["days"]:
            for s in day["sessions"]:
                expected = "gym" if day["weekday"] in ("mon", "wed") else "home"
                self.assertEqual(s["location"], expected,
                                 f"{day['weekday']}: expected {expected}, got {s['location']}")

    def test_outdoor_preference_never_reassigned(self):
        """An outdoor slot is an explicit intent to be on rock — never a default."""
        avail = _avail_prefer("outdoor", days=("tue",))
        avail["wed"] = {"evening": {"available": True, "locations": ["home", "gym"],
                                    "preferred_location": "gym"}}
        plan = generate_phase_week(**_make_kwargs(availability=avail, home_equipment=[]))
        for day in plan["weeks"][0]["days"]:
            if day["weekday"] == "tue":
                for s in day["sessions"]:
                    self.assertNotIn(s["location"], ("home", "gym"),
                                     "an outdoor slot was reassigned indoors")


class TestAllowedLocationsForEquipment(unittest.TestCase):
    """Defect 2: home_enabled was written by the wizard and read by nobody."""

    def test_home_disabled_with_gym_drops_home(self):
        self.assertEqual(
            allowed_locations_for({"home_enabled": False, "home": [], "gyms": [{"gym_id": "g"}]}),
            ["gym"],
        )

    def test_home_disabled_without_gym_keeps_home(self):
        """No gym to fall back on — dropping home would leave nowhere to train."""
        self.assertEqual(
            allowed_locations_for({"home_enabled": False, "home": [], "gyms": []}),
            ["home", "gym"],
        )

    def test_home_enabled_keeps_both(self):
        self.assertEqual(
            allowed_locations_for({"home_enabled": True, "home": ["dumbbell"], "gyms": [{"gym_id": "g"}]}),
            ["home", "gym"],
        )

    def test_missing_and_empty_equipment_default_to_both(self):
        self.assertEqual(allowed_locations_for({}), ["home", "gym"])
        self.assertEqual(allowed_locations_for(None), ["home", "gym"])


class TestBoulderGoalValidation(unittest.TestCase):
    """Defect 3: the goal sanity checks never ran for a boulder user."""

    def test_font_current_grade_is_not_unknown(self):
        """target_grade arrives lead-converted; current_grade stays in Font."""
        warnings = _validate_goal({
            "discipline": "boulder", "current_grade": "8A",
            "target_grade": "9a", "target_boulder_grade": "8C",
        })
        self.assertEqual(
            [w for w in warnings if "Unknown current_grade" in w], [],
            "Font current_grade still falls through to the unknown branch",
        )

    def test_regression_warning_now_fires_for_boulder(self):
        """8A → 7A is a regression and must be flagged, as it is for lead."""
        warnings = _validate_goal({
            "discipline": "boulder", "current_grade": "8A",
            "target_grade": "6c", "target_boulder_grade": "7A",
        })
        self.assertTrue(
            any("not harder" in w for w in warnings),
            f"no regression warning for a boulder goal that goes backwards: {warnings}",
        )

    def test_lead_goal_unchanged(self):
        self.assertEqual(_validate_goal({
            "discipline": "lead", "current_grade": "7a", "target_grade": "7c",
        }), [])

    def test_genuinely_unknown_grade_still_warns(self):
        warnings = _validate_goal({
            "discipline": "boulder", "current_grade": "banana", "target_grade": "8a",
        })
        self.assertTrue(any("Unknown current_grade" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
