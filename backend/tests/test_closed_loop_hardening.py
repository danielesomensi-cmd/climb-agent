"""Closed-loop test hardening — covers crash paths, idempotency,
session classification, log building, and adaptation edge cases.

Origin: D-BE audit found closed_loop_v1 + adaptation/closed_loop under-tested.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from backend.engine.closed_loop_v1 import (
    STIMULUS_CATEGORIES,
    _session_categories,
    apply_day_result_to_user_state,
    build_log_entry,
    ensure_planning_defaults,
)
from backend.engine.adaptation.closed_loop import record_cluster_cooldown


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_state() -> dict:
    return ensure_planning_defaults({"schema_version": "1.4"})


def _resolved_day(
    *,
    date: str = "2026-02-10",
    sessions: list | None = None,
) -> dict:
    if sessions is None:
        sessions = [
            {"session_id": "strength_long", "intent": "strength", "tags": {"hard": True, "finger": True}},
        ]
    return {
        "date": date,
        "plan": {"plan_version": "planner.v2", "start_date": "2026-02-03"},
        "sessions": sessions,
    }


# ===================================================================
# PRIORITY 1 — Crash-path tests (empty / missing / invalid inputs)
# ===================================================================


class TestCrashPaths:
    """Ensure closed-loop functions never crash on degenerate input."""

    def test_apply_day_result_empty_sessions(self):
        """Empty sessions list → state updated, no crash, counters untouched."""
        state = _base_state()
        day = _resolved_day(sessions=[])
        result = apply_day_result_to_user_state(state, resolved_day=day, status="done")
        # Fatigue counters remain at 0 (no sessions to count)
        assert result["fatigue_proxy"]["done_sessions_total"] == 0
        assert result["fatigue_proxy"]["hard_sessions_total"] == 0
        assert result["fatigue_proxy"]["last_updated_date"] == "2026-02-10"

    def test_apply_day_result_none_sessions(self):
        """sessions=None in resolved_day → treated as empty, no crash."""
        state = _base_state()
        day = {"date": "2026-02-10", "sessions": None}
        result = apply_day_result_to_user_state(state, resolved_day=day, status="done")
        assert result["fatigue_proxy"]["done_sessions_total"] == 0

    def test_apply_day_result_session_missing_tags(self):
        """Session without tags key → no crash, classified as complementaries."""
        state = _base_state()
        session = {"session_id": "yoga_recovery", "intent": "recovery"}
        # No "tags" key at all
        day = _resolved_day(sessions=[session])
        result = apply_day_result_to_user_state(state, resolved_day=day, status="done")
        assert result["stimulus_recency"]["complementaries"]["done_count"] == 1

    def test_apply_day_result_session_none_tags(self):
        """Session with tags=None → no crash."""
        state = _base_state()
        session = {"session_id": "yoga_recovery", "intent": "recovery", "tags": None}
        day = _resolved_day(sessions=[session])
        result = apply_day_result_to_user_state(state, resolved_day=day, status="done")
        assert result["fatigue_proxy"]["done_sessions_total"] == 1

    def test_build_log_entry_invalid_status_raises(self):
        """build_log_entry with invalid status → ValueError."""
        day = _resolved_day()
        with pytest.raises(ValueError, match="status must be one of"):
            build_log_entry(resolved_day=day, status="cancelled")

    def test_build_log_entry_empty_sessions(self):
        """build_log_entry with zero sessions → valid log entry, no crash."""
        day = _resolved_day(sessions=[])
        entry = build_log_entry(resolved_day=day, status="done")
        assert entry["status"] == "done"
        assert entry["session_ids"] == []
        assert entry["summary"]["session_count"] == 0
        assert entry["location"] is None



# ===================================================================
# PRIORITY 2 — Idempotency
# ===================================================================


class TestIdempotency:
    """Applying the same result twice must not double-count."""

    def test_apply_same_done_twice_doubles_counters(self):
        """Calling apply_day_result twice with same day increments counters twice.

        This is expected behavior — the caller (API layer) is responsible for
        not calling it twice. We verify the function is NOT idempotent by design
        (it's an append operation), so the API layer must guard against double-tap.
        """
        state = _base_state()
        day = _resolved_day()
        state = apply_day_result_to_user_state(state, resolved_day=day, status="done")
        assert state["fatigue_proxy"]["done_sessions_total"] == 1

        state = apply_day_result_to_user_state(state, resolved_day=day, status="done")
        assert state["fatigue_proxy"]["done_sessions_total"] == 2
        # Document: double-tap protection must be in API layer, not here

    def test_done_then_skipped_same_day(self):
        """Mark done then mark skipped on same day → both counters increment."""
        state = _base_state()
        day = _resolved_day()
        state = apply_day_result_to_user_state(state, resolved_day=day, status="done")
        state = apply_day_result_to_user_state(state, resolved_day=day, status="skipped")
        assert state["fatigue_proxy"]["done_sessions_total"] == 1
        assert state["fatigue_proxy"]["skipped_sessions_total"] == 1
        cat = state["stimulus_recency"]["finger_strength"]
        assert cat["done_count"] == 1
        assert cat["skipped_count"] == 1



# ===================================================================
# PRIORITY 3 — Session categories + build_log_entry
# ===================================================================


class TestSessionCategories:
    """Verify _session_categories() classification logic."""

    def test_finger_session(self):
        cats = _session_categories({"session_id": "finger_strength_home", "intent": "strength", "tags": {"finger": True}})
        assert "finger_strength" in cats

    def test_power_session(self):
        cats = _session_categories({"session_id": "power_contact_gym", "intent": "power", "tags": {}})
        assert "boulder_power" in cats

    def test_endurance_session(self):
        cats = _session_categories({"session_id": "endurance_aerobic_gym", "intent": "aerobic_endurance", "tags": {}})
        assert "endurance" in cats

    def test_technique_is_complementaries(self):
        cats = _session_categories({"session_id": "technique_focus_gym", "intent": "technique", "tags": {}})
        assert "complementaries" in cats

    def test_recovery_is_complementaries(self):
        cats = _session_categories({"session_id": "yoga_recovery", "intent": "recovery", "tags": {}})
        assert "complementaries" in cats

    def test_unknown_session_defaults_to_complementaries(self):
        """Session that doesn't match any pattern → complementaries."""
        cats = _session_categories({"session_id": "something_custom", "intent": None, "tags": {}})
        assert cats == ["complementaries"]

    def test_multi_category_session(self):
        """Session matching both finger and complementaries (technique + finger)."""
        cats = _session_categories({"session_id": "finger_technique_mix", "intent": "technique", "tags": {"finger": True}})
        assert "finger_strength" in cats
        assert "complementaries" in cats

    def test_empty_session_id_defaults_to_complementaries(self):
        cats = _session_categories({"session_id": "", "intent": "", "tags": {}})
        assert cats == ["complementaries"]


class TestBuildLogEntry:
    """Verify build_log_entry() output structure."""

    def test_done_entry_structure(self):
        day = _resolved_day()
        entry = build_log_entry(resolved_day=day, status="done")
        assert entry["schema_version"] == "resolved_day_log_entry.v1"
        assert entry["log_version"] == "closed_loop.v1"
        assert entry["date"] == "2026-02-10"
        assert entry["status"] == "done"
        assert entry["session_ids"] == ["strength_long"]
        assert entry["summary"]["session_count"] == 1
        assert "finger_strength" in entry["summary"]["categories"]

    def test_skipped_entry(self):
        day = _resolved_day()
        entry = build_log_entry(resolved_day=day, status="skipped")
        assert entry["status"] == "skipped"

    def test_notes_and_outcomes(self):
        day = _resolved_day()
        outcomes = {"exercise_feedback_v1": [{"exercise_id": "max_hang_7s", "feedback_label": "ok"}]}
        entry = build_log_entry(resolved_day=day, status="done", notes="Felt great", outcomes=outcomes)
        assert entry["notes"] == "Felt great"
        assert entry["actual_feedback_v1"] == outcomes["exercise_feedback_v1"]

    def test_no_notes_no_outcomes(self):
        day = _resolved_day()
        entry = build_log_entry(resolved_day=day, status="done")
        assert entry["notes"] == ""
        assert entry["actual_feedback_v1"] == []
        assert entry["actual"] == {}


# ===================================================================
# PRIORITY 3b — ensure_planning_defaults
# ===================================================================


class TestEnsurePlanningDefaults:
    """Verify ensure_planning_defaults() initializes all required fields."""

    def test_all_stimulus_categories_present(self):
        state = ensure_planning_defaults({})
        for cat in STIMULUS_CATEGORIES:
            assert cat in state["stimulus_recency"]
            entry = state["stimulus_recency"][cat]
            assert entry["last_done_date"] is None
            assert entry["done_count"] == 0

    def test_fatigue_proxy_initialized(self):
        state = ensure_planning_defaults({})
        fp = state["fatigue_proxy"]
        assert fp["done_sessions_total"] == 0
        assert fp["skipped_sessions_total"] == 0
        assert fp["hard_sessions_total"] == 0
        assert fp["finger_sessions_total"] == 0
        assert fp["endurance_sessions_total"] == 0

    def test_existing_values_preserved(self):
        """Pre-existing values in state are NOT overwritten by defaults."""
        state = ensure_planning_defaults({
            "fatigue_proxy": {"done_sessions_total": 5},
            "stimulus_recency": {"finger_strength": {"last_done_date": "2026-01-01", "done_count": 3}},
        })
        assert state["fatigue_proxy"]["done_sessions_total"] == 5
        assert state["stimulus_recency"]["finger_strength"]["done_count"] == 3

    def test_schema_version_set(self):
        state = ensure_planning_defaults({})
        assert state["schema_version"] == "1.4"

    def test_does_not_mutate_input(self):
        """ensure_planning_defaults must deepcopy — original input untouched."""
        original = {"schema_version": "1.3"}
        result = ensure_planning_defaults(original)
        assert original["schema_version"] == "1.3"
        assert result["schema_version"] == "1.4"


# ===================================================================
# PRIORITY 4 — Per-cluster cooldown (A245 E-4: multiplier branch removed)
# ===================================================================


class TestClusterCooldown:
    """A245 E-4: only the cooldown branch survives — see closed_loop.py."""

    def test_cooldown_set_on_fail(self):
        exercises_by_id = {
            "weighted_pullup": {
                "id": "weighted_pullup",
                "domain": ["strength_general"],
                "recency_group": "pulling_weighted",
            },
        }
        state = {}
        outcome = {"difficulty": "fail", "date": "2026-02-10"}
        state = record_cluster_cooldown(
            state, "weighted_pullup", outcome,
            exercises_by_id=exercises_by_id, feedback_date="2026-02-10",
        )
        cooldowns = state.get("cooldowns", {}).get("per_cluster", {})
        assert len(cooldowns) > 0
        # Cooldown should be 2 days for fail
        cluster_vals = list(cooldowns.values())
        assert "2026-02-12" in cluster_vals[0]["until_date"]

    def test_no_cooldown_on_ok(self):
        exercises_by_id = {
            "weighted_pullup": {
                "id": "weighted_pullup",
                "domain": ["strength_general"],
                "recency_group": "pulling_weighted",
            },
        }
        state = {}
        outcome = {"difficulty": "ok", "date": "2026-02-10"}
        state = record_cluster_cooldown(
            state, "weighted_pullup", outcome,
            exercises_by_id=exercises_by_id, feedback_date="2026-02-10",
        )
        cooldowns = state.get("cooldowns", {}).get("per_cluster", {})
        assert len(cooldowns) == 0

