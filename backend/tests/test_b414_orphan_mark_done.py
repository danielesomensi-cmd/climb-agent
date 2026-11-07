"""B414 — INBOX-2026-11-04-ORPHAN (server side, part 2): a mark_done on a
session that is not in the plan any more is refused, never logged.

04/11: the coach swapped treadmill_hiit_4x4 for a custom at 12:21; the phone,
on a cached plan, played the treadmill session and its feedback marked done a
session that was no longer there. ``apply_events`` did nothing in silence,
and the callers still wrote a completion-log row for it — an orphan
completion the key-session status and the reports then read.

Now ``apply_events`` raises :class:`SessionNotInPlan` (a ``ValueError``, like
the "session not found" of mark_skipped / remove_session):

- ``/api/replanner/events`` answers **422** (dry run included) and writes
  nothing — no completion-log row, no plan save, no revision bump;
- ``/api/feedback`` recognises it (it is NOT the B216 "date outside the plan
  window" ValueError: no retry on another week). Since B414 step 27 it never
  gets that far: ``session_not_in_plan`` answers 409 before any write (the
  full coverage is in test_b414_feedback_session_not_in_plan).
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
from backend.api.routers import feedback as feedback_router
from backend.engine.replanner_v1 import SessionNotInPlan, apply_events

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"
MON = "2026-03-16"
TUE = "2026-03-17"


def _plan() -> dict:
    return {
        "start_date": MON,
        "plan_revision": 4,
        "weeks": [{"phase": "base", "days": [
            {"date": MON, "weekday": "mon", "sessions": [{
                "session_id": "strength_long", "slot": "evening", "status": "done",
                "actual_exercises": [{"exercise_id": "max_hang_7s", "completed": True}],
                "resolved": {"session_load_score": 30, "resolved_session": {
                    "exercise_instances": [{"exercise_id": "max_hang_7s"}]}},
                "session_duration_seconds": 3600,
            }]},
            {"date": TUE, "weekday": "tue", "sessions": [
                {"session_id": "custom_cs_320de282", "slot": "lunch", "is_custom": True,
                 "exercises": [{"exercise_id": "goblet_squat", "sets": 3, "reps": 8}]},
            ]},
        ]}],
    }


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    shutil.copy2(REAL_STATE_PATH, tmp_state)
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    state = deps.load_state(None)
    wp = _plan()
    state["current_week_plan"] = deepcopy(wp)
    state["week_plans"] = {MON: deepcopy(wp)}
    state["session_completion_log"] = [
        {"date": MON, "session_id": "strength_long", "status": "done", "completed_at": "2026-03-16T19:00:00+00:00"},
    ]
    deps.save_state(state, None)
    yield tmp_state


ORPHAN = {"event_type": "mark_done", "date": TUE, "session_ref": "treadmill_hiit_4x4"}


# ---------------------------------------------------------------------------
# apply_events (unit)
# ---------------------------------------------------------------------------

def test_mark_done_on_a_missing_session_raises_and_leaves_the_plan_alone():
    plan = _plan()
    before = deepcopy(plan)
    with pytest.raises(SessionNotInPlan) as e:
        apply_events(plan, [ORPHAN])
    assert isinstance(e.value, ValueError)
    assert (e.value.date, e.value.session_ref, e.value.slot) == (TUE, "treadmill_hiit_4x4", None)
    assert plan == before


def test_slot_only_mark_done_on_an_empty_slot_raises():
    with pytest.raises(SessionNotInPlan):
        apply_events(_plan(), [{"event_type": "mark_done", "date": TUE, "slot": "evening"}])


def test_wrong_slot_for_an_existing_session_raises():
    with pytest.raises(SessionNotInPlan):
        apply_events(_plan(), [{"event_type": "mark_done", "date": TUE, "session_ref": "custom_cs_320de282",
                                "slot": "evening"}])


def test_mark_done_on_a_session_in_the_plan_still_works_and_is_idempotent():
    after = apply_events(_plan(), [{"event_type": "mark_done", "date": TUE, "session_ref": "custom_cs_320de282"}])
    assert after["weeks"][0]["days"][1]["sessions"][0]["status"] == "done"
    # Already done: matched, not an orphan.
    again = apply_events(after, [{"event_type": "mark_done", "date": MON, "session_ref": "strength_long"}])
    assert again["weeks"][0]["days"][0]["sessions"][0]["status"] == "done"


def test_the_coach_swap_then_mark_done_in_one_call_is_accepted():
    """«Registrala al posto di X»: remove + add + mark_done in ONE /events
    call — the mark_done finds the session added just before it."""
    after = apply_events(_plan(), [
        {"event_type": "remove_session", "date": TUE, "session_ref": "custom_cs_320de282", "slot": "lunch"},
        {"event_type": "add_planned_session", "target_date": TUE, "slot": "lunch",
         "session_id": "treadmill_hiit_4x4"},
        {"event_type": "mark_done", "date": TUE, "session_ref": "treadmill_hiit_4x4", "slot": "lunch"},
    ])
    day = after["weeks"][0]["days"][1]
    assert [(s["session_id"], s.get("status")) for s in day["sessions"]] == [("treadmill_hiit_4x4", "done")]


# ---------------------------------------------------------------------------
# /api/replanner/events
# ---------------------------------------------------------------------------

def test_events_answers_422_and_writes_nothing(isolate_state):
    raw_before = isolate_state.read_bytes()
    state = deps.load_state(None)
    r = client.post("/api/replanner/events", json={
        "week_plan": state["week_plans"][MON], "events": [ORPHAN],
        "base_revision": state["week_plans"][MON]["plan_revision"]})
    assert r.status_code == 422, r.text
    assert "not in the plan" in r.json()["detail"]
    # No completion-log row, no plan save, no revision bump: the state file is
    # byte-identical — the played Monday session included.
    assert isolate_state.read_bytes() == raw_before


def test_events_dry_run_answers_422_too(isolate_state):
    raw_before = isolate_state.read_bytes()
    state = deps.load_state(None)
    r = client.post("/api/replanner/events", json={
        "week_plan": state["week_plans"][MON], "events": [ORPHAN], "dry_run": True})
    assert r.status_code == 422, r.text
    assert isolate_state.read_bytes() == raw_before


def test_events_on_a_real_session_still_logs_it(isolate_state):
    state = deps.load_state(None)
    r = client.post("/api/replanner/events", json={
        "week_plan": state["week_plans"][MON],
        "events": [{"event_type": "mark_done", "date": TUE, "session_ref": "custom_cs_320de282"}],
        "base_revision": state["week_plans"][MON]["plan_revision"]})
    assert r.status_code == 200, r.text
    after = deps.load_state(None)
    assert any(e["date"] == TUE and e["session_id"] == "custom_cs_320de282"
               for e in after["session_completion_log"])
    # The played Monday session is byte-identical.
    assert json.dumps(after["week_plans"][MON]["weeks"][0]["days"][0], sort_keys=True) == \
        json.dumps(_plan()["weeks"][0]["days"][0], sort_keys=True)


# ---------------------------------------------------------------------------
# /api/feedback — refused before any write (409, B414 step 27), never retried
# ---------------------------------------------------------------------------

def _orphan_feedback() -> dict:
    return {"log_entry": {"date": TUE, "session_id": "treadmill_hiit_4x4", "session_duration_seconds": 1800,
                          "actual": {"exercise_feedback_v1": [
                              {"exercise_id": "treadmill_intervals", "completed": True, "feedback_label": "ok"}]}},
            "status": "done"}


def test_feedback_on_a_missing_session_answers_409_before_any_mark_done(monkeypatch, isolate_state):
    calls: list = []
    real = feedback_router.apply_events

    def spy(plan, events, **kw):
        calls.append(plan.get("start_date"))
        return real(plan, events, **kw)

    monkeypatch.setattr(feedback_router, "apply_events", spy)
    raw_before = isolate_state.read_bytes()
    r = client.post("/api/feedback", json=_orphan_feedback())
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "session_not_in_plan"
    # Refused before the inline mark_done (and before any B216 retry).
    assert calls == []
    # The week is not changed: no phantom mark_done adaptation, no revision
    # bump, sessions intact — the whole state file is byte-identical.
    assert isolate_state.read_bytes() == raw_before


def test_feedback_b216_rollover_on_a_week_without_the_session_answers_409(isolate_state):
    """Rollover: current_week_plan is the previous week (the date is outside
    it — the B216 case, the plan that counts is week_plans[monday]); the
    session is not there either → 409, nothing written."""
    state = deps.load_state(None)
    prev = deepcopy(_plan())
    prev["start_date"] = "2026-03-09"
    for d, iso in zip(prev["weeks"][0]["days"], ("2026-03-09", "2026-03-10")):
        d["date"] = iso
    state["current_week_plan"] = prev
    state["week_plans"]["2026-03-09"] = deepcopy(prev)
    deps.save_state(state, None)
    raw_before = isolate_state.read_bytes()
    r = client.post("/api/feedback", json=_orphan_feedback())
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["day_sessions"][0]["session_id"] == "custom_cs_320de282"
    assert isolate_state.read_bytes() == raw_before


def test_feedback_b216_retry_still_lands_a_real_session():
    state = deps.load_state(None)
    prev = deepcopy(_plan())
    prev["start_date"] = "2026-03-09"
    for d, iso in zip(prev["weeks"][0]["days"], ("2026-03-09", "2026-03-10")):
        d["date"] = iso
    state["current_week_plan"] = prev
    state["week_plans"]["2026-03-09"] = deepcopy(prev)
    deps.save_state(state, None)
    body = _orphan_feedback()
    body["log_entry"]["session_id"] = "custom_cs_320de282"
    r = client.post("/api/feedback", json=body)
    assert r.status_code == 200, r.text
    sess = deps.load_state(None)["week_plans"][MON]["weeks"][0]["days"][1]["sessions"][0]
    assert sess["status"] == "done"
