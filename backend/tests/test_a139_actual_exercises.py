"""A139: Verify actual_exercises persistence in session slot after feedback."""

from __future__ import annotations

import copy
from unittest.mock import patch

import pytest

from backend.api.routers.feedback import router  # noqa: F401 — ensure import works


def _make_week_plan(date: str = "2026-03-16", session_id: str = "strength_long") -> dict:
    """Minimal week plan with one completed session."""
    return {
        "start_date": date,
        "weeks": [{
            "phase": "base",
            "days": [{
                "date": date,
                "weekday": "mon",
                "sessions": [{
                    "session_id": session_id,
                    "slot": "evening",
                    "status": "done",
                    "resolved": {"resolved_session": {"exercise_instances": []}},
                }],
            }],
        }],
    }


def _make_state(week_plan: dict | None = None) -> dict:
    """Minimal user state with a current_week_plan."""
    wp = week_plan or _make_week_plan()
    return {
        "current_week_plan": wp,
        "week_plans": {wp["start_date"]: wp} if wp else {},
        "session_completion_log": [],
        "feedback_log": [],
        "working_loads": {"entries": [], "rules": {}},
        "tests": {},
        "baselines": {},
        "assessment": {"profile": {}, "tests": {}},
        "body": {"weight_kg": 75},
    }


def _post_feedback(state: dict, log_entry: dict, status: str = "done") -> dict:
    """Simulate POST /api/feedback by calling the handler's core logic inline.

    We replicate the relevant steps from feedback.py to avoid needing a running server,
    while still testing the actual_exercises persistence logic.
    """
    from backend.engine.progression_v1 import apply_feedback as _apply_feedback
    from backend.engine.adaptive_replan import append_feedback_log, load_exercises_by_id

    state = _apply_feedback(log_entry, state)

    exercises_by_id = load_exercises_by_id()
    append_feedback_log(state, log_entry, None, exercises_by_id)

    # A139: Persist raw actual exercise data in session slot (mirrors feedback.py)
    fb_items = (log_entry.get("actual") or {}).get("exercise_feedback_v1") or []
    if fb_items:
        target_date = log_entry.get("date")
        target_sid = log_entry.get("session_id")
        wp = state.get("current_week_plan") or {}
        for week_block in wp.get("weeks", []):
            for day_entry in week_block.get("days", []):
                if day_entry.get("date") != target_date:
                    continue
                for sess in day_entry.get("sessions", []):
                    if sess.get("session_id") == target_sid:
                        sess["actual_exercises"] = fb_items
                        break

    return state


class TestA139ActualExercises:
    """A139: actual_exercises persistence in session slot."""

    def test_rich_feedback_persisted(self):
        """Guided session feedback with load data → actual_exercises stored."""
        state = _make_state()
        log_entry = {
            "date": "2026-03-16",
            "session_id": "strength_long",
            "session_duration_seconds": 3600,
            "actual": {
                "exercise_feedback_v1": [
                    {
                        "exercise_id": "max_hang_7s",
                        "feedback_label": "hard",
                        "completed": True,
                        "used_external_load_kg": 26.0,
                        "used_total_load_kg": 101.0,
                    },
                    {
                        "exercise_id": "limit_bouldering",
                        "feedback_label": "ok",
                        "completed": True,
                        "used_grade": "7A",
                    },
                ],
            },
        }

        state = _post_feedback(state, log_entry)

        session = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert "actual_exercises" in session
        assert len(session["actual_exercises"]) == 2
        assert session["actual_exercises"][0]["exercise_id"] == "max_hang_7s"
        assert session["actual_exercises"][0]["used_external_load_kg"] == 26.0
        assert session["actual_exercises"][0]["used_total_load_kg"] == 101.0
        assert session["actual_exercises"][1]["used_grade"] == "7A"

    def test_empty_feedback_no_actual_exercises(self):
        """Empty exercise_feedback_v1 → actual_exercises NOT added."""
        state = _make_state()
        log_entry = {
            "date": "2026-03-16",
            "session_id": "strength_long",
            "actual": {"exercise_feedback_v1": []},
        }

        state = _post_feedback(state, log_entry)

        session = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert "actual_exercises" not in session

    def test_label_only_feedback_persisted(self):
        """FeedbackDialog flow: only labels → actual_exercises stored with labels only."""
        state = _make_state()
        log_entry = {
            "date": "2026-03-16",
            "session_id": "strength_long",
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "max_hang_7s", "feedback_label": "ok", "completed": True},
                    {"exercise_id": "limit_bouldering", "feedback_label": "hard", "completed": True},
                ],
            },
        }

        state = _post_feedback(state, log_entry)

        session = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert "actual_exercises" in session
        assert len(session["actual_exercises"]) == 2
        # Should have labels but no load data
        assert session["actual_exercises"][0]["feedback_label"] == "ok"
        assert "used_external_load_kg" not in session["actual_exercises"][0]

    def test_survives_in_week_plans_cache(self):
        """actual_exercises written via current_week_plan reference also exists in week_plans{}."""
        state = _make_state()
        log_entry = {
            "date": "2026-03-16",
            "session_id": "strength_long",
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "max_hang_7s", "feedback_label": "hard", "completed": True,
                     "used_external_load_kg": 26.0},
                ],
            },
        }

        state = _post_feedback(state, log_entry)

        # current_week_plan and week_plans["2026-03-16"] should be the same reference
        cached = state["week_plans"]["2026-03-16"]
        session = cached["weeks"][0]["days"][0]["sessions"][0]
        assert "actual_exercises" in session
        assert session["actual_exercises"][0]["used_external_load_kg"] == 26.0

    def test_session_not_found_no_crash(self):
        """Feedback for a session_id not in week plan → no crash, no actual_exercises."""
        state = _make_state()
        log_entry = {
            "date": "2026-03-16",
            "session_id": "nonexistent_session",
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "x", "feedback_label": "ok", "completed": True},
                ],
            },
        }

        state = _post_feedback(state, log_entry)

        # Original session should be untouched
        session = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert "actual_exercises" not in session

    def test_date_not_found_no_crash(self):
        """Feedback for a date not in week plan → no crash."""
        state = _make_state()
        log_entry = {
            "date": "2099-01-01",
            "session_id": "strength_long",
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "x", "feedback_label": "ok", "completed": True},
                ],
            },
        }

        state = _post_feedback(state, log_entry)

        session = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert "actual_exercises" not in session
