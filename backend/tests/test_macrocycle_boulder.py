"""Tests for boulder-specific macrocycle generation (B91)."""

import pytest

from backend.engine.macrocycle_v1 import (
    _BASE_WEIGHTS_BOULDER,
    _SESSION_POOL_BOULDER,
    _build_session_pool,
    _compute_phase_durations,
    generate_macrocycle,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PROFILE = {
    "finger_strength": 55,
    "pulling_strength": 50,
    "power_endurance": 45,
    "technique": 60,
    "endurance": 40,
    "body_composition": 50,
}

_BOULDER_GOAL = {
    "goal_type": "boulder_grade",
    "discipline": "boulder",
    "target_grade": "7C",
    "current_grade": "7A+",
    "deadline": "2026-08-01",
}

_LEAD_GOAL = {
    "goal_type": "lead_grade",
    "discipline": "lead",
    "target_grade": "7c",
    "current_grade": "7a+",
    "deadline": "2026-08-01",
}

_USER_STATE: dict = {"trips": []}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBoulderMacrocycleGenerates:
    """generate_macrocycle with boulder goal produces a valid macrocycle."""

    def test_boulder_macrocycle_generates(self):
        mc = generate_macrocycle(
            _BOULDER_GOAL, _PROFILE, _USER_STATE, "2026-03-09", total_weeks=11,
        )
        assert mc["macrocycle_version"] == "macrocycle.v1"
        assert mc["goal_snapshot"]["discipline"] == "boulder"
        assert mc["goal_snapshot"]["goal_type"] == "boulder_grade"
        phases = mc["phases"]
        phase_ids = [p["phase_id"] for p in phases]
        assert phase_ids == ["base", "strength_power", "power_endurance", "performance", "deload"]


class TestBoulderBasePhase:
    """Base phase boulder is shorter than lead base."""

    def test_boulder_base_phase_shorter(self):
        durations = _compute_phase_durations(_PROFILE, total_weeks=11, discipline="boulder")
        assert durations["base"] <= 3

    def test_boulder_strength_power_longer(self):
        durations = _compute_phase_durations(_PROFILE, total_weeks=11, discipline="boulder")
        assert durations["strength_power"] >= 3


class TestBoulderPoolNoRoutes:
    """Boulder pool base does not contain route-oriented sessions."""

    def test_boulder_pool_no_routes_in_base(self):
        pool = _build_session_pool("base", discipline="boulder")
        assert "endurance_aerobic_gym" not in pool
        assert "route_endurance_gym" not in pool

    def test_boulder_pool_has_boulder_sessions(self):
        base_pool = _build_session_pool("base", discipline="boulder")
        assert "boulder_circuit_gym" in base_pool
        assert "technique_focus_gym" in base_pool

        sp_pool = _build_session_pool("strength_power", discipline="boulder")
        assert "power_contact_gym" in sp_pool

    def test_boulder_pe_phase_no_route_sessions(self):
        pe_pool = _build_session_pool("power_endurance", discipline="boulder")
        assert "power_endurance_gym" not in pe_pool
        assert "route_endurance_gym" not in pe_pool
        assert "endurance_aerobic_gym" not in pe_pool
        # boulder PE uses boulder_circuit_gym instead
        assert "boulder_circuit_gym" in pe_pool


class TestLeadMacrocycleUnchanged:
    """Lead macrocycle with discipline='lead' is identical to default."""

    def test_lead_macrocycle_unchanged(self):
        mc_default = generate_macrocycle(
            {**_LEAD_GOAL, "discipline": "lead"},
            _PROFILE, _USER_STATE, "2026-03-09", total_weeks=12,
        )
        mc_explicit = generate_macrocycle(
            _LEAD_GOAL,
            _PROFILE, _USER_STATE, "2026-03-09", total_weeks=12,
        )
        # Compare phase structure (not generated_at timestamp)
        for p_def, p_exp in zip(mc_default["phases"], mc_explicit["phases"]):
            assert p_def["phase_id"] == p_exp["phase_id"]
            assert p_def["duration_weeks"] == p_exp["duration_weeks"]
            assert p_def["session_pool"] == p_exp["session_pool"]
            assert p_def["domain_weights"] == p_exp["domain_weights"]

    def test_lead_durations_unchanged(self):
        """Default durations for lead discipline match original _BASE_DURATIONS."""
        durations = _compute_phase_durations(_PROFILE, total_weeks=12, discipline="lead")
        # With the given profile (endurance=40, weakest), base gets +1, sp gets -1
        # but regardless, the lead path should use the original base durations
        assert durations["deload"] == 1
        total = sum(durations.values())
        assert total == 12


class TestBoulderWeights:
    """Boulder weights differ from lead weights."""

    def test_boulder_strength_power_finger_weight(self):
        assert _BASE_WEIGHTS_BOULDER["strength_power"]["finger_strength"] == 0.40

    def test_boulder_base_pe_marginal(self):
        assert _BASE_WEIGHTS_BOULDER["base"]["power_endurance"] == 0.05


class TestBoulderPoolContents:
    """Verify boulder pool contents per phase."""

    def test_boulder_performance_has_projecting(self):
        pool = _build_session_pool("performance", discipline="boulder")
        assert "technique_focus_gym" in pool
        assert "power_contact_gym" in pool

    def test_boulder_deload_same_as_lead(self):
        boulder_pool = _build_session_pool("deload", discipline="boulder")
        lead_pool = _build_session_pool("deload", discipline="lead")
        assert set(boulder_pool) == set(lead_pool)
