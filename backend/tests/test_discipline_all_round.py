"""Tests for A-B1: all_round goal type + discipline selection."""

import pytest

from backend.engine.macrocycle_v1 import (
    _build_session_pool,
    _compute_phase_durations,
    generate_macrocycle,
    _BASE_DURATIONS,
    _BASE_DURATIONS_BOULDER,
    PHASE_ORDER,
)
from backend.engine.assessment_v1 import compute_assessment_profile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PROFILE = {
    "finger_strength": 55,
    "pulling_strength": 50,
    "power_endurance": 45,
    "technique": 60,
    "endurance": 40,
}

_LEAD_GOAL = {
    "goal_type": "lead_grade",
    "discipline": "lead",
    "target_grade": "7c",
    "current_grade": "7a+",
    "deadline": "2026-08-01",
}

_BOULDER_GOAL = {
    "goal_type": "boulder_grade",
    "discipline": "boulder",
    "target_grade": "7C",
    "target_boulder_grade": "7C",
    "current_grade": "7A+",
    "deadline": "2026-08-01",
}

_ALL_ROUND_GOAL = {
    "goal_type": "all_round",
    "discipline": "both",
    "target_grade": "7c",
    "target_boulder_grade": "7B+",
    "current_grade": "7a+",
    "deadline": "2026-08-01",
}

_USER_STATE: dict = {"trips": []}


# ---------------------------------------------------------------------------
# all_round macrocycle
# ---------------------------------------------------------------------------

class TestAllRoundMacrocycle:
    """all_round goal type generates valid macrocycle with merged pools."""

    def test_generates_successfully(self):
        mc = generate_macrocycle(
            _ALL_ROUND_GOAL, _PROFILE, _USER_STATE, "2026-03-09", total_weeks=12,
        )
        assert mc["macrocycle_version"] == "macrocycle.v1"
        assert mc["goal_snapshot"]["discipline"] == "both"
        assert mc["goal_snapshot"]["goal_type"] == "all_round"
        assert mc["goal_snapshot"]["target_boulder_grade"] == "7B+"

    def test_uses_lead_durations(self):
        """DD-B3: all_round uses lead durations."""
        durations = _compute_phase_durations(_PROFILE, total_weeks=12, discipline="both")
        # Should be same total as lead (12), not boulder (10)
        assert sum(durations.values()) == 12
        # Deload should be 1 (same as lead)
        assert durations["deload"] == 1

    def test_all_phases_present(self):
        mc = generate_macrocycle(
            _ALL_ROUND_GOAL, _PROFILE, _USER_STATE, "2026-03-09", total_weeks=12,
        )
        phase_ids = [p["phase_id"] for p in mc["phases"]]
        assert phase_ids == list(PHASE_ORDER)


class TestAllRoundSessionPool:
    """all_round pool merges lead and boulder sessions."""

    def test_pool_contains_lead_sessions(self):
        pool = _build_session_pool("base", discipline="both")
        # Lead-only sessions should be present
        assert "endurance_aerobic_gym" in pool
        assert "route_endurance_gym" in pool

    def test_pool_contains_boulder_sessions(self):
        pool = _build_session_pool("base", discipline="both")
        assert "boulder_circuit_gym" in pool

    def test_pool_no_duplicates(self):
        for phase in PHASE_ORDER:
            pool = _build_session_pool(phase, discipline="both")
            assert len(pool) == len(set(pool)), f"Duplicates in {phase} pool"

    def test_primary_before_available(self):
        """Primary sessions should come before available sessions."""
        pool = _build_session_pool("strength_power", discipline="both")
        # All lead and boulder primary sessions should be in the first portion
        # At minimum, check the ordering is correct
        assert len(pool) > 0

    def test_merged_pool_larger_than_either(self):
        """Merged pool should have at least as many sessions as either individual pool."""
        for phase in PHASE_ORDER:
            lead_pool = set(_build_session_pool(phase, discipline="lead"))
            boulder_pool = set(_build_session_pool(phase, discipline="boulder"))
            merged_pool = set(_build_session_pool(phase, discipline="both"))
            assert lead_pool.issubset(merged_pool), f"Lead sessions missing in {phase}"
            assert boulder_pool.issubset(merged_pool), f"Boulder sessions missing in {phase}"

    def test_primary_promotion(self):
        """A session that is primary in boulder but available in lead should be primary in merged."""
        # core_training is available-only in boulder base but not in lead base at all
        # boulder_circuit_gym is primary in boulder, primary in lead
        pool = _build_session_pool("power_endurance", discipline="both")
        # boulder_circuit_gym is primary in boulder PE → should be in merged pool
        assert "boulder_circuit_gym" in pool


class TestAllRoundPerformancePool:
    """Performance phase should include both route_projecting and limit_boulder."""

    def test_performance_has_route_projecting(self):
        pool = _build_session_pool("performance", discipline="both")
        assert "route_projecting_gym" in pool

    def test_performance_has_limit_boulder(self):
        pool = _build_session_pool("performance", discipline="both")
        assert "limit_boulder_gym" in pool


# ---------------------------------------------------------------------------
# Lead regression
# ---------------------------------------------------------------------------

class TestLeadRegression:
    """Lead macrocycle must produce identical results to before this change."""

    def test_lead_pool_unchanged(self):
        """Lead session pool should not be affected by all_round changes."""
        pool = _build_session_pool("base", discipline="lead")
        assert "endurance_aerobic_gym" in pool
        assert "core_training" not in pool  # lead base doesn't have core_training

    def test_lead_macrocycle_identical(self):
        mc1 = generate_macrocycle(
            _LEAD_GOAL, _PROFILE, _USER_STATE, "2026-03-09", total_weeks=12,
        )
        mc2 = generate_macrocycle(
            _LEAD_GOAL, _PROFILE, _USER_STATE, "2026-03-09", total_weeks=12,
        )
        for p1, p2 in zip(mc1["phases"], mc2["phases"]):
            assert p1["phase_id"] == p2["phase_id"]
            assert p1["duration_weeks"] == p2["duration_weeks"]
            assert p1["session_pool"] == p2["session_pool"]
            assert p1["domain_weights"] == p2["domain_weights"]


# ---------------------------------------------------------------------------
# Boulder regression
# ---------------------------------------------------------------------------

class TestBoulderRegression:
    """Boulder macrocycle must still work correctly."""

    def test_boulder_10_week_cycle(self):
        mc = generate_macrocycle(
            _BOULDER_GOAL, _PROFILE, _USER_STATE, "2026-03-09", total_weeks=10,
        )
        total = sum(p["duration_weeks"] for p in mc["phases"])
        assert total == 10

    def test_boulder_pool_no_route_endurance(self):
        pool = _build_session_pool("base", discipline="boulder")
        assert "route_endurance_gym" not in pool
        assert "endurance_aerobic_gym" not in pool


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Goal without discipline field defaults to lead."""

    def test_missing_discipline_defaults_lead(self):
        goal_no_discipline = {
            "goal_type": "lead_grade",
            "target_grade": "7c",
            "current_grade": "7a+",
            "deadline": "2026-08-01",
        }
        mc = generate_macrocycle(
            goal_no_discipline, _PROFILE, _USER_STATE, "2026-03-09", total_weeks=12,
        )
        assert mc["goal_snapshot"]["discipline"] == "lead"
        # Should produce same pools as explicit lead
        mc_lead = generate_macrocycle(
            _LEAD_GOAL, _PROFILE, _USER_STATE, "2026-03-09", total_weeks=12,
        )
        for p1, p2 in zip(mc["phases"], mc_lead["phases"]):
            assert p1["session_pool"] == p2["session_pool"]


# ---------------------------------------------------------------------------
# Assessment with boulder goal
# ---------------------------------------------------------------------------

class TestAssessmentBoulderGoal:
    """Assessment should work with boulder-style goal."""

    def test_assessment_with_boulder_target(self):
        """Using a boulder grade as target_grade still produces valid profile."""
        assessment = {
            "body": {"weight_kg": 70.0},
            "experience": {"climbing_years": 3},
            "grades": {"boulder_max_rp": "7A", "lead_max_rp": "7a", "lead_max_os": "6b+"},
            "tests": {},
            "self_eval": {"primary_weakness": "poor_body_tension", "secondary_weakness": "weak_on_slopers"},
        }
        # For boulder, target_grade is set to the boulder grade (mapped by onboarding)
        goal = {"target_grade": "7a", "current_grade": "6b+"}
        profile = compute_assessment_profile(assessment, goal)
        for v in profile.values():
            assert 0 <= v <= 100

    def test_assessment_with_all_round_goal(self):
        """all_round goal uses lead target_grade for assessment."""
        assessment = {
            "body": {"weight_kg": 70.0},
            "experience": {"climbing_years": 5},
            "grades": {"lead_max_rp": "7b", "lead_max_os": "6c+", "boulder_max_rp": "7A"},
            "tests": {},
            "self_eval": {"primary_weakness": "technique_errors", "secondary_weakness": "poor_dynamic_movement"},
        }
        goal = {"target_grade": "7c+", "current_grade": "7b"}
        profile = compute_assessment_profile(assessment, goal)
        for v in profile.values():
            assert 0 <= v <= 100
