from __future__ import annotations

import json
import subprocess
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_closed_loop_trace_report_is_deterministic(tmp_path: Path) -> None:
    user_state = {
        "tests": {
            "max_strength": [
                {
                    "test_id": "weighted_pullup_1rm",
                    "exercise_id": "weighted_pullup",
                    "date": "2026-01-20",
                    "external_load_kg": 40.0,
                }
            ]
        },
        "adjustments": {"per_exercise": {"weighted_pullup": {"multiplier": 1.05, "streak": 1}}},
    }
    exercises = {
        "exercises": [
            {
                "id": "weighted_pullup",
                "name": "Weighted Pull-up",
                "role": ["main"],
                "domain": ["strength_general"],
                "location_allowed": ["home", "gym"],
                "equipment_required": ["pullup_bar", "weight"],
                "prescription_defaults": {"sets": 5, "reps": 3, "rest_seconds": 180},
            }
        ]
    }

    user_state_path = tmp_path / "user_state.json"
    exercises_path = tmp_path / "exercises.json"
    out_path = tmp_path / "trace.md"
    write_json(user_state_path, user_state)
    write_json(exercises_path, exercises)

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "closed_loop_trace.py"

    cmd = [
        "python",
        str(script_path),
        "--date",
        "2026-02-02",
        "--exercise_id",
        "weighted_pullup",
        "--feedback",
        "too_easy",
        "--user_state",
        str(user_state_path),
        "--exercises_path",
        str(exercises_path),
        "--output_path",
        str(out_path),
    ]

    first = subprocess.run(cmd, check=True, capture_output=True, text=True)
    second = subprocess.run(cmd, check=True, capture_output=True, text=True)

    assert first.stdout == second.stdout
    assert out_path.read_text(encoding="utf-8") == first.stdout

    output = first.stdout
    assert "## INPUT" in output
    assert "## FEEDBACK" in output
    assert "## OUTPUT" in output
    assert "weighted_pullup" in output
    assert "\"load_kg\": 42.0" in output
    assert "\"sets\": 5" in output
