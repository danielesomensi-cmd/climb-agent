"""Health-vault export (2026-08): feedback must persist the REAL wall-clock
``started_at`` on the completion log entry.

Background: the guided player measures a real start timestamp
(``state.startedAt``) and the on-screen timer runs on it, but the client only
ever sent the derived ``session_duration_seconds`` delta — the start timestamp
was thrown away. The completion log therefore had a real finish
(``completed_at``, set server-side at feedback time) but no real start. For the
Garmin/health-vault join we need the real ``ora_inizio``.

This suite verifies:
  T1: POST with started_at → completion log entry carries started_at, plus a
      finished_at mirroring the real completion tap.
  T2: A quick "mark done" WITHOUT started_at must NOT invent one — the field
      stays absent (requirement: never fake a timestamp).
  T3: started_at is not clobbered on resubmit.
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
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


def _seed_week_plan(date: str = "2026-04-06", session_id: str = "strength_long") -> dict:
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


def _seed(wp: dict) -> None:
    state = deps.load_state(None)
    state["current_week_plan"] = deepcopy(wp)
    state["week_plans"] = {wp["start_date"]: deepcopy(wp)}
    state["session_completion_log"] = []
    state["feedback_log"] = []
    deps.save_state(state, None)


def _post_feedback(date: str, sid: str, started_at: str | None = None, duration_seconds: int | None = 1800):
    log_entry: dict = {
        "date": date,
        "session_id": sid,
        "actual": {"exercise_feedback_v1": [
            {"exercise_id": "ex_a", "feedback_label": "ok"},
        ]},
    }
    if started_at is not None:
        log_entry["started_at"] = started_at
    if duration_seconds is not None:
        log_entry["session_duration_seconds"] = duration_seconds
    return client.post("/api/feedback", json={"log_entry": log_entry})


def _log_entry(state: dict, date: str, sid: str):
    for e in reversed(state.get("session_completion_log", [])):
        if e.get("date") == date and e.get("session_id") == sid:
            return e
    return None


class TestStartedAtPersistence:
    def test_T1_started_at_persisted_with_finished_at(self):
        _seed(_seed_week_plan())
        start = "2026-04-06T17:58:12+00:00"
        r = _post_feedback("2026-04-06", "strength_long", started_at=start)
        assert r.status_code == 200, r.text

        state = deps.load_state(None)
        entry = _log_entry(state, "2026-04-06", "strength_long")
        assert entry is not None
        assert entry.get("started_at") == start
        # finished_at mirrors the real completion tap so the export reads a pair.
        assert entry.get("finished_at") == entry.get("completed_at")
        assert entry.get("completed_at")  # server-side, always present for done

    def test_T2_no_started_at_is_not_invented(self):
        """Quick mark-done has no real start → field must stay absent, never faked."""
        _seed(_seed_week_plan())
        r = _post_feedback("2026-04-06", "strength_long", started_at=None)
        assert r.status_code == 200, r.text

        state = deps.load_state(None)
        entry = _log_entry(state, "2026-04-06", "strength_long")
        assert entry is not None
        assert "started_at" not in entry
        assert "finished_at" not in entry
        # completed_at is still the real finish — that one is always captured.
        assert entry.get("completed_at")

    def test_T3_started_at_not_clobbered_on_resubmit(self):
        _seed(_seed_week_plan())
        first = "2026-04-06T17:58:12+00:00"
        assert _post_feedback("2026-04-06", "strength_long", started_at=first).status_code == 200
        # A stray resubmit with a different (later) start must not overwrite it.
        assert _post_feedback("2026-04-06", "strength_long", started_at="2026-04-06T19:30:00+00:00").status_code == 200

        state = deps.load_state(None)
        entry = _log_entry(state, "2026-04-06", "strength_long")
        assert entry.get("started_at") == first
