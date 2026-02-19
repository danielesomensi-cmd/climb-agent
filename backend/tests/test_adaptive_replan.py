"""Tests for adaptive replanning after feedback (B25)."""

from __future__ import annotations

from copy import deepcopy

import pytest

from backend.engine.adaptive_replan import (
    _derive_session_difficulty,
    append_feedback_log,
    apply_adaptive_replan,
    check_adaptive_replan,
)


# ── Fixtures ──


def _make_plan(days):
    """Build a minimal valid plan with given days."""
    return {
        "weeks": [{"week_index": 1, "days": days}],
        "adaptations": [],
    }


def _make_day(date, sessions):
    """Build a minimal day dict."""
    return {"date": date, "weekday": "mon", "sessions": sessions}


def _make_session(
    session_id,
    hard=False,
    intensity="max",
    slot="evening",
    location="gym",
    gym_id="gym1",
    status=None,
):
    """Build a minimal session dict."""
    s = {
        "session_id": session_id,
        "slot": slot,
        "location": location,
        "gym_id": gym_id,
        "intensity": intensity,
        "tags": {"hard": hard, "finger": False},
    }
    if status:
        s["status"] = status
    return s


def _make_feedback(date, difficulty):
    """Build a minimal feedback log entry."""
    return {"date": date, "session_id": "test_session", "difficulty": difficulty}


def _make_log_entry(date, feedback_items=None):
    """Build a minimal log_entry dict with exercise feedback."""
    return {
        "date": date,
        "planned": [{"session_id": "test_session"}],
        "actual": {
            "exercise_feedback_v1": feedback_items or [],
        },
    }


# ── Tests for check_adaptive_replan ──


def test_no_action_on_ok_feedback():
    plan = _make_plan([
        _make_day("2026-01-06", [_make_session("strength_long", hard=True)]),
    ])
    history = [_make_feedback("2026-01-05", "ok")]
    result = check_adaptive_replan(plan, history, "2026-01-05")
    assert result["actions"] == []


def test_no_action_on_easy_feedback():
    plan = _make_plan([
        _make_day("2026-01-06", [_make_session("strength_long", hard=True)]),
    ])
    history = [_make_feedback("2026-01-05", "very_easy")]
    result = check_adaptive_replan(plan, history, "2026-01-05")
    assert result["actions"] == []


def test_single_very_hard_downgrades_next_hard():
    plan = _make_plan([
        _make_day("2026-01-05", [_make_session("complementary_conditioning", hard=False, intensity="medium")]),
        _make_day("2026-01-06", [_make_session("strength_long", hard=True)]),
        _make_day("2026-01-07", [_make_session("power_contact_gym", hard=True)]),
    ])
    history = [_make_feedback("2026-01-05", "very_hard")]
    result = check_adaptive_replan(plan, history, "2026-01-05")

    assert len(result["actions"]) == 1
    action = result["actions"][0]
    assert action["type"] == "downgrade_next_hard"
    assert action["target_date"] == "2026-01-06"
    assert action["replacement_session_id"] == "complementary_conditioning"
    assert action["original_session_id"] == "strength_long"


def test_single_fail_downgrades_next_hard():
    plan = _make_plan([
        _make_day("2026-01-06", [_make_session("strength_long", hard=True)]),
    ])
    history = [_make_feedback("2026-01-05", "fail")]
    result = check_adaptive_replan(plan, history, "2026-01-05")

    assert len(result["actions"]) == 1
    assert result["actions"][0]["type"] == "downgrade_next_hard"


def test_double_very_hard_inserts_recovery():
    plan = _make_plan([
        _make_day("2026-01-06", [_make_session("strength_long", hard=True)]),
        _make_day("2026-01-07", [_make_session("power_contact_gym", hard=True)]),
    ])
    history = [
        _make_feedback("2026-01-04", "very_hard"),
        _make_feedback("2026-01-05", "very_hard"),
    ]
    result = check_adaptive_replan(plan, history, "2026-01-05")

    assert len(result["actions"]) == 1
    action = result["actions"][0]
    assert action["type"] == "insert_recovery"
    assert action["target_date"] == "2026-01-06"
    assert action["replacement_session_id"] == "regeneration_easy"


def test_rule2_overrides_rule1():
    """When both rules apply, Rule 2 wins — only recovery action, no downgrade."""
    plan = _make_plan([
        _make_day("2026-01-06", [_make_session("strength_long", hard=True)]),
        _make_day("2026-01-07", [_make_session("power_contact_gym", hard=True)]),
    ])
    history = [
        _make_feedback("2026-01-03", "very_hard"),
        _make_feedback("2026-01-05", "very_hard"),
    ]
    result = check_adaptive_replan(plan, history, "2026-01-05")

    assert len(result["actions"]) == 1
    assert result["actions"][0]["type"] == "insert_recovery"


def test_no_touch_completed_sessions():
    """Sessions with status done or skipped are not modified."""
    plan = _make_plan([
        _make_day("2026-01-06", [
            _make_session("strength_long", hard=True, status="done"),
        ]),
        _make_day("2026-01-07", [
            _make_session("power_contact_gym", hard=True),
        ]),
    ])
    history = [_make_feedback("2026-01-05", "very_hard")]
    result = check_adaptive_replan(plan, history, "2026-01-05")

    assert len(result["actions"]) == 1
    assert result["actions"][0]["target_date"] == "2026-01-07"


def test_no_touch_current_day():
    """Only days with date > current_date are targeted."""
    plan = _make_plan([
        _make_day("2026-01-05", [_make_session("strength_long", hard=True)]),
        _make_day("2026-01-06", [_make_session("power_contact_gym", hard=True)]),
    ])
    history = [_make_feedback("2026-01-05", "very_hard")]
    result = check_adaptive_replan(plan, history, "2026-01-05")

    assert len(result["actions"]) == 1
    assert result["actions"][0]["target_date"] == "2026-01-06"


def test_deterministic():
    """Same inputs produce same output (call twice, compare)."""
    plan = _make_plan([
        _make_day("2026-01-06", [_make_session("strength_long", hard=True)]),
    ])
    history = [_make_feedback("2026-01-05", "very_hard")]

    r1 = check_adaptive_replan(plan, history, "2026-01-05")
    r2 = check_adaptive_replan(plan, history, "2026-01-05")
    assert r1 == r2


def test_empty_feedback_history():
    plan = _make_plan([
        _make_day("2026-01-06", [_make_session("strength_long", hard=True)]),
    ])
    result = check_adaptive_replan(plan, [], "2026-01-05")
    assert result["actions"] == []


# ── Tests for append_feedback_log ──


def test_feedback_log_trimmed():
    """After 10 appends, log has max 7 entries."""
    state: dict = {}
    exercises_by_id: dict = {}
    for i in range(10):
        log_entry = _make_log_entry(f"2026-01-{i + 1:02d}")
        append_feedback_log(state, log_entry, None, exercises_by_id)

    assert len(state["feedback_log"]) == 7
    # Most recent dates should be kept
    dates = [e["date"] for e in state["feedback_log"]]
    assert "2026-01-10" in dates
    assert "2026-01-04" in dates
    assert "2026-01-03" not in dates


# ── Tests for apply_adaptive_replan ──


def test_adaptive_replan_preserves_slot_location():
    """Replaced session keeps slot, location, gym_id from original."""
    plan = _make_plan([
        _make_day("2026-01-06", [
            _make_session("strength_long", hard=True, slot="morning", location="gym", gym_id="my_gym"),
        ]),
    ])
    actions = [{
        "type": "downgrade_next_hard",
        "target_date": "2026-01-06",
        "reason": "test",
        "original_session_id": "strength_long",
        "replacement_session_id": "complementary_conditioning",
    }]
    updated = apply_adaptive_replan(plan, actions)

    session = updated["weeks"][0]["days"][0]["sessions"][0]
    assert session["session_id"] == "complementary_conditioning"
    assert session["slot"] == "morning"
    assert session["location"] == "gym"
    assert session["gym_id"] == "my_gym"


def test_adaptations_logged():
    """plan['adaptations'] contains entry with type 'adaptive_replan'."""
    plan = _make_plan([
        _make_day("2026-01-06", [_make_session("strength_long", hard=True)]),
    ])
    actions = [{
        "type": "downgrade_next_hard",
        "target_date": "2026-01-06",
        "reason": "test",
        "original_session_id": "strength_long",
        "replacement_session_id": "complementary_conditioning",
    }]
    updated = apply_adaptive_replan(plan, actions)

    assert any(a["type"] == "adaptive_replan" for a in updated["adaptations"])


# ── Tests for _derive_session_difficulty (weighted average) ──


def test_derive_difficulty_weighted_average():
    """Warmup (fatigue_cost=1) very_hard + main exercises (fatigue_cost=9) easy → result easy."""
    exercises_by_id = {
        "finger_warmup_generic": {"id": "finger_warmup_generic", "fatigue_cost": 1},
        "max_hang_5s": {"id": "max_hang_5s", "fatigue_cost": 9},
    }
    log_entry = _make_log_entry("2026-01-05", [
        {"exercise_id": "finger_warmup_generic", "feedback_label": "very_hard"},
        {"exercise_id": "max_hang_5s", "feedback_label": "easy"},
    ])
    result = _derive_session_difficulty(log_entry, exercises_by_id)
    # Weighted: (5*1 + 2*9) / (1+9) = 23/10 = 2.3 → easy (≤2.5)
    assert result == "easy"


def test_derive_difficulty_heavy_exercise_dominates():
    """Main exercise (fatigue_cost=9) very_hard + warmup (fatigue_cost=1) easy → hard or very_hard."""
    exercises_by_id = {
        "finger_warmup_generic": {"id": "finger_warmup_generic", "fatigue_cost": 1},
        "max_hang_5s": {"id": "max_hang_5s", "fatigue_cost": 9},
    }
    log_entry = _make_log_entry("2026-01-05", [
        {"exercise_id": "finger_warmup_generic", "feedback_label": "easy"},
        {"exercise_id": "max_hang_5s", "feedback_label": "very_hard"},
    ])
    result = _derive_session_difficulty(log_entry, exercises_by_id)
    # Weighted: (2*1 + 5*9) / (1+9) = 47/10 = 4.7 → very_hard (>4.5)
    assert result in {"hard", "very_hard"}
