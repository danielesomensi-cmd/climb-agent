"""A207 — Custom session integration with replanner event pipeline.

Verifies that custom sessions can be:
- added via the `add_custom_session` event,
- marked done/skipped through the standard event handlers,
- contribute their load_score to day totals,
- do NOT trigger ripple effects (custom sessions bypass replanner logic).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from backend.engine.replanner_v1 import apply_events


# ── Fixtures ────────────────────────────────────────────────────────────


def _make_week_plan(day_sessions_by_index: Dict[int, List[Dict[str, Any]]] | None = None) -> Dict[str, Any]:
    """Empty week starting Mon 2026-03-16, optionally preloaded per-day."""
    dates = [f"2026-03-{16 + i:02d}" for i in range(7)]
    weekdays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    days = [
        {
            "date": dates[i],
            "weekday": weekdays[i],
            "sessions": deepcopy((day_sessions_by_index or {}).get(i, [])),
        }
        for i in range(7)
    ]
    return {
        "start_date": "2026-03-16",
        "weeks": [{"days": days}],
    }


def _make_catalog_session(sid: str, **kwargs: Any) -> Dict[str, Any]:
    s = {
        "session_id": sid,
        "slot": "evening",
        "location": "gym",
        "status": "planned",
        "estimated_load_score": 40,
        "intensity": "medium",
        "tags": {},
    }
    s.update(kwargs)
    return s


def _make_custom_session(cs_id: str = "cs_abc12345", **overrides: Any) -> Dict[str, Any]:
    cs = {
        "id": cs_id,
        "name": "My conditioning",
        "created_at": "2026-04-01T10:00:00Z",
        "updated_at": "2026-04-01T10:00:00Z",
        "tags": ["core", "mobility"],
        "exercises": [
            {
                "exercise_id": "dead_hang_body",
                "sets": 3,
                "reps": None,
                "work_seconds": 10,
                "rest_between_sets_seconds": 120,
                "load_kg": 0,
                "notes": "",
            }
        ],
        "estimated_load_score": 35,
        "estimated_duration_minutes": 45,
    }
    cs.update(overrides)
    return cs


# ── Tests ───────────────────────────────────────────────────────────────


class TestAddCustomSessionEvent:
    def test_add_custom_session_appears_in_plan(self):
        plan = _make_week_plan()
        cs = _make_custom_session()
        updated = apply_events(
            plan,
            [
                {
                    "event_type": "add_custom_session",
                    "custom_session_id": cs["id"],
                    "target_date": "2026-03-18",  # Wed
                    "slot": "evening",
                    "location": "home",
                }
            ],
            custom_sessions=[cs],
        )
        wed = updated["weeks"][0]["days"][2]
        assert len(wed["sessions"]) == 1
        added = wed["sessions"][0]
        assert added["session_id"] == f"custom_{cs['id']}"
        assert added["custom_session_id"] == cs["id"]
        assert added["is_custom"] is True
        assert added["session_mode"] == "custom_build"
        assert added["name"] == "My conditioning"
        assert added["exercises"] == cs["exercises"]
        assert added["estimated_load_score"] == 35
        assert added["status"] == "planned"
        assert added["tags"] == {"hard": False, "finger": False}

    def test_add_invalid_custom_session_id_is_skipped(self):
        plan = _make_week_plan()
        updated = apply_events(
            plan,
            [
                {
                    "event_type": "add_custom_session",
                    "custom_session_id": "cs_does_not_exist",
                    "target_date": "2026-03-18",
                    "slot": "evening",
                    "location": "home",
                }
            ],
            custom_sessions=[_make_custom_session("cs_something_else")],
        )
        # Silent skip: no exception, no session added
        for day in updated["weeks"][0]["days"]:
            assert day["sessions"] == []

    def test_custom_session_does_not_trigger_ripple(self):
        """Adding a high-load custom session must NOT cascade into other days.

        Contrast with outdoor/hard catalog sessions, which can trigger
        ripple effects. Custom sessions bypass replanner entirely.
        """
        # Pre-load a hard catalog session on Tue — it would normally be
        # replaced if the previous day carried a high-load hard session.
        existing = _make_catalog_session(
            "strength_long",
            intensity="max",
            tags={"hard": True, "finger": True},
            estimated_load_score=60,
        )
        plan = _make_week_plan({1: [existing]})  # Tue
        cs = _make_custom_session(estimated_load_score=90)  # Very high load
        updated = apply_events(
            plan,
            [
                {
                    "event_type": "add_custom_session",
                    "custom_session_id": cs["id"],
                    "target_date": "2026-03-16",  # Mon — day before Tue
                    "slot": "evening",
                    "location": "home",
                }
            ],
            custom_sessions=[cs],
        )
        tue = updated["weeks"][0]["days"][1]
        # Tuesday session must NOT have been replaced by a complementary
        assert tue["sessions"][0]["session_id"] == "strength_long"


class TestMarkDoneSkippedOnCustomSession:
    def test_mark_done_on_custom_session(self):
        plan = _make_week_plan()
        cs = _make_custom_session()
        mid = apply_events(
            plan,
            [
                {
                    "event_type": "add_custom_session",
                    "custom_session_id": cs["id"],
                    "target_date": "2026-03-18",
                    "slot": "evening",
                    "location": "home",
                }
            ],
            custom_sessions=[cs],
        )
        updated = apply_events(
            mid,
            [
                {
                    "event_type": "mark_done",
                    "date": "2026-03-18",
                    "session_ref": f"custom_{cs['id']}",
                    "slot": "evening",
                }
            ],
        )
        wed = updated["weeks"][0]["days"][2]
        assert wed["sessions"][0]["status"] == "done"
        assert wed["sessions"][0]["is_custom"] is True

    def test_mark_skipped_on_custom_session(self):
        plan = _make_week_plan()
        cs = _make_custom_session()
        mid = apply_events(
            plan,
            [
                {
                    "event_type": "add_custom_session",
                    "custom_session_id": cs["id"],
                    "target_date": "2026-03-18",
                    "slot": "evening",
                    "location": "home",
                }
            ],
            custom_sessions=[cs],
        )
        updated = apply_events(
            mid,
            [
                {
                    "event_type": "mark_skipped",
                    "date": "2026-03-18",
                    "session_ref": f"custom_{cs['id']}",
                    "slot": "evening",
                }
            ],
        )
        wed = updated["weeks"][0]["days"][2]
        # mark_skipped replaces the session with a recovery fill marked skipped
        assert any(s.get("status") == "skipped" for s in wed["sessions"])


class TestCustomSessionLoadInDay:
    def test_custom_session_load_score_present_on_session(self):
        """A207 relies on `estimated_load_score` on the session entry so that
        existing report/adherence aggregations (which read this field) pick up
        custom sessions without any extra wiring."""
        plan = _make_week_plan()
        cs = _make_custom_session(estimated_load_score=55)
        updated = apply_events(
            plan,
            [
                {
                    "event_type": "add_custom_session",
                    "custom_session_id": cs["id"],
                    "target_date": "2026-03-18",
                    "slot": "evening",
                    "location": "home",
                }
            ],
            custom_sessions=[cs],
        )
        wed = updated["weeks"][0]["days"][2]
        day_load = sum(s.get("estimated_load_score", 0) for s in wed["sessions"])
        assert day_load == 55
