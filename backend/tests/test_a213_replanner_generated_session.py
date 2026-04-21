"""A213 — Replanner `add_generated_session` event integration tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

import pytest

from backend.engine.replanner_v1 import apply_events


def _make_week_plan(day_sessions_by_index: Dict[int, List[Dict[str, Any]]] | None = None) -> Dict[str, Any]:
    dates = [f"2026-04-{20 + i:02d}" for i in range(7)]
    weekdays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    days = [
        {
            "date": dates[i],
            "weekday": weekdays[i],
            "sessions": deepcopy((day_sessions_by_index or {}).get(i, [])),
        }
        for i in range(7)
    ]
    return {"start_date": "2026-04-20", "weeks": [{"days": days}]}


def _make_generated_payload(**overrides: Any) -> Dict[str, Any]:
    payload = {
        "session_mode": "custom_build",
        "build_kind": "body_parts",
        "is_custom": True,
        "name": "Body Part Training — Core",
        "body_parts_selected": ["core"],
        "equipment_mode": "bodyweight",
        "include_cooldown": True,
        "exercises": [
            {
                "exercise_id": "front_plank",
                "body_part": "core",
                "prescription": {"sets": 3, "work_seconds": 30},
            },
            {
                "exercise_id": "hollow_body_hold",
                "body_part": "core",
                "prescription": {"sets": 3, "work_seconds": 20},
            },
        ],
        "estimated_duration_minutes": 25,
        "estimated_load_score": 30,
        "intensity": "medium",
        "tags": {"hard": False, "finger": False},
    }
    payload.update(overrides)
    return payload


class TestAddGeneratedSessionEvent:
    def test_add_generated_session_appears_in_plan(self):
        plan = _make_week_plan()
        payload = _make_generated_payload()
        updated = apply_events(plan, [{
            "event_type": "add_generated_session",
            "session_payload": payload,
            "target_date": "2026-04-22",
            "slot": "evening",
            "location": "home",
        }])
        wed = updated["weeks"][0]["days"][2]
        assert len(wed["sessions"]) == 1
        added = wed["sessions"][0]
        assert added["session_mode"] == "custom_build"
        assert added["build_kind"] == "body_parts"
        assert added["is_custom"] is True
        assert added["status"] == "planned"
        assert added["slot"] == "evening"
        assert added["location"] == "home"
        assert added["constraints_applied"] == ["generated_add"]
        assert "generated_body_parts_2026-04-22_evening" in added["session_id"]

    def test_add_generated_session_slot_conflict_raises(self):
        existing = {
            "session_id": "strength_long",
            "slot": "evening",
            "status": "planned",
            "estimated_load_score": 40,
            "tags": {},
        }
        plan = _make_week_plan({2: [existing]})
        payload = _make_generated_payload()
        with pytest.raises(ValueError, match="already occupied"):
            apply_events(plan, [{
                "event_type": "add_generated_session",
                "session_payload": payload,
                "target_date": "2026-04-22",
                "slot": "evening",
                "location": "home",
            }])

    def test_add_generated_session_missing_payload_skipped(self):
        plan = _make_week_plan()
        updated = apply_events(plan, [{
            "event_type": "add_generated_session",
            "target_date": "2026-04-22",
            "slot": "evening",
        }])
        for day in updated["weeks"][0]["days"]:
            assert day["sessions"] == []

    def test_add_generated_session_invalid_date_skipped(self):
        plan = _make_week_plan()
        updated = apply_events(plan, [{
            "event_type": "add_generated_session",
            "session_payload": _make_generated_payload(),
            "target_date": "2099-01-01",
            "slot": "evening",
        }])
        for day in updated["weeks"][0]["days"]:
            assert day["sessions"] == []

    def test_add_generated_session_no_ripple_effect(self):
        """High-load generated session must NOT trigger ripple into other days."""
        tue_existing = {
            "session_id": "strength_long",
            "slot": "evening",
            "intensity": "max",
            "tags": {"hard": True, "finger": True},
            "estimated_load_score": 60,
            "status": "planned",
        }
        plan = _make_week_plan({1: [tue_existing]})
        payload = _make_generated_payload(estimated_load_score=85)
        updated = apply_events(plan, [{
            "event_type": "add_generated_session",
            "session_payload": payload,
            "target_date": "2026-04-20",
            "slot": "evening",
            "location": "home",
        }])
        tue = updated["weeks"][0]["days"][1]
        assert tue["sessions"][0]["session_id"] == "strength_long"

    def test_mark_done_on_generated_session(self):
        plan = _make_week_plan()
        payload = _make_generated_payload()
        mid = apply_events(plan, [{
            "event_type": "add_generated_session",
            "session_payload": payload,
            "target_date": "2026-04-22",
            "slot": "evening",
            "location": "home",
        }])
        sid = mid["weeks"][0]["days"][2]["sessions"][0]["session_id"]
        updated = apply_events(mid, [{
            "event_type": "mark_done",
            "date": "2026-04-22",
            "session_ref": sid,
            "slot": "evening",
        }])
        wed = updated["weeks"][0]["days"][2]
        assert wed["sessions"][0]["status"] == "done"
        assert wed["sessions"][0]["is_custom"] is True
        assert wed["sessions"][0]["build_kind"] == "body_parts"

    def test_generated_session_load_score_present(self):
        plan = _make_week_plan()
        payload = _make_generated_payload(estimated_load_score=45)
        updated = apply_events(plan, [{
            "event_type": "add_generated_session",
            "session_payload": payload,
            "target_date": "2026-04-22",
            "slot": "evening",
            "location": "home",
        }])
        wed = updated["weeks"][0]["days"][2]
        day_load = sum(s.get("estimated_load_score", 0) for s in wed["sessions"])
        assert day_load == 45

    def test_add_generated_session_default_slot(self):
        plan = _make_week_plan()
        payload = _make_generated_payload()
        updated = apply_events(plan, [{
            "event_type": "add_generated_session",
            "session_payload": payload,
            "target_date": "2026-04-22",
            "location": "home",
        }])
        wed = updated["weeks"][0]["days"][2]
        assert wed["sessions"][0]["slot"] == "evening"
