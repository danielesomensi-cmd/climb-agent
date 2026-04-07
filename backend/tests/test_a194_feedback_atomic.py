"""A194: atomic feedback endpoint — mark_done + feedback in single round-trip.

Tests the refactored POST /api/feedback that:
  1. Applies mark_done inline to current_week_plan via apply_events
  2. Appends to session_completion_log (with dedup guard)
  3. Returns the updated week_plan in the response
  4. Handles missing fields gracefully
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


def _seed_week_plan(
    date: str = "2026-04-06",
    session_id: str = "strength_long",
) -> dict:
    """Minimal valid week plan with one planned session."""
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
                    "resolved": {
                        "resolved_session": {"exercise_instances": []},
                    },
                }],
            }],
        }],
    }


def _seed_state_with_week_plan(wp: dict) -> None:
    """Load state via deps, attach the week plan, save via deps."""
    state = deps.load_state(None)
    state["current_week_plan"] = deepcopy(wp)
    state["week_plans"] = {wp["start_date"]: deepcopy(wp)}
    state["session_completion_log"] = []
    deps.save_state(state, None)


class TestA194FeedbackAtomic:
    """A194: atomic feedback endpoint."""

    def test_mark_done_applied_inline(self):
        """POST /api/feedback marks the target session as done in current_week_plan."""
        wp = _seed_week_plan()
        _seed_state_with_week_plan(wp)

        r = client.post("/api/feedback", json={
            "log_entry": {
                "date": "2026-04-06",
                "session_id": "strength_long",
                "actual": {"exercise_feedback_v1": []},
            },
        })
        assert r.status_code == 200, r.text

        # Verify state was persisted with status=done
        state = deps.load_state(None)
        sess = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert sess.get("status") == "done"

    def test_response_includes_week_plan(self):
        """Response contains the updated week_plan so frontend can setQueryData."""
        wp = _seed_week_plan()
        _seed_state_with_week_plan(wp)

        r = client.post("/api/feedback", json={
            "log_entry": {
                "date": "2026-04-06",
                "session_id": "strength_long",
                "actual": {"exercise_feedback_v1": []},
            },
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "week_plan" in data
        returned_plan = data["week_plan"]
        assert returned_plan["start_date"] == "2026-04-06"
        # The returned plan has the session marked done
        sess = returned_plan["weeks"][0]["days"][0]["sessions"][0]
        assert sess["status"] == "done"

    def test_session_completion_log_updated_no_duplicates(self):
        """A194 R3: completion_log dedup — same date+session_id+status not duplicated."""
        wp = _seed_week_plan()
        _seed_state_with_week_plan(wp)

        # Pre-populate completion_log as if /today handleMarkDone already fired
        state = deps.load_state(None)
        state["session_completion_log"] = [{
            "date": "2026-04-06",
            "session_id": "strength_long",
            "status": "done",
            "completed_at": "2026-04-06T10:00:00+00:00",
        }]
        deps.save_state(state, None)

        r = client.post("/api/feedback", json={
            "log_entry": {
                "date": "2026-04-06",
                "session_id": "strength_long",
                "actual": {"exercise_feedback_v1": []},
            },
        })
        assert r.status_code == 200

        # Should still be exactly one entry (no duplicate)
        state = deps.load_state(None)
        log = state.get("session_completion_log", [])
        matching = [
            e for e in log
            if e.get("date") == "2026-04-06"
            and e.get("session_id") == "strength_long"
            and e.get("status") == "done"
        ]
        assert len(matching) == 1

    def test_session_completion_log_appended_when_missing(self):
        """When no prior entry exists, feedback appends a fresh completion log entry."""
        wp = _seed_week_plan()
        _seed_state_with_week_plan(wp)

        r = client.post("/api/feedback", json={
            "log_entry": {
                "date": "2026-04-06",
                "session_id": "strength_long",
                "actual": {"exercise_feedback_v1": []},
            },
        })
        assert r.status_code == 200

        state = deps.load_state(None)
        log = state.get("session_completion_log", [])
        assert len(log) == 1
        assert log[0]["date"] == "2026-04-06"
        assert log[0]["session_id"] == "strength_long"
        assert log[0]["status"] == "done"

    def test_feedback_with_unknown_session_graceful(self):
        """A194: unknown session_id in log_entry does not crash — mark_done skipped, feedback still applies."""
        wp = _seed_week_plan()
        _seed_state_with_week_plan(wp)

        r = client.post("/api/feedback", json={
            "log_entry": {
                "date": "2026-04-06",
                "session_id": "nonexistent_session",
                "actual": {"exercise_feedback_v1": []},
            },
        })
        # Should not crash — response is still 200
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

        # Original session remains untouched (not marked done)
        state = deps.load_state(None)
        sess = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert sess.get("status") != "done"

    def test_feedback_without_current_week_plan(self):
        """No current_week_plan → feedback still applies, no week_plan in response."""
        # Don't seed a week plan
        state = deps.load_state(None)
        state.pop("current_week_plan", None)
        state["week_plans"] = {}
        state["session_completion_log"] = []
        deps.save_state(state, None)

        r = client.post("/api/feedback", json={
            "log_entry": {
                "date": "2026-04-06",
                "session_id": "strength_long",
                "actual": {"exercise_feedback_v1": []},
            },
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        # No week_plan should be returned
        assert "week_plan" not in data
