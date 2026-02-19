from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from backend.engine.closed_loop_v1 import apply_day_result_to_user_state, ensure_planning_defaults
from backend.engine.planner_v1 import generate_week_plan


def test_resolve_planned_day_is_stable(tmp_path: Path):
    plan_path = tmp_path / "plan_week.json"
    out_a = tmp_path / "resolved_a.json"
    out_b = tmp_path / "resolved_b.json"

    plan = generate_week_plan(start_date="2026-01-05", availability={}, allowed_locations=["home", "gym", "outdoor"], default_gym_id="work_gym")
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    cmd = [
        sys.executable,
        "_archive/scripts_legacy/scripts/resolve_planned_day.py",
        "--plan",
        str(plan_path),
        "--date",
        "2026-01-05",
        "--out",
        str(out_a),
    ]
    subprocess.run(cmd, check=True)
    cmd[-1] = str(out_b)
    subprocess.run(cmd, check=True)

    a = json.loads(out_a.read_text(encoding="utf-8"))
    b = json.loads(out_b.read_text(encoding="utf-8"))
    assert a == b


def test_log_update_user_state_counters():
    base = ensure_planning_defaults({"schema_version": "1.3"})
    resolved_day = {
        "date": "2026-01-05",
        "plan": {"plan_version": "planner.v1", "start_date": "2026-01-05"},
        "sessions": [
            {"session_id": "strength_long", "intent": "strength", "tags": {"hard": True, "finger": True}},
            {"session_id": "gym_power_endurance", "intent": "power_endurance", "tags": {"hard": True, "finger": False}},
        ],
    }

    done = apply_day_result_to_user_state(base, resolved_day=resolved_day, status="done")
    assert done["stimulus_recency"]["finger_strength"]["last_done_date"] == "2026-01-05"
    assert done["fatigue_proxy"]["done_sessions_total"] == 2
    assert done["fatigue_proxy"]["hard_sessions_total"] == 2

    skipped = apply_day_result_to_user_state(done, resolved_day=resolved_day, status="skipped")
    assert skipped["stimulus_recency"]["finger_strength"]["last_skipped_date"] == "2026-01-05"
    assert skipped["fatigue_proxy"]["skipped_sessions_total"] == 2


def test_resolve_planned_day_fails_for_gym_session_without_gym_id(tmp_path: Path):
    plan_path = tmp_path / "plan_week.json"
    out_path = tmp_path / "resolved.json"

    plan = {
        "plan_version": "planner.v1",
        "start_date": "2026-01-05",
        "weeks": [
            {
                "week_index": 1,
                "days": [
                    {
                        "date": "2026-01-05",
                        "weekday": "mon",
                        "sessions": [
                            {
                                "slot": "evening",
                                "session_id": "gym_power_bouldering",
                                "location": "gym",
                                "gym_id": None,
                                "intent": "power",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    cmd = [
        sys.executable,
        "_archive/scripts_legacy/scripts/resolve_planned_day.py",
        "--plan",
        str(plan_path),
        "--date",
        "2026-01-05",
        "--out",
        str(out_path),
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "must include non-null gym_id" in proc.stderr


def test_resolve_planned_day_respects_user_state_for_gym_equipment(tmp_path: Path):
    user_state_path = tmp_path / "user_state.json"
    plan_path = tmp_path / "plan_week.json"
    out_path = tmp_path / "resolved.json"

    user_state = {
        "schema_version": "1.4",
        "equipment": {
            "home": [],
            "gyms": [
                {
                    "gym_id": "blocx",
                    "name": "BlocX",
                    "equipment": ["campus_board"]
                }
            ]
        }
    }
    user_state_path.write_text(json.dumps(user_state, ensure_ascii=False, indent=2), encoding="utf-8")

    plan = {
        "plan_version": "planner.v1",
        "start_date": "2026-01-05",
        "weeks": [
            {
                "week_index": 1,
                "days": [
                    {
                        "date": "2026-01-05",
                        "weekday": "mon",
                        "sessions": [
                            {
                                "slot": "evening",
                                "session_id": "gym_power_bouldering",
                                "location": "gym",
                                "gym_id": "blocx",
                                "intent": "power"
                            }
                        ]
                    }
                ]
            }
        ]
    }
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    cmd = [
        sys.executable,
        "_archive/scripts_legacy/scripts/resolve_planned_day.py",
        "--plan",
        str(plan_path),
        "--date",
        "2026-01-05",
        "--user-state",
        str(user_state_path),
        "--out",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)

    resolved = json.loads(out_path.read_text(encoding="utf-8"))
    session = resolved["sessions"][0]
    exercise_ids = {ei.get("exercise_id") for ei in session.get("exercise_instances") or []}
    assert "limit_bouldering" not in exercise_ids

    target_blocks = [
        b for b in (session.get("resolved_blocks") or [])
        if b.get("block_id") == "main_limit_bouldering"
    ]
    if target_blocks:
        block = target_blocks[0]
        assert block.get("status") == "skipped"
        assert block.get("message") == "No candidates after hard filters (P0)."
