from __future__ import annotations

import json
from pathlib import Path

from catalog.engine.daily_loop import preview_day


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_daily_preview_determinism(tmp_path: Path):
    plan = {
        "plan_version": "planner.v1",
        "start_date": "2026-01-05",
        "weeks": [
            {
                "week_index": 0,
                "days": [
                    {
                        "date": "2026-01-05",
                        "weekday": "mon",
                        "sessions": [
                            {
                                "session_id": "strength_long",
                                "slot": "evening",
                                "intent": "strength",
                                "priority": "high",
                                "location": "home",
                                "gym_id": None,
                                "constraints_applied": [],
                                "explain": ["fixture"],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    user_state = json.loads(Path("data/user_state.json").read_text(encoding="utf-8"))

    plan_path = tmp_path / "plan.json"
    state_path = tmp_path / "user_state.json"
    out_1 = tmp_path / "resolved_1.json"
    out_2 = tmp_path / "resolved_2.json"
    _write(plan_path, plan)
    _write(state_path, user_state)

    preview_day(str(plan_path), "2026-01-05", str(state_path), str(out_1))
    preview_day(str(plan_path), "2026-01-05", str(state_path), str(out_2))

    assert out_1.read_text(encoding="utf-8") == out_2.read_text(encoding="utf-8")
