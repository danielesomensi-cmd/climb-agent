"""Tests for P0 fixes — NEW-F2 (equipment), NEW-F5 (phase durations), NEW-F10 (pretrip start_date)."""

import json
import unittest
from pathlib import Path

from backend.engine.macrocycle_v1 import (
    _MIN_TOTAL_WEEKS,
    _compute_phase_durations,
    check_pretrip_deload,
    compute_pretrip_dates,
    generate_macrocycle,
)
from backend.engine.planner_v2 import generate_phase_week
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _build_session_pool, _adjust_domain_weights

REPO_ROOT = Path(__file__).resolve().parents[2]
EXERCISES_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"


def _make_profile(**overrides):
    base = {
        "finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
        "technique": 50, "endurance": 40, "body_composition": 65,
    }
    base.update(overrides)
    return base


def _make_planner_kwargs(phase_id="base", **overrides):
    profile = _make_profile()
    base_weights = _BASE_WEIGHTS[phase_id]
    domain_weights = _adjust_domain_weights(base_weights, profile)
    session_pool = _build_session_pool(phase_id)
    defaults = dict(
        phase_id=phase_id,
        domain_weights=domain_weights,
        session_pool=session_pool,
        start_date="2026-03-02",
        allowed_locations=["home", "gym"],
        hard_cap_per_week=3,
    )
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# NEW-F2: Equipment required on climbing exercises
# ---------------------------------------------------------------------------

class TestClimbingEquipment(unittest.TestCase):
    """Every gym-only climbing exercise must require a climbing surface."""

    def setUp(self):
        with open(EXERCISES_PATH) as f:
            data = json.load(f)
        self.exercises = data["exercises"]

    def _has_wall_requirement(self, e):
        """Check if an exercise declares any climbing surface requirement."""
        eq = e.get("equipment_required", [])
        eq_any = e.get("equipment_required_any", [])
        wall_tags = {"gym_boulder", "gym_routes", "spraywall", "board_kilter"}
        return bool(set(eq) & wall_tags) or bool(set(eq_any) & wall_tags)

    def test_gym_climbing_exercises_have_wall_requirement(self):
        """Exercises that require a climbing wall must declare it."""
        wall_exercise_ids = {
            "gym_limit_bouldering", "gym_power_endurance_4x4",
            "gym_arc_easy_volume", "gym_technique_boulder_drills",
            "arc_training", "continuity_climbing",
            "downclimbing_drill", "slow_climbing",
            "silent_feet_drill", "no_readjust_drill",
        }
        for e in self.exercises:
            if e["id"] in wall_exercise_ids:
                self.assertTrue(
                    self._has_wall_requirement(e),
                    f"{e['id']} is a wall climbing exercise but has no wall equipment requirement",
                )

    def test_no_gym_climbing_exercise_missing_wall(self):
        """Broad check: any gym-only exercise with climbing-related domain should require a wall."""
        climbing_domains = {"power", "technique_boulder", "technique_footwork",
                           "technique_lead", "aerobic_capacity", "power_endurance",
                           "anaerobic_capacity", "regeneration"}
        for e in self.exercises:
            locs = set(e.get("location_allowed", []))
            domains = set(e.get("domain", []))
            if locs == {"gym"} and domains & climbing_domains:
                # Skip exercises that have hangboard/campus/board as they're not wall-climbing
                if any(kw in e["id"] for kw in ("hang", "campus", "finger_", "dead_hang")):
                    continue
                if e.get("category") in ("prehab", "warmup_specific", "core"):
                    continue
                self.assertTrue(
                    self._has_wall_requirement(e),
                    f"{e['id']} is gym-only with climbing domain {domains} but no wall requirement",
                )


# ---------------------------------------------------------------------------
# NEW-F5: Phase durations — no negative, validate minimum
# ---------------------------------------------------------------------------

class TestPhaseDurationValidation(unittest.TestCase):
    """_compute_phase_durations must reject short macrocycles and never produce negatives."""

    def test_total_weeks_below_minimum_raises(self):
        profile = _make_profile()
        with self.assertRaises(ValueError) as ctx:
            _compute_phase_durations(profile, 6)
        self.assertIn("must be >= 9", str(ctx.exception))

    def test_total_weeks_8_raises(self):
        profile = _make_profile()
        with self.assertRaises(ValueError):
            _compute_phase_durations(profile, 8)

    def test_total_weeks_9_all_phases_valid(self):
        profile = _make_profile()
        durations = _compute_phase_durations(profile, 9)
        self.assertEqual(sum(durations.values()), 9)
        for phase_id in ("base", "strength_power", "power_endurance", "performance"):
            self.assertGreaterEqual(durations[phase_id], 1,
                                    f"Phase {phase_id} has {durations[phase_id]} weeks in 9w macrocycle")
        self.assertGreaterEqual(durations["deload"], 1)

    def test_total_weeks_12_normal_behavior(self):
        """Regression: standard 12-week macrocycle should work as before."""
        profile = _make_profile()
        durations = _compute_phase_durations(profile, 12)
        self.assertEqual(sum(durations.values()), 12)
        for phase_id in ("base", "strength_power", "power_endurance", "performance"):
            self.assertGreaterEqual(durations[phase_id], 2)

    def test_no_negative_durations_any_profile(self):
        """No phase should ever have negative duration, regardless of profile."""
        for total in range(9, 20):
            for pe_score in (10, 30, 50, 80):
                profile = _make_profile(power_endurance=pe_score)
                durations = _compute_phase_durations(profile, total)
                for phase_id, weeks in durations.items():
                    self.assertGreaterEqual(weeks, 0,
                        f"Phase {phase_id} is negative ({weeks}) for total_weeks={total}, pe={pe_score}")

    def test_generate_macrocycle_rejects_short(self):
        """generate_macrocycle should propagate the ValueError for total_weeks < 9."""
        profile = _make_profile()
        goal = {"goal_type": "lead_grade", "target_grade": "7c+", "current_grade": "7b"}
        with self.assertRaises(ValueError):
            generate_macrocycle(goal, profile, {"trips": []}, "2026-03-02", total_weeks=6)


# ---------------------------------------------------------------------------
# NEW-F10: Trip start_date included in pretrip window
# ---------------------------------------------------------------------------

class TestPretripIncludesStartDate(unittest.TestCase):
    """The pre-trip deload window must include the trip departure day itself."""

    def test_check_pretrip_deload_includes_trip_day(self):
        """check_pretrip_deload should fire on the trip start_date itself (days_until=0)."""
        trips = [{"name": "Arco", "start_date": "2026-03-10"}]
        result = check_pretrip_deload({}, trips, "2026-03-10")
        self.assertIsNotNone(result, "Should trigger on trip start_date itself")
        self.assertEqual(result["days_until_trip"], 0)

    def test_compute_pretrip_dates_includes_start_date(self):
        """compute_pretrip_dates should include the trip start_date in the list."""
        trips = [{"name": "Arco", "start_date": "2026-03-07"}]
        # Week Mon-Sun: 2026-03-02 to 2026-03-08
        dates = compute_pretrip_dates(trips, "2026-03-02", "2026-03-08")
        self.assertIn("2026-03-07", dates, "Trip start_date should be in pretrip_dates")
        # Also the days before within the week
        self.assertIn("2026-03-02", dates)
        self.assertIn("2026-03-06", dates)

    def test_trip_start_date_blocks_hard_session(self):
        """A hard session should NOT be placed on the trip start_date."""
        # Trip starts Saturday 2026-03-07 → that day should be blocked
        pretrip = ["2026-03-02", "2026-03-03", "2026-03-04",
                    "2026-03-05", "2026-03-06", "2026-03-07"]
        plan = generate_phase_week(**_make_planner_kwargs(
            "strength_power", pretrip_dates=pretrip))
        days = plan["weeks"][0]["days"]
        trip_day = next(d for d in days if d["date"] == "2026-03-07")
        for s in trip_day.get("sessions", []):
            self.assertFalse(s["tags"]["hard"],
                f"Hard session {s['session_id']} on trip start_date 2026-03-07")

    def test_compute_pretrip_dates_no_trips(self):
        """No trips → empty list."""
        dates = compute_pretrip_dates([], "2026-03-02", "2026-03-08")
        self.assertEqual(dates, [])

    def test_compute_pretrip_dates_trip_outside_week(self):
        """Trip that starts well after the week → empty list."""
        trips = [{"name": "Arco", "start_date": "2026-04-18"}]
        dates = compute_pretrip_dates(trips, "2026-03-02", "2026-03-08")
        self.assertEqual(dates, [])


if __name__ == "__main__":
    unittest.main()
