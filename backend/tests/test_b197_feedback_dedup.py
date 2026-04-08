"""B197: feedback resubmit must not clobber the recorded session duration.

Background: A194 made POST /api/feedback atomic (mark_done + feedback in one
round-trip). The frontend computes `session_duration_seconds` from
`Date.now() - state.startedAt`. If the user re-runs the guided flow after a
/today render race, `state.startedAt` gets reset to the current time, so the
resubmit carries a duration of ~30 seconds.

Two backend defenses verified here:
  1. session_completion_log entry duration is the MAX across resubmits (not
     last-write-wins), so the real ~30-minute training is preserved.
  2. feedback_log dedup by (date, session_id) — resubmit merges into the
     existing entry instead of appending a new one. The duration on the
     merged entry also keeps the max.

Bug 2 (separate, single-line fix): GET /api/free-session/history must include
the `circuit` field so the frontend day-card can render
`circuit.completed_exercises` for circuit-mode free sessions instead of
showing "0 exercises".
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


def _post_feedback(date: str, sid: str, duration_seconds: int):
    return client.post("/api/feedback", json={
        "log_entry": {
            "date": date,
            "session_id": sid,
            "session_duration_seconds": duration_seconds,
            "actual": {"exercise_feedback_v1": [
                {"exercise_id": "ex_a", "feedback_label": "ok"},
            ]},
        },
    })


class TestB197CompletionLogDuration:
    """session_completion_log preserves max duration across resubmits."""

    def test_first_submit_records_duration(self):
        wp = _seed_week_plan()
        _seed(wp)

        r = _post_feedback("2026-04-06", "strength_long", 1800)  # 30 min
        assert r.status_code == 200, r.text

        state = deps.load_state(None)
        log = state["session_completion_log"]
        assert len(log) == 1
        assert log[0]["session_duration_seconds"] == 1800

    def test_resubmit_with_shorter_duration_preserves_longer(self):
        """Real bug: re-run sends ~30s, must NOT clobber the original ~30 min."""
        wp = _seed_week_plan()
        _seed(wp)

        # First (real) submit: 30 minutes
        assert _post_feedback("2026-04-06", "strength_long", 1800).status_code == 200
        # Second (accidental restart) submit: 32 seconds — must be ignored
        assert _post_feedback("2026-04-06", "strength_long", 32).status_code == 200

        state = deps.load_state(None)
        log = state["session_completion_log"]
        # Dedup: still one entry
        assert len(log) == 1
        # Duration: max preserved
        assert log[0]["session_duration_seconds"] == 1800

    def test_resubmit_with_longer_duration_replaces(self):
        """If a real resubmit happens with a longer duration, take the max."""
        wp = _seed_week_plan()
        _seed(wp)

        assert _post_feedback("2026-04-06", "strength_long", 600).status_code == 200
        assert _post_feedback("2026-04-06", "strength_long", 2400).status_code == 200

        state = deps.load_state(None)
        log = state["session_completion_log"]
        assert len(log) == 1
        assert log[0]["session_duration_seconds"] == 2400


class TestB197FeedbackLogDedup:
    """feedback_log appends are deduped by (date, session_id)."""

    def test_resubmit_does_not_append_duplicate(self):
        """Real bug from prod: 5 entries for the same (date, session_id)."""
        wp = _seed_week_plan()
        _seed(wp)

        for _ in range(5):
            assert _post_feedback("2026-04-06", "strength_long", 1800).status_code == 200

        state = deps.load_state(None)
        fb_log = state.get("feedback_log", [])
        matching = [
            e for e in fb_log
            if e.get("date") == "2026-04-06" and e.get("session_id") == "strength_long"
        ]
        assert len(matching) == 1

    def test_feedback_log_duration_is_max_across_resubmits(self):
        wp = _seed_week_plan()
        _seed(wp)

        assert _post_feedback("2026-04-06", "strength_long", 1800).status_code == 200
        assert _post_feedback("2026-04-06", "strength_long", 32).status_code == 200
        assert _post_feedback("2026-04-06", "strength_long", 47).status_code == 200

        state = deps.load_state(None)
        fb_log = state.get("feedback_log", [])
        matching = [
            e for e in fb_log
            if e.get("date") == "2026-04-06" and e.get("session_id") == "strength_long"
        ]
        assert len(matching) == 1
        assert matching[0]["session_duration_seconds"] == 1800

    def test_different_sessions_same_day_not_deduped(self):
        """Two different sessions on the same day must each get their own entry."""
        wp = _seed_week_plan()
        # Add a second session to the same day
        wp["weeks"][0]["days"][0]["sessions"].append({
            "session_id": "core_short",
            "slot": "morning",
            "resolved": {"resolved_session": {"exercise_instances": []}},
        })
        _seed(wp)

        assert _post_feedback("2026-04-06", "strength_long", 1800).status_code == 200
        assert _post_feedback("2026-04-06", "core_short", 600).status_code == 200

        state = deps.load_state(None)
        fb_log = state.get("feedback_log", [])
        same_day = [e for e in fb_log if e.get("date") == "2026-04-06"]
        sids = {e.get("session_id") for e in same_day}
        assert sids == {"strength_long", "core_short"}


class TestB197CircuitInHistory:
    """Bug 2: GET /api/free-session/history must include the circuit field
    so circuit-mode sessions don't render as '0 exercises' on the day card."""

    def test_history_returns_circuit_for_circuit_mode_session(self):
        # Seed a finished circuit free session directly into state
        state = deps.load_state(None)
        state.setdefault("free_sessions", []).append({
            "id": "free_test_001",
            "date": "2026-04-07",
            "surface": "circuit_core",
            "session_mode": "circuit",
            "context": "standalone",
            "preset_id": None,
            "gym_name": None,
            "summary": {"total_climbs": 0, "sent": 0, "flashed": 0, "attempted": 0},
            "circuit": {
                "work_seconds": 50,
                "rest_seconds": 10,
                "target_exercises": 10,
                "completed_exercises": 10,
                "exercises_performed": [
                    "ce_hollow_flutter", "ce_superman_swimmers", "ce_body_saw",
                    "ce_sl_glute_bridge", "ce_side_plank_l", "ce_alt_leg_raise",
                    "ce_bicycle_crunch", "ce_copenhagen_r", "ce_dead_bug",
                    "ce_toes_to_hands",
                ],
            },
            "climbs": [],
            "started_at": "2026-04-07T18:32:26+00:00",
            "finished_at": "2026-04-07T18:42:35+00:00",
            "duration_minutes": 10,
            "overall_feel": "good",
            "load_score": 5.0,
        })
        deps.save_state(state, None)

        r = client.get("/api/free-session/history?date=2026-04-07")
        assert r.status_code == 200, r.text
        sessions = r.json()["sessions"]
        assert len(sessions) == 1

        s = sessions[0]
        # Bug 2 fix: circuit field present
        assert "circuit" in s
        assert s["circuit"] is not None
        assert s["circuit"]["completed_exercises"] == 10
        assert len(s["circuit"]["exercises_performed"]) == 10
