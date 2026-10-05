"""B367 (#2) — undoing a skip restores the session that was skipped.

``mark_skipped`` swaps the session for a ``regeneration_easy`` stub (A294 keeps
``skipped_session_id`` / ``skipped_tags`` on it). ``mark_planned`` only popped
the status, and the UI sends the stub's id — so the undo left a planned
regeneration_easy where the original session was, and a skipped custom lost
its exercises for good. The completion-log entry of the skip (logged under the
original id) also survived the undo.
"""
from __future__ import annotations

import copy
import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine.planner_v2 import _SESSION_META
from backend.engine.replanner_v1 import apply_events

client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"

FINGER = "strength_long"
MON = "2026-10-05"


def _sess(sid, slot="evening", **kw):
    m = _SESSION_META[sid]
    s = {"slot": slot, "session_id": sid, "location": "gym", "gym_id": "g1", "intensity": m["intensity"],
         "tags": {"hard": m["hard"], "finger": m["finger"]}, "constraints_applied": [],
         "resolved": {"resolved_session": {"exercise_instances": [{"exercise_id": "max_hang_7s"}]}}}
    s.update(kw)
    return s


def _custom(slot="evening"):
    return {"slot": slot, "session_id": "custom_abc", "custom_session_id": "abc", "is_custom": True,
            "session_mode": "custom_build", "name": "Mine", "status": "planned", "location": "home",
            "intensity": "high", "tags": {"hard": True, "finger": True},
            "exercises": [{"exercise_id": "max_hang_7s", "sets": 5}], "constraints_applied": ["custom_add"]}


def _plan(days_sessions, start=MON):
    d0 = date.fromisoformat(start)
    days = [{"date": (d0 + timedelta(i)).isoformat(), "sessions": copy.deepcopy(days_sessions.get(i, []))}
            for i in range(7)]
    return {"start_date": start, "plan_revision": 1,
            "profile_snapshot": {"phase_id": "strength_power", "hard_cap_per_week": 3,
                                 "recovery_multiplier": 1.0},
            "weeks": [{"week_index": 1, "days": days}], "adaptations": []}


def _skip_then_undo(plan, sid, date_=MON):
    skipped = apply_events(plan, [{"event_type": "mark_skipped", "date": date_, "session_ref": sid}])
    stub = next(s for s in skipped["weeks"][0]["days"][0]["sessions"] if s.get("status") == "skipped")
    undone = apply_events(skipped, [{"event_type": "mark_planned", "date": date_,
                                     "session_ref": stub["session_id"]}])
    return skipped, undone


def test_undo_restores_the_catalog_session_byte_identical():
    original = _sess(FINGER)
    _skipped, undone = _skip_then_undo(_plan({0: [original]}), FINGER)
    assert undone["weeks"][0]["days"][0]["sessions"] == [original]


def test_undo_restores_a_skipped_custom_with_its_exercises():
    original = _custom()
    _skipped, undone = _skip_then_undo(_plan({0: [original]}), "custom_abc")
    assert undone["weeks"][0]["days"][0]["sessions"] == [original]


def test_stub_still_carries_the_a294_fields():
    skipped, _ = _skip_then_undo(_plan({0: [_sess(FINGER)]}), FINGER)
    stub = skipped["weeks"][0]["days"][0]["sessions"][0]
    assert stub["session_id"] == "regeneration_easy" and stub["status"] == "skipped"
    assert stub["skipped_session_id"] == FINGER and stub["skipped_tags"] == {"hard": True, "finger": True}


def test_undo_hits_the_skip_stub_not_a_planned_namesake():
    """A planned regeneration_easy earlier in the day used to swallow the undo."""
    easy = _sess("regeneration_easy", slot="morning")
    plan = _plan({0: [easy, _sess(FINGER)]})
    _skipped, undone = _skip_then_undo(plan, FINGER)
    ss = undone["weeks"][0]["days"][0]["sessions"]
    assert [s["session_id"] for s in ss] == ["regeneration_easy", FINGER]
    assert ss[0] == easy


def test_legacy_a294_stub_is_rebuilt_from_the_catalog():
    stub = {"slot": "evening", "session_id": "regeneration_easy", "location": "gym", "gym_id": "g1",
            "intensity": "low", "tags": {"hard": False, "finger": False}, "status": "skipped",
            "skipped_session_id": FINGER, "skipped_tags": {"hard": True, "finger": True}}
    out = apply_events(_plan({0: [stub]}), [{"event_type": "mark_planned", "date": MON,
                                             "session_ref": "regeneration_easy"}])
    s = out["weeks"][0]["days"][0]["sessions"][0]
    assert s["session_id"] == FINGER and "status" not in s
    assert s["tags"] == {"hard": True, "finger": True} and s["slot"] == "evening"


def test_pre_a294_stub_keeps_the_old_behaviour_but_stops_claiming_a_skip():
    stub = {"slot": "evening", "session_id": "regeneration_easy", "location": "gym",
            "intensity": "low", "tags": {"hard": False, "finger": False}, "status": "skipped"}
    out = apply_events(_plan({0: [stub]}), [{"event_type": "mark_planned", "date": MON,
                                             "session_ref": "regeneration_easy"}])
    s = out["weeks"][0]["days"][0]["sessions"][0]
    assert s["session_id"] == "regeneration_easy" and "status" not in s


def test_undo_never_touches_done_or_other_days():
    done = _sess(FINGER, slot="morning", status="done", feedback_summary="hard")
    other_day = [_sess("power_endurance_gym", status="done")]
    plan = _plan({0: [done, _sess("technique_focus_gym")], 2: other_day})
    _skipped, undone = _skip_then_undo(plan, "technique_focus_gym")
    days = undone["weeks"][0]["days"]
    assert days[0]["sessions"][0] == done
    assert days[0]["sessions"][1]["session_id"] == "technique_focus_gym"
    assert days[2]["sessions"] == other_day


def test_restored_finger_session_is_still_reconciled():
    """Undo is an explicit edit, not an exemption: the 48h gap still applies."""
    plan = _plan({0: [_sess(FINGER, status="done")], 1: [_sess(FINGER)]})
    skipped = apply_events(plan, [{"event_type": "mark_skipped", "date": "2026-10-06", "session_ref": FINGER}])
    undone = apply_events(skipped, [{"event_type": "mark_planned", "date": "2026-10-06",
                                     "session_ref": "regeneration_easy"}])
    tue = undone["weeks"][0]["days"][1]["sessions"][0]
    assert tue["session_id"] == "regeneration_easy" and tue.get("downshifted_from") == FINGER
    assert undone["weeks"][0]["days"][0]["sessions"][0]["status"] == "done"


# ── API: the completion log entry of the skip goes away ─────────────────────

@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


def test_api_undo_removes_the_skipped_log_entry(isolated_state):
    d = date.today()
    monday = (d - timedelta(days=d.weekday())).isoformat()
    today = d.isoformat()
    offset = d.weekday()
    plan = _plan({offset: [_sess("technique_focus_gym")]}, start=monday)
    r = client.post("/api/replanner/events", json={
        "week_plan": plan, "today": today,
        "events": [{"event_type": "mark_skipped", "date": today, "session_ref": "technique_focus_gym"}]})
    assert r.status_code == 200, r.text
    log = deps.load_state(None).get("session_completion_log") or []
    assert any(e["date"] == today and e["session_id"] == "technique_focus_gym" and e["status"] == "skipped"
               for e in log)
    r2 = client.post("/api/replanner/events", json={
        "week_plan": r.json()["week_plan"], "today": today,
        "events": [{"event_type": "mark_planned", "date": today, "session_ref": "regeneration_easy"}]})
    assert r2.status_code == 200, r2.text
    restored = r2.json()["week_plan"]["weeks"][0]["days"][offset]["sessions"][0]
    assert restored["session_id"] == "technique_focus_gym" and "status" not in restored
    log = deps.load_state(None).get("session_completion_log") or []
    assert not any(e["date"] == today and e["session_id"] == "technique_focus_gym" for e in log)
