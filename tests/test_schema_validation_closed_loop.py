from __future__ import annotations

import json
from pathlib import Path

from scripts.schema_registry import SchemaRegistry, validate_instance


def test_closed_loop_log_schema_validation(tmp_path: Path):
    schema_registry = SchemaRegistry.from_dir("data/schemas")

    payload = {
        "schema_version": "resolved_day_log_entry.v1",
        "log_version": "closed_loop.v1",
        "date": "2026-01-05",
        "status": "done",
        "session_ids": ["strength_long"],
        "summary": {
            "session_count": 1,
            "status": "done",
            "categories": ["finger_strength"],
            "session_ids": ["strength_long"],
        },
        "actual": {
            "exercise_feedback_v1": [
                {
                    "exercise_id": "max_hang_5s",
                    "feedback_label": "ok",
                    "completed": True,
                    "used_total_load_kg": 90.0,
                }
            ]
        },
        "actual_feedback_v1": [
            {
                "exercise_id": "max_hang_5s",
                "feedback_label": "ok",
                "completed": True,
                "used_total_load_kg": 90.0,
            }
        ],
    }

    errs = validate_instance(payload, schema_registry, "resolved_day_log_entry.v1")
    assert errs == []
