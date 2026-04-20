"""B217: feedback must persist session_duration_seconds on the session slot.

Background (see docs/audit/D216/findings.md): the frontend guided flow writes
the POST /api/feedback response directly to the react-query cache (bypassing a
GET refetch). Before B217, the response serialized the in-memory state without
ever writing `session_duration_seconds` onto the `current_week_plan` session
slot — only into `session_completion_log` + `feedback_log`. So the frontend
`session-card` badge, reading `session.session_duration_seconds`, found
nothing, fell back to the hardcoded slot-table `{lunch:35, morning:60,
evening:90}`, and rendered e.g. "Completed · ~90 min" regardless of wall-clock.

This suite verifies:
  T1: POST with duration → response state has the duration on the session slot.
  T2: Max-guard across resubmits (B197-style) on the session slot.
  T3: `duration_source` in payload → 200 OK, silently ignored (backward-compat
      during a mid-deploy with the old frontend).
  T4: Single POST writes duration in BOTH session_completion_log[-1] AND the
      session slot (two independent writers, both load-bearing).
  T5: Undo (mark_planned via replanner_v1) still pops session_duration_seconds
      per B192 invariant — must not regress here.
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


def _post_feedback(date: str, sid: str, duration_seconds: int | None = None, extra: dict | None = None):
    log_entry: dict = {
        "date": date,
        "session_id": sid,
        "actual": {"exercise_feedback_v1": [
            {"exercise_id": "ex_a", "feedback_label": "ok"},
        ]},
    }
    if duration_seconds is not None:
        log_entry["session_duration_seconds"] = duration_seconds
    if extra:
        log_entry.update(extra)
    return client.post("/api/feedback", json={"log_entry": log_entry})


def _find_session(state: dict, date: str, sid: str, plan_key: str = "current_week_plan"):
    wp = state.get(plan_key) or {}
    if plan_key == "week_plans":
        wp = wp.get(date) or {}  # start_date == date for single-day seeds
    for wk in wp.get("weeks", []):
        for dy in wk.get("days", []):
            if dy.get("date") != date:
                continue
            for ss in dy.get("sessions", []):
                if ss.get("session_id") == sid:
                    return ss
    return None


class TestB217DurationOnSessionSlot:
    """session_duration_seconds lives on the session slot after POST."""

    def test_T1_post_writes_duration_on_session_slot(self):
        """Primary fix: POST response state has duration on current_week_plan session."""
        _seed(_seed_week_plan())
        r = _post_feedback("2026-04-06", "strength_long", 1800)
        assert r.status_code == 200, r.text

        state = deps.load_state(None)
        sess = _find_session(state, "2026-04-06", "strength_long")
        assert sess is not None
        assert sess.get("session_duration_seconds") == 1800

        # Also in week_plans cache (B136b parallel)
        cached = (state.get("week_plans") or {}).get("2026-04-06")
        assert cached is not None
        cached_sess = _find_session({"current_week_plan": cached}, "2026-04-06", "strength_long")
        assert cached_sess is not None
        assert cached_sess.get("session_duration_seconds") == 1800

    def test_T2_resubmit_shorter_preserves_longer(self):
        """Max-guard: accidental restart (~30s) must not clobber real duration."""
        _seed(_seed_week_plan())
        assert _post_feedback("2026-04-06", "strength_long", 1800).status_code == 200
        assert _post_feedback("2026-04-06", "strength_long", 32).status_code == 200

        state = deps.load_state(None)
        sess = _find_session(state, "2026-04-06", "strength_long")
        assert sess.get("session_duration_seconds") == 1800

    def test_T3_duration_source_silently_ignored(self):
        """Backward-compat during mid-deploy: old frontend still sends duration_source.
        Backend must accept it (200 OK) and not persist it anywhere.
        """
        _seed(_seed_week_plan())
        r = _post_feedback(
            "2026-04-06", "strength_long", 1800,
            extra={"duration_source": "timer"},
        )
        assert r.status_code == 200, r.text

        state = deps.load_state(None)
        sess = _find_session(state, "2026-04-06", "strength_long")
        assert sess.get("session_duration_seconds") == 1800
        # duration_source must NOT appear on the session slot
        assert "duration_source" not in sess
        # nor on the completion log entry
        log = state.get("session_completion_log", [])
        assert log and "duration_source" not in log[-1]
        # nor on the feedback_log entry
        fb_log = state.get("feedback_log", [])
        assert fb_log and "duration_source" not in fb_log[-1]

    def test_T4_single_post_writes_both_completion_log_and_slot(self):
        """Two load-bearing writers — completion_log AND session slot — both covered."""
        _seed(_seed_week_plan())
        assert _post_feedback("2026-04-06", "strength_long", 1800).status_code == 200

        state = deps.load_state(None)
        # Completion log
        log = state.get("session_completion_log", [])
        assert len(log) == 1
        assert log[-1].get("session_duration_seconds") == 1800
        # Session slot
        sess = _find_session(state, "2026-04-06", "strength_long")
        assert sess.get("session_duration_seconds") == 1800

    def test_T5_undo_pops_session_duration(self):
        """B192 invariant: Undo (mark_planned) must clear session_duration_seconds
        from the session slot along with the other feedback-derived fields.
        B217 adds a new writer — verify it doesn't leak past an undo.
        """
        wp = _seed_week_plan()
        _seed(wp)
        assert _post_feedback("2026-04-06", "strength_long", 1800).status_code == 200

        # Confirm it's there
        state = deps.load_state(None)
        sess = _find_session(state, "2026-04-06", "strength_long")
        assert sess.get("session_duration_seconds") == 1800

        # Undo via /api/replanner/events (canonical event shape per B192 tests)
        r = client.post("/api/replanner/events", json={
            "week_plan": deepcopy(state["current_week_plan"]),
            "events": [{
                "event_type": "mark_planned",
                "date": "2026-04-06",
                "slot": "evening",
                "session_ref": "strength_long",
            }],
        })
        assert r.status_code == 200, r.text

        # The returned week_plan reflects the pop; also assert on persisted state.
        returned_wp = r.json().get("week_plan") or {}
        returned_sess = _find_session(
            {"current_week_plan": returned_wp}, "2026-04-06", "strength_long"
        )
        assert returned_sess is not None
        assert "session_duration_seconds" not in returned_sess, (
            f"Undo must pop session_duration_seconds (B192 regression). "
            f"Got: {returned_sess}"
        )
