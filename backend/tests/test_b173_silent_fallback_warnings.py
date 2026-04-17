"""B173 — Silent fallback warning tests.

Verifies that gym_id misses and baseline mismatches produce logger.warning
instead of silently degrading output. Fallback behaviour is preserved.
"""
import logging

import pytest

from backend.engine.resolve_session import _pick_hangboard_baseline
from backend.engine.progression_v1 import _max_hang_suggested, _hangboard_suggested
from backend.engine.replanner_v1 import apply_day_override, apply_events, suggest_sessions


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

GYM_A = {"gym_id": "aaa111", "name": "Gym A", "priority": 1, "equipment": ["gym_boulder", "hangboard"]}
GYM_B = {"gym_id": "bbb222", "name": "Gym B", "priority": 2, "equipment": ["gym_routes"]}
GYMS = [GYM_A, GYM_B]

HB_BASELINE = {
    "edge_mm": 20,
    "grip": "half_crimp",
    "hang_seconds": 5,
    "max_total_load_kg": 90.0,
    "source": "test",
}


def _minimal_plan(phase_id="strength_power"):
    return {
        "profile_snapshot": {"phase_id": phase_id},
        "weeks": [{
            "week_num": 1,
            "days": [
                {
                    "date": "2026-03-30",
                    "sessions": [
                        {"session_id": "limit_boulder_gym", "slot": "morning", "location": "gym",
                         "gym_id": "aaa111", "phase_id": phase_id, "intensity": "high", "status": "planned"}
                    ]
                }
            ]
        }]
    }


# ---------------------------------------------------------------------------
# Test 1: resolve_session gym_id miss warns (via get_location_equipment)
# ---------------------------------------------------------------------------

def test_get_location_equipment_warns_on_unknown_gym_id(caplog):
    """If gym_id is provided but not found, should warn and fall back to first gym."""
    from backend.engine.resolve_session import get_location_equipment

    user_state = {
        # B206: location now comes from user_state.context first; session.context is legacy hint.
        "context": {"location": "gym", "gym_id": "UNKNOWN_ID"},
        "equipment": {
            "gyms": GYMS,
            "home": [],
        }
    }
    session = {
        "context": {"location": "gym", "gym_id": "UNKNOWN_ID"}
    }

    with caplog.at_level(logging.WARNING, logger="backend.engine.resolve_session"):
        location, equipment = get_location_equipment(user_state, session)

    assert any("unknown_id" in msg.lower() or "not found" in msg for msg in caplog.messages), (
        "Expected warning mentioning the unknown gym_id"
    )
    # Fallback behaviour preserved: returns equipment from first-by-priority gym
    assert "gym_boulder" in equipment or "gym_routes" in equipment, (
        "Should still return some equipment after fallback"
    )


# ---------------------------------------------------------------------------
# Test 2: apply_day_override with unknown gym_id warns
# ---------------------------------------------------------------------------

def test_apply_day_override_warns_on_unknown_gym_id(caplog):
    plan = _minimal_plan()
    with caplog.at_level(logging.WARNING, logger="backend.engine.replanner_v1"):
        updated = apply_day_override(
            plan,
            intent="strength",
            reference_date="2026-03-30",
            target_date="2026-03-30",
            location="gym",
            gym_id="GHOST_GYM",
            gyms=GYMS,
        )

    assert any("GHOST_GYM" in msg for msg in caplog.messages), (
        "Expected warning mentioning the unknown gym_id in apply_day_override"
    )
    # Override should still be applied (fallback behaviour preserved)
    day = updated["weeks"][0]["days"][0]
    assert any(s.get("session_id") for s in day.get("sessions", [])), (
        "Override should still produce a session"
    )


# ---------------------------------------------------------------------------
# Test 3: change_gym event with unknown gym_id warns
# ---------------------------------------------------------------------------

def test_change_gym_event_warns_on_unknown_gym_id(caplog):
    plan = _minimal_plan()
    events = [{"event_type": "change_gym", "date": "2026-03-30", "gym_id": "GHOST_GYM", "location": "gym"}]

    with caplog.at_level(logging.WARNING, logger="backend.engine.replanner_v1"):
        updated = apply_events(plan, events, gyms=GYMS)

    assert any("GHOST_GYM" in msg for msg in caplog.messages), (
        "Expected warning mentioning the unknown gym_id in change_gym event"
    )


# ---------------------------------------------------------------------------
# Test 4: suggest_sessions with missing profile_snapshot warns
# ---------------------------------------------------------------------------

def test_suggest_sessions_warns_on_missing_profile_snapshot(caplog):
    plan_no_snapshot = {"weeks": [{"week_num": 1, "days": []}]}

    with caplog.at_level(logging.WARNING, logger="backend.engine.replanner_v1"):
        results = suggest_sessions(plan_no_snapshot, "2026-03-30", "gym")

    assert any("profile_snapshot" in msg or "phase_id" in msg for msg in caplog.messages), (
        "Expected warning about missing profile_snapshot"
    )
    # Function should still return suggestions (fallback to base pool)
    assert isinstance(results, list), "suggest_sessions should return a list even without profile_snapshot"


# ---------------------------------------------------------------------------
# Test 5: _pick_hangboard_baseline warns on no match, returns baselines[0]
# ---------------------------------------------------------------------------

def test_pick_hangboard_baseline_warns_on_mismatch(caplog):
    user_state = {"baselines": {"hangboard": [HB_BASELINE]}}

    with caplog.at_level(logging.WARNING, logger="backend.engine.resolve_session"):
        result = _pick_hangboard_baseline(
            user_state,
            edge_mm=10,        # different edge — no match
            grip="full_crimp", # different grip
            hang_seconds=7,    # different duration
        )

    assert any("fallback" in msg.lower() for msg in caplog.messages), (
        "Expected warning about fallback in _pick_hangboard_baseline"
    )
    # Fallback: should return baselines[0]
    assert result == HB_BASELINE


def test_pick_hangboard_baseline_no_warn_on_match(caplog):
    """No warning when baseline matches exactly."""
    user_state = {"baselines": {"hangboard": [HB_BASELINE]}}

    with caplog.at_level(logging.WARNING, logger="backend.engine.resolve_session"):
        result = _pick_hangboard_baseline(
            user_state,
            edge_mm=20,
            grip="half_crimp",
            hang_seconds=5,
        )

    assert result == HB_BASELINE
    assert not any("fallback" in msg.lower() for msg in caplog.messages), (
        "Should not warn when baseline matches exactly"
    )


def test_pick_hangboard_baseline_returns_none_when_empty(caplog):
    """Returns None (no warning, no crash) when baselines list is empty."""
    user_state = {"baselines": {"hangboard": []}}

    with caplog.at_level(logging.WARNING, logger="backend.engine.resolve_session"):
        result = _pick_hangboard_baseline(user_state, edge_mm=20, grip="half_crimp", hang_seconds=5)

    assert result is None
    assert not caplog.messages, "No warning expected when baselines list is simply empty"


# ---------------------------------------------------------------------------
# Test 6: _max_hang_suggested warns when no baselines
# ---------------------------------------------------------------------------

def test_max_hang_suggested_warns_on_empty_baselines(caplog):
    user_state = {"weight_kg": 70, "baselines": {"hangboard": []}}
    prescription = {"sets": 5, "intensity_pct_of_total_load": 0.9}

    with caplog.at_level(logging.WARNING, logger="backend.engine.progression_v1"):
        result = _max_hang_suggested(user_state, prescription)

    assert any("fallback" in msg.lower() or "baseline" in msg.lower() for msg in caplog.messages), (
        "Expected warning about missing baselines in _max_hang_suggested"
    )
    # Should still return a valid dict using bodyweight
    assert "suggested_total_load_kg" in result


# ---------------------------------------------------------------------------
# Test 7: _hangboard_suggested warns when no baselines
# ---------------------------------------------------------------------------

def test_hangboard_suggested_warns_on_empty_baselines(caplog):
    user_state = {"weight_kg": 70, "baselines": {"hangboard": []}}
    prescription = {"sets": 6, "reps": 6, "rest_seconds": 180}

    with caplog.at_level(logging.WARNING, logger="backend.engine.progression_v1"):
        result = _hangboard_suggested(user_state, "repeater_7_3", prescription)

    assert any("fallback" in msg.lower() or "baseline" in msg.lower() for msg in caplog.messages), (
        "Expected warning about missing baselines in _hangboard_suggested"
    )
    assert isinstance(result, dict)
