"""A139: Verify actual_exercises persistence in session slot after feedback.

A194: rewritten to use TestClient against the real POST /api/feedback endpoint
instead of a hand-rolled inline simulation.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    """Copy real state to tmp and monkeypatch STATE_PATH so tests are isolated."""
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


def _make_week_plan(date: str = "2026-03-16", session_id: str = "strength_long") -> dict:
    """Minimal week plan with one session (planned — feedback will mark it done)."""
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
                    "resolved": {"resolved_session": {"exercise_instances": []}},
                }],
            }],
        }],
    }


def _seed(wp: dict | None = None) -> None:
    """Seed the isolated state with a current_week_plan via deps."""
    wp = wp or _make_week_plan()
    state = deps.load_state(None)
    state["current_week_plan"] = deepcopy(wp)
    state["week_plans"] = {wp["start_date"]: deepcopy(wp)}
    state["session_completion_log"] = []
    deps.save_state(state, None)


def _post_feedback(log_entry: dict) -> dict:
    """POST /api/feedback via TestClient and return the post-request state."""
    r = client.post("/api/feedback", json={"log_entry": log_entry})
    assert r.status_code == 200, r.text
    return deps.load_state(None)


class TestA139ActualExercises:
    """A139: actual_exercises persistence in session slot."""

    def test_rich_feedback_persisted(self):
        """Guided session feedback with load data → actual_exercises stored."""
        _seed()
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

        state = _post_feedback(log_entry)

        session = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert "actual_exercises" in session
        assert len(session["actual_exercises"]) == 2
        assert session["actual_exercises"][0]["exercise_id"] == "max_hang_7s"
        assert session["actual_exercises"][0]["used_external_load_kg"] == 26.0
        assert session["actual_exercises"][0]["used_total_load_kg"] == 101.0
        assert session["actual_exercises"][1]["used_grade"] == "7A"

    def test_empty_feedback_no_actual_exercises(self):
        """Empty exercise_feedback_v1 → actual_exercises NOT added."""
        _seed()
        log_entry = {
            "date": "2026-03-16",
            "session_id": "strength_long",
            "actual": {"exercise_feedback_v1": []},
        }

        state = _post_feedback(log_entry)

        session = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert "actual_exercises" not in session

    def test_label_only_feedback_persisted(self):
        """FeedbackDialog flow: only labels → actual_exercises stored with labels only."""
        _seed()
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

        state = _post_feedback(log_entry)

        session = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert "actual_exercises" in session
        assert len(session["actual_exercises"]) == 2
        # Should have labels but no load data
        assert session["actual_exercises"][0]["feedback_label"] == "ok"
        assert "used_external_load_kg" not in session["actual_exercises"][0]

    def test_survives_in_week_plans_cache(self):
        """actual_exercises written via current_week_plan reference also exists in week_plans{}."""
        _seed()
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

        state = _post_feedback(log_entry)

        # current_week_plan and week_plans["2026-03-16"] should be the same reference
        cached = state["week_plans"]["2026-03-16"]
        session = cached["weeks"][0]["days"][0]["sessions"][0]
        assert "actual_exercises" in session
        assert session["actual_exercises"][0]["used_external_load_kg"] == 26.0

    def test_session_not_found_no_crash(self):
        """Feedback for a session_id not in week plan → no crash, no actual_exercises."""
        _seed()
        log_entry = {
            "date": "2026-03-16",
            "session_id": "nonexistent_session",
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "x", "feedback_label": "ok", "completed": True},
                ],
            },
        }

        state = _post_feedback(log_entry)

        # Original session should be untouched
        session = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert "actual_exercises" not in session

    def test_date_not_found_no_crash(self):
        """Feedback for a date not in week plan → no crash."""
        _seed()
        log_entry = {
            "date": "2099-01-01",
            "session_id": "strength_long",
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "x", "feedback_label": "ok", "completed": True},
                ],
            },
        }

        state = _post_feedback(log_entry)

        session = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert "actual_exercises" not in session
