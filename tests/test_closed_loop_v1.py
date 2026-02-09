from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from catalog.engine.closed_loop_v1 import apply_day_result_to_user_state, ensure_planning_defaults
from catalog.engine.planner_v1 import generate_week_plan


def test_resolve_planned_day_is_stable(tmp_path: Path):
    plan_path = tmp_path / "plan_week.json"
    out_a = tmp_path / "resolved_a.json"
    out_b = tmp_path / "resolved_b.json"

    plan = generate_week_plan(start_date="2026-01-05", availability={}, allowed_locations=["home", "gym", "outdoor"])
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    cmd = [
        sys.executable,
        "scripts/resolve_planned_day.py",
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
            {"session_id": "blocx_power_endurance", "intent": "power_endurance", "tags": {"hard": True, "finger": False}},
        ],
    }

    done = apply_day_result_to_user_state(base, resolved_day=resolved_day, status="done")
    assert done["stimulus_recency"]["finger_strength"]["last_done_date"] == "2026-01-05"
    assert done["fatigue_proxy"]["done_sessions_total"] == 2
    assert done["fatigue_proxy"]["hard_sessions_total"] == 2

    skipped = apply_day_result_to_user_state(done, resolved_day=resolved_day, status="skipped")
    assert skipped["stimulus_recency"]["finger_strength"]["last_skipped_date"] == "2026-01-05"
    assert skipped["fatigue_proxy"]["skipped_sessions_total"] == 2
