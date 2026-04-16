from __future__ import annotations

from backend.engine.closed_loop_v1 import apply_day_result_to_user_state, ensure_planning_defaults


def test_log_update_user_state_counters():
    base = ensure_planning_defaults({"schema_version": "1.3"})
    resolved_day = {
        "date": "2026-01-05",
        "plan": {"plan_version": "planner.v1", "start_date": "2026-01-05"},
        "sessions": [
            {"session_id": "strength_long", "intent": "strength", "tags": {"hard": True, "finger": True}},
            {"session_id": "power_endurance_gym", "intent": "power_endurance", "tags": {"hard": True, "finger": False}},
        ],
    }

    done = apply_day_result_to_user_state(base, resolved_day=resolved_day, status="done")
    assert done["stimulus_recency"]["finger_strength"]["last_done_date"] == "2026-01-05"
    assert done["fatigue_proxy"]["done_sessions_total"] == 2
    assert done["fatigue_proxy"]["hard_sessions_total"] == 2

    skipped = apply_day_result_to_user_state(done, resolved_day=resolved_day, status="skipped")
    assert skipped["stimulus_recency"]["finger_strength"]["last_skipped_date"] == "2026-01-05"
    assert skipped["fatigue_proxy"]["skipped_sessions_total"] == 2


