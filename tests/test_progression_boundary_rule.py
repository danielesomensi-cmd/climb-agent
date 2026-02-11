from __future__ import annotations

import copy

from catalog.engine.progression_v1 import apply_feedback


def _state() -> dict:
    return {
        "schema_version": "1.4",
        "bodyweight_kg": 77.0,
        "baselines": {"hangboard": [{"max_total_load_kg": 100.0}]},
        "tests": {"max_strength": [{"test_id": "max_hang_5s_total_load", "total_load_kg": 100.0, "date": "2026-01-01"}]},
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


def test_training_feedback_updates_working_only_not_official_tests():
    before = _state()
    log_entry = {
        "date": "2026-01-05",
        "planned": [{"session_id": "strength_long", "exercise_instances": [{"exercise_id": "max_hang_5s", "prescription": {"edge_mm": 20, "grip": "half_crimp", "load_method": "added_weight"}}]}],
        "actual": {
            "exercise_feedback_v1": [
                {
                    "exercise_id": "max_hang_5s",
                    "completed": True,
                    "feedback_label": "hard",
                    "used_external_load_kg": 12.0,
                    "used_total_load_kg": 89.0,
                    "edge_mm": 20,
                    "grip": "half_crimp",
                    "load_method": "added_weight",
                }
            ]
        },
    }

    after = apply_feedback(log_entry, copy.deepcopy(before))

    assert after["working_loads"]["entries"]
    assert after["baselines"] == before["baselines"]
    assert after["tests"] == before["tests"]
