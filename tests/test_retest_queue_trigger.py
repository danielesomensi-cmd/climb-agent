from __future__ import annotations

from catalog.engine.progression_v1 import apply_feedback


def _state() -> dict:
    return {
        "schema_version": "1.4",
        "bodyweight_kg": 77.0,
        "working_loads": {
            "entries": [],
            "rules": {
                "adjustment_policy": {
                    "very_easy": {"pct_range": [0.1, 0.2]},
                    "easy": {"pct_range": [0.05, 0.1]},
                    "ok": {"pct_range": [0.0, 0.05]},
                    "hard": {"pct_range": [-0.05, 0.0]},
                    "very_hard": {"pct_range": [-0.15, -0.05]},
                }
            },
        },
    }


def _log(date_value: str, label: str) -> dict:
    return {
        "date": date_value,
        "planned": [{"session_id": "strength_long", "exercise_instances": [{"exercise_id": "max_hang_5s", "prescription": {"edge_mm": 20, "grip": "half_crimp", "load_method": "added_weight"}}]}],
        "actual": {
            "exercise_feedback_v1": [
                {
                    "exercise_id": "max_hang_5s",
                    "completed": True,
                    "feedback_label": label,
                    "used_total_load_kg": 90.0,
                    "edge_mm": 20,
                    "grip": "half_crimp",
                    "load_method": "added_weight",
                }
            ]
        },
    }


def test_two_hard_feedback_enqueue_retest_date_plus_7():
    state = _state()
    after_1 = apply_feedback(_log("2026-01-05", "hard"), state)
    assert after_1["test_queue"] == []

    after_2 = apply_feedback(_log("2026-01-06", "very_hard"), after_1)
    assert after_2["test_queue"][0]["test_id"] == "max_hang_5s_total_load"
    assert after_2["test_queue"][0]["recommended_by_date"] == "2026-01-13"
    assert after_2["test_queue"][0]["created_at"] == "2026-01-06"
