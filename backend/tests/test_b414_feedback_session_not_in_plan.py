"""B414 step 27 — INBOX-2026-11-04-ORPHAN (server side, part 1): ``POST
/api/feedback`` on a session that is no longer on that day of the plan answers
**409** ``session_not_in_plan`` before any write.

04/11: the coach swapped treadmill_hiit_4x4 for a custom at 12:21; the phone,
on a cached plan, played the treadmill and its feedback wrote an orphan
completion — completion-log row, feedback_log entry (pushing a real one out of
the last 7), working_loads moved — for a session that was not there. Step 4
made the inline mark_done refuse it (``SessionNotInPlan``) but /feedback still
answered 200 and wrote the rest; the app learned to handle the refusal at step
24 (the player asks: in place of X / as an extra / discard).

The check reads the plan the inline mark_done writes — ``current_week_plan``
when it covers the date, else ``week_plans[monday]`` (the B216 rollover) — with
the same ``_session_matches`` apply_events uses, so the two never disagree.
Unchanged (200): a date no stored plan covers (an archived week), a session
already done, the B216 rollover onto a session that is there, no plan at all.
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
PREV = "2026-03-09"
MON = "2026-03-16"
TUE = "2026-03-17"
WED = "2026-03-18"

PLAYED_MONDAY = {
    "session_id": "strength_long", "slot": "evening", "status": "done",
    "actual_exercises": [{"exercise_id": "max_hang_7s", "completed": True, "used_external_load_kg": 12}],
    "resolved": {"session_load_score": 30, "resolved_session": {
        "exercise_instances": [{"exercise_id": "max_hang_7s"}]}},
    "session_duration_seconds": 3600,
    "feedback_summary": "hard",
}


def _plan(start: str = MON, dates=(MON, TUE, WED)) -> dict:
    mon, tue, wed = dates
    return {
        "start_date": start,
        "plan_revision": 4,
        "weeks": [{"phase": "base", "days": [
            {"date": mon, "weekday": "mon", "sessions": [deepcopy(PLAYED_MONDAY)]},
            {"date": tue, "weekday": "tue", "sessions": [
                {"session_id": "custom_cs_320de282", "slot": "lunch", "is_custom": True,
                 "name": "Gambe a casa",
                 "exercises": [{"exercise_id": "goblet_squat", "sets": 3, "reps": 8}]},
                {"session_id": "strength_long", "slot": "evening", "location": "gym"},
            ]},
            {"date": wed, "weekday": "wed", "sessions": [
                {"session_id": "regeneration_easy", "slot": "evening", "location": "home"},
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
        {"date": MON, "session_id": "strength_long", "status": "done",
         "completed_at": "2026-03-16T19:00:00+00:00"},
    ]
    state["feedback_log"] = [{"date": MON, "session_id": "strength_long", "difficulty": "hard"}]
    deps.save_state(state, None)
    yield tmp_state


def _save(mutate) -> None:
    state = deps.load_state(None)
    mutate(state)
    deps.save_state(state, None)


def _feedback(sid: str, day: str = TUE) -> dict:
    return {"log_entry": {"date": day, "session_id": sid, "session_duration_seconds": 1800,
                          "actual": {"exercise_feedback_v1": [
                              {"exercise_id": "treadmill_intervals", "completed": True,
                               "feedback_label": "hard"}]}},
            "status": "done"}


def _assert_refused(r, isolate_state, raw_before, *, sid: str, day: str = TUE) -> dict:
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "session_not_in_plan"
    assert (detail["date"], detail["session_id"]) == (day, sid)
    assert detail["message"]
    # Never a stale-plan body: the client would refetch and retry for nothing.
    assert "current_revision" not in detail
    # Nothing written — completion log, feedback_log, working_loads, plan,
    # adaptations, revision, the played Monday: the state file is byte-identical.
    assert isolate_state.read_bytes() == raw_before
    return detail


# ---------------------------------------------------------------------------
# 409 — the session is not on that day
# ---------------------------------------------------------------------------

def test_the_0411_orphan_is_refused_with_the_day_as_the_server_sees_it(isolate_state):
    raw_before = isolate_state.read_bytes()
    r = client.post("/api/feedback", json=_feedback("treadmill_hiit_4x4"))
    detail = _assert_refused(r, isolate_state, raw_before, sid="treadmill_hiit_4x4")
    assert detail["day_sessions"] == [
        {"session_id": "custom_cs_320de282", "slot": "lunch", "status": None, "name": "Gambe a casa"},
        {"session_id": "strength_long", "slot": "evening", "status": None, "name": None},
    ]


def test_a_session_of_another_day_is_not_on_this_one(isolate_state):
    """regeneration_easy is on Wednesday, not Tuesday."""
    raw_before = isolate_state.read_bytes()
    r = client.post("/api/feedback", json=_feedback("regeneration_easy"))
    _assert_refused(r, isolate_state, raw_before, sid="regeneration_easy")


def test_a_skipped_session_is_not_in_the_plan(isolate_state):
    """mark_skipped leaves a regeneration_easy stub with skipped_session_id."""
    def skip(state):
        wp = apply_events(state["current_week_plan"], [
            {"event_type": "mark_skipped", "date": TUE, "session_ref": "strength_long", "slot": "evening"}])
        state["current_week_plan"] = wp
        state["week_plans"][MON] = deepcopy(wp)
    _save(skip)
    stub = next(s for s in deps.load_state(None)["current_week_plan"]["weeks"][0]["days"][1]["sessions"]
                if s.get("slot") == "evening")
    assert (stub["status"], stub["skipped_session_id"]) == ("skipped", "strength_long")
    raw_before = isolate_state.read_bytes()
    r = client.post("/api/feedback", json=_feedback("strength_long"))
    _assert_refused(r, isolate_state, raw_before, sid="strength_long")


def test_the_stub_of_a_skipped_regeneration_easy_is_not_the_session(isolate_state):
    """Skipping regeneration_easy leaves a stub with the same session_id: the
    stub stands for the skip, it is not the session."""
    def skip(state):
        wp = apply_events(state["current_week_plan"], [
            {"event_type": "mark_skipped", "date": WED, "session_ref": "regeneration_easy"}])
        state["current_week_plan"] = wp
        state["week_plans"][MON] = deepcopy(wp)
    _save(skip)
    stub = deps.load_state(None)["current_week_plan"]["weeks"][0]["days"][2]["sessions"][0]
    assert (stub["session_id"], stub["status"], stub["skipped_session_id"]) == (
        "regeneration_easy", "skipped", "regeneration_easy")
    raw_before = isolate_state.read_bytes()
    r = client.post("/api/feedback", json=_feedback("regeneration_easy", WED))
    _assert_refused(r, isolate_state, raw_before, sid="regeneration_easy", day=WED)


def test_b216_rollover_onto_a_week_without_the_session(isolate_state):
    """current_week_plan is last week: the plan that counts is week_plans[monday]."""
    def roll(state):
        prev = _plan(PREV, ("2026-03-09", "2026-03-10", "2026-03-11"))
        state["current_week_plan"] = prev
        state["week_plans"][PREV] = deepcopy(prev)
    _save(roll)
    raw_before = isolate_state.read_bytes()
    r = client.post("/api/feedback", json=_feedback("treadmill_hiit_4x4"))
    _assert_refused(r, isolate_state, raw_before, sid="treadmill_hiit_4x4")


def test_without_current_week_plan_the_cached_week_still_counts(isolate_state):
    _save(lambda state: state.update(current_week_plan=None))
    raw_before = isolate_state.read_bytes()
    r = client.post("/api/feedback", json=_feedback("treadmill_hiit_4x4"))
    _assert_refused(r, isolate_state, raw_before, sid="treadmill_hiit_4x4")


def test_the_check_refuses_before_the_ladder_archive_read(isolate_state, monkeypatch):
    """Nothing remote is read for a request that is refused anyway."""
    def boom(*a, **k):
        raise AssertionError("ladder archive read on a refused feedback")

    monkeypatch.setattr(feedback_router._ladder_archive, "load", boom)
    raw_before = isolate_state.read_bytes()
    r = client.post("/api/feedback", json=_feedback("treadmill_hiit_4x4"))
    _assert_refused(r, isolate_state, raw_before, sid="treadmill_hiit_4x4")


def test_backstop_apply_events_refusal_is_the_same_409(isolate_state, monkeypatch):
    """If the check ever let an orphan through, the inline mark_done's
    SessionNotInPlan answers the same 409 — still nothing written."""
    monkeypatch.setattr(feedback_router, "session_not_in_plan", lambda *a, **k: None)
    raw_before = isolate_state.read_bytes()
    r = client.post("/api/feedback", json=_feedback("treadmill_hiit_4x4"))
    detail = _assert_refused(r, isolate_state, raw_before, sid="treadmill_hiit_4x4")
    assert [s["session_id"] for s in detail["day_sessions"]] == ["custom_cs_320de282", "strength_long"]


def test_backstop_on_the_b216_retry_is_the_same_409(isolate_state, monkeypatch):
    def roll(state):
        prev = _plan(PREV, ("2026-03-09", "2026-03-10", "2026-03-11"))
        state["current_week_plan"] = prev
        state["week_plans"][PREV] = deepcopy(prev)
    _save(roll)
    monkeypatch.setattr(feedback_router, "session_not_in_plan", lambda *a, **k: None)
    raw_before = isolate_state.read_bytes()
    r = client.post("/api/feedback", json=_feedback("treadmill_hiit_4x4"))
    _assert_refused(r, isolate_state, raw_before, sid="treadmill_hiit_4x4")


# ---------------------------------------------------------------------------
# 200 — unchanged
# ---------------------------------------------------------------------------

def test_a_session_in_the_plan_is_logged_as_before(isolate_state):
    r = client.post("/api/feedback", json=_feedback("custom_cs_320de282"))
    assert r.status_code == 200, r.text
    after = deps.load_state(None)
    sess = after["current_week_plan"]["weeks"][0]["days"][1]["sessions"][0]
    assert sess["status"] == "done"
    assert any(e["date"] == TUE and e["session_id"] == "custom_cs_320de282"
               for e in after["session_completion_log"])
    # The played Monday is byte-identical.
    assert json.dumps(after["week_plans"][MON]["weeks"][0]["days"][0], sort_keys=True) == \
        json.dumps(_plan()["weeks"][0]["days"][0], sort_keys=True)


def test_an_already_done_session_stays_200_and_idempotent(isolate_state):
    """The /today flow marks it through /events first; the coach re-sends
    /feedback on a played session (B197): both stay 200."""
    r = client.post("/api/feedback", json=_feedback("strength_long", MON))
    assert r.status_code == 200, r.text
    r2 = client.post("/api/feedback", json=_feedback("strength_long", MON))
    assert r2.status_code == 200, r2.text
    log = deps.load_state(None)["session_completion_log"]
    assert sum(1 for e in log if e["date"] == MON and e["session_id"] == "strength_long") == 1


def test_done_in_the_cached_copy_only_stays_200(isolate_state):
    """Already done in week_plans[monday] while the legacy pointer lags: the
    pre-B414 skip of the inline mark_done, unchanged."""
    def lag(state):
        cwp = state["current_week_plan"]
        cwp["weeks"][0]["days"][1]["sessions"] = cwp["weeks"][0]["days"][1]["sessions"][1:]
        state["week_plans"][MON]["weeks"][0]["days"][1]["sessions"][0]["status"] = "done"
    _save(lag)
    r = client.post("/api/feedback", json=_feedback("custom_cs_320de282"))
    assert r.status_code == 200, r.text


def test_b216_rollover_onto_a_session_that_is_there(isolate_state):
    def roll(state):
        prev = _plan(PREV, ("2026-03-09", "2026-03-10", "2026-03-11"))
        state["current_week_plan"] = prev
        state["week_plans"][PREV] = deepcopy(prev)
    _save(roll)
    r = client.post("/api/feedback", json=_feedback("custom_cs_320de282"))
    assert r.status_code == 200, r.text
    sess = deps.load_state(None)["week_plans"][MON]["weeks"][0]["days"][1]["sessions"][0]
    assert sess["status"] == "done"


def test_a_date_no_stored_plan_covers_stays_200(isolate_state):
    """An archived week (or a date outside every stored plan): as before."""
    r = client.post("/api/feedback", json=_feedback("treadmill_hiit_4x4", "2026-02-10"))
    assert r.status_code == 200, r.text
    assert any(e["date"] == "2026-02-10" and e["session_id"] == "treadmill_hiit_4x4"
               for e in deps.load_state(None)["session_completion_log"])


def test_no_plan_at_all_stays_200(isolate_state):
    _save(lambda state: state.update(current_week_plan=None, week_plans={}))
    r = client.post("/api/feedback", json=_feedback("treadmill_hiit_4x4"))
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# The check and the inline mark_done agree (same predicate)
# ---------------------------------------------------------------------------

CANDIDATES = ["strength_long", "custom_cs_320de282", "regeneration_easy", "treadmill_hiit_4x4"]


@pytest.mark.parametrize("day", [TUE, WED])
@pytest.mark.parametrize("sid", CANDIDATES)
def test_check_passes_exactly_when_mark_done_finds_the_session(day, sid):
    """Every pass of the check is a mark_done apply_events accepts, and every
    refusal one it would refuse (the 409 is never stricter or looser than the
    write it protects — the stub exclusion apart, tested above)."""
    plan = _plan()
    state = {"current_week_plan": deepcopy(plan), "week_plans": {MON: deepcopy(plan)}}
    refused = feedback_router.session_not_in_plan(state, day, sid) is not None
    try:
        apply_events(deepcopy(plan), [{"event_type": "mark_done", "date": day, "session_ref": sid}])
        engine_refused = False
    except SessionNotInPlan:
        engine_refused = True
    assert refused == engine_refused
