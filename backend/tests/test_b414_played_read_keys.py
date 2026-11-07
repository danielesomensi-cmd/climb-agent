"""B414 — PLAYED-SESSION-READ-KEYS: the read-time keys of a played session
never land in the stored record, and the write responses carry them like GET.

GET /api/week attaches, on a copy, the A141 ``process_cue`` (every session)
and — on a done session, from ``feedback_log`` — ``feedback_summary``,
``exercise_feedback`` and ``session_duration_seconds``. The client sends the
whole week back to /events (and the other client-plan writers), and B371's
``strip_derived`` used to leave a played session exactly as sent: the copies
were saved into the record. ``session_duration_seconds`` is ALSO a real field
of the record (``/feedback`` step 4b keeps the max of every resubmit), so the
fix restores each of the four keys from the stored played twin (removed when
the twin has none) instead of dropping them — the stored duration always wins.

And ``read_view`` (the plan every write endpoint returns) now attaches the
pills and the cue as GET does: before, a tap on /today wiped them from the
screen until the next GET.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.api.plan_revision import read_view, strip_derived

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"

READ_KEYS = ("process_cue", "feedback_summary", "exercise_feedback", "session_duration_seconds")


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    shutil.copy2(REAL_STATE_PATH, tmp_state)
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    state = deps.load_state(None)
    state["macrocycle"]["start_date"] = _monday(-1)
    state["macrocycle"].pop("pause", None)
    phases = state["macrocycle"].get("phases") or []
    phases[0]["duration_weeks"] = max(phases[0].get("duration_weeks", 1), 6)
    state["week_plans"] = {}
    state["current_week_plan"] = None
    state.pop("_prev_week_plan", None)
    state.pop("weekly_overrides", None)
    state["feedback_log"] = []
    deps.save_state(state, None)
    yield tmp_state


def _monday(offset_weeks: int = 0) -> str:
    today = date.today()
    return (today - timedelta(days=today.weekday()) + timedelta(weeks=offset_weeks)).isoformat()


# ---------------------------------------------------------------------------
# strip_derived (unit)
# ---------------------------------------------------------------------------

def _done(sid="strength_long", slot="evening", **extra):
    return {"session_id": sid, "slot": slot, "status": "done",
            "actual_exercises": [{"exercise_id": "max_hang_7s", "completed": True}], **extra}


def _plan(*days):
    return {"start_date": "2026-10-12", "weeks": [{"days": [
        {"date": d, "sessions": ss} for d, ss in days]}]}


def test_played_with_twin_takes_the_four_keys_from_the_stored_twin():
    stored = _plan(("2026-10-12", [_done(session_duration_seconds=3600)]))
    client_plan = deepcopy(stored)
    s = client_plan["weeks"][0]["days"][0]["sessions"][0]
    # What GET put on the copy at read (feedback_log may hold a shorter
    # duration than the stored max).
    s.update({"process_cue": "breathe", "feedback_summary": "hard",
              "exercise_feedback": {"max_hang_7s": "hard"}, "session_duration_seconds": 1200})
    s["actual_exercises"][0]["note"] = "client field kept"

    strip_derived(client_plan, stored)

    s = client_plan["weeks"][0]["days"][0]["sessions"][0]
    for k in ("process_cue", "feedback_summary", "exercise_feedback"):
        assert k not in s, k
    assert s["session_duration_seconds"] == 3600, "the stored duration wins"
    # Every other field of a played session stays as sent (as before B414).
    assert s["actual_exercises"][0]["note"] == "client field kept"


def test_stored_duration_is_restored_when_the_client_dropped_it():
    stored = _plan(("2026-10-12", [_done(session_duration_seconds=3600)]))
    client_plan = deepcopy(stored)
    client_plan["weeks"][0]["days"][0]["sessions"][0].pop("session_duration_seconds")
    strip_derived(client_plan, stored)
    assert client_plan["weeks"][0]["days"][0]["sessions"][0]["session_duration_seconds"] == 3600


def test_a_stored_key_is_kept_with_its_stored_value():
    """A record that already carries a key (an old save) keeps it: restored,
    never deleted."""
    stored = _plan(("2026-10-12", [_done(feedback_summary="ok", session_duration_seconds=10)]))
    client_plan = deepcopy(stored)
    client_plan["weeks"][0]["days"][0]["sessions"][0]["feedback_summary"] = "very_hard"
    strip_derived(client_plan, stored)
    s = client_plan["weeks"][0]["days"][0]["sessions"][0]
    assert s["feedback_summary"] == "ok" and s["session_duration_seconds"] == 10


def test_twins_matched_in_order_on_date_slot_session_id():
    stored = _plan(("2026-10-12", [_done(session_duration_seconds=100), _done(session_duration_seconds=200)]))
    client_plan = deepcopy(stored)
    for s in client_plan["weeks"][0]["days"][0]["sessions"]:
        s["session_duration_seconds"] = 5
    strip_derived(client_plan, stored)
    assert [s["session_duration_seconds"] for s in client_plan["weeks"][0]["days"][0]["sessions"]] == [100, 200]


def test_played_without_twin_only_loses_the_cue():
    """A client from before B371 whose plan diverged: no stored played twin
    (the stored one is still pending) → only the always-recomputed cue goes."""
    stored = _plan(("2026-10-12", [{"session_id": "strength_long", "slot": "evening"}]))
    client_plan = _plan(("2026-10-12", [_done(process_cue="x", feedback_summary="hard",
                                              session_duration_seconds=77)]))
    strip_derived(client_plan, stored)
    s = client_plan["weeks"][0]["days"][0]["sessions"][0]
    assert "process_cue" not in s
    assert s["feedback_summary"] == "hard" and s["session_duration_seconds"] == 77


def test_skipped_session_follows_the_same_rule():
    stored = _plan(("2026-10-12", [{"session_id": "regeneration_easy", "slot": "evening", "status": "skipped",
                                    "skipped_session_id": "strength_long"}]))
    client_plan = deepcopy(stored)
    client_plan["weeks"][0]["days"][0]["sessions"][0]["process_cue"] = "c"
    strip_derived(client_plan, stored)
    assert client_plan == stored


def test_pending_sessions_unchanged():
    stored = _plan(("2026-10-12", [{"session_id": "strength_long", "slot": "evening",
                                    "session_duration_seconds": 9}]))
    client_plan = deepcopy(stored)
    client_plan["weeks"][0]["days"][0]["sessions"][0]["process_cue"] = "c"
    strip_derived(client_plan, stored)
    assert client_plan == stored


# ---------------------------------------------------------------------------
# read_view (unit)
# ---------------------------------------------------------------------------

def test_read_view_attaches_pills_and_cue_on_a_copy_deterministically():
    state = deps.load_state(None)
    plan = _plan(("2026-10-12", [_done(session_duration_seconds=3600)]),
                 ("2026-10-13", [{"session_id": "strength_long", "slot": "evening"}]))
    state["feedback_log"] = [{"date": "2026-10-12", "session_id": "strength_long", "difficulty": "hard",
                              "exercise_feedback": {"max_hang_7s": "hard"}, "session_duration_seconds": 3000}]
    raw = deepcopy(plan)
    v1 = read_view(plan, state, user_id="u1")
    v2 = read_view(plan, state, user_id="u1")
    assert v1 == v2, "deterministic"
    assert plan == raw, "the stored plan stays raw"
    done = v1["weeks"][0]["days"][0]["sessions"][0]
    assert done["feedback_summary"] == "hard"
    assert done["exercise_feedback"] == {"max_hang_7s": "hard"}
    # Exactly what GET shows (B32: the feedback_log value).
    assert done["session_duration_seconds"] == 3000
    from backend.api.routers.week import _attach_feedback, _attach_process_cues

    get_view = deepcopy(raw)
    _attach_feedback(get_view, state["feedback_log"])
    _attach_process_cues(get_view, "u1")
    for d_view, d_get in zip(v1["weeks"][0]["days"], get_view["weeks"][0]["days"]):
        for s_view, s_get in zip(d_view["sessions"], d_get["sessions"]):
            for k in READ_KEYS:
                assert s_view.get(k) == s_get.get(k), k


def test_read_view_never_attaches_feedback_to_a_pending_session():
    state = deps.load_state(None)
    state["feedback_log"] = [{"date": "2026-10-13", "session_id": "strength_long", "difficulty": "hard"}]
    plan = _plan(("2026-10-13", [{"session_id": "strength_long", "slot": "evening"}]))
    assert "feedback_summary" not in read_view(plan, state)["weeks"][0]["days"][0]["sessions"][0]


# ---------------------------------------------------------------------------
# End to end: feedback → GET (with the keys) → /events on another session
# ---------------------------------------------------------------------------

def _next_week():
    wn = client.get("/api/week/0").json()["week_num"]
    r = client.get(f"/api/week/{wn + 1}")
    assert r.status_code == 200, r.text
    return wn + 1, r.json()["week_plan"]


def _pending(plan):
    out = []
    for d in plan["weeks"][0]["days"]:
        for s in d.get("sessions") or []:
            if s.get("status") not in ("done", "skipped") and s.get("resolved"):
                out.append((d["date"], s))
    return out


def _session(plan, day, sid, slot):
    d = next(x for x in plan["weeks"][0]["days"] if x["date"] == day)
    return next(s for s in d["sessions"] if s.get("session_id") == sid and s.get("slot") == slot)


def test_feedback_get_then_events_keeps_the_record_clean_and_the_view_full():
    wn, plan = _next_week()
    pending = _pending(plan)
    assert len(pending) >= 2, "the generated week needs two sessions"
    (day, sess), (other_day, other) = pending[0], pending[1]
    sid, slot = sess["session_id"], sess["slot"]
    ids = [i["exercise_id"] for i in sess["resolved"]["resolved_session"]["exercise_instances"]]
    items = [{"exercise_id": ex, "feedback_label": "hard", "completed": True} for ex in ids]
    r = client.post("/api/feedback", json={"log_entry": {
        "date": day, "session_id": sid, "session_duration_seconds": 3600,
        "actual": {"exercise_feedback_v1": items}}, "status": "done"})
    assert r.status_code == 200, r.text
    # A shorter resubmit never lowers the stored duration (B197).
    r = client.post("/api/feedback", json={"log_entry": {
        "date": day, "session_id": sid, "session_duration_seconds": 30,
        "actual": {"exercise_feedback_v1": items}}, "status": "done"})
    assert r.status_code == 200, r.text
    start = _monday(1)
    stored_played = deepcopy(_session(deps.load_state(None)["week_plans"][start], day, sid, slot))
    assert stored_played["status"] == "done"
    assert stored_played["session_duration_seconds"] == 3600
    for k in ("process_cue", "feedback_summary", "exercise_feedback"):
        assert k not in stored_played

    got = client.get(f"/api/week/{wn}").json()["week_plan"]
    shown = _session(got, day, sid, slot)
    assert shown.get("feedback_summary") == "hard"
    assert shown.get("exercise_feedback")
    # The view carries what GET attaches; sent back as is.
    shown["session_duration_seconds"] = 5
    r = client.post("/api/replanner/events", json={
        "events": [{"event_type": "mark_done", "date": other_day, "session_ref": other["session_id"],
                    "slot": other["slot"]}],
        "week_plan": got, "base_revision": got["plan_revision"]})
    assert r.status_code == 200, r.text

    saved = _session(deps.load_state(None)["week_plans"][start], day, sid, slot)
    for k in ("process_cue", "feedback_summary", "exercise_feedback"):
        assert k not in saved, k
    assert saved["session_duration_seconds"] == 3600, "the stored duration wins over the client copy"
    # Immutability: the played record is byte-identical to before the /events.
    assert json.dumps(saved, sort_keys=True) == json.dumps(stored_played, sort_keys=True)

    # The response is GET's view: the pills and the cue are still there.
    view = _session(r.json()["week_plan"], day, sid, slot)
    assert view.get("feedback_summary") == "hard"
    assert view.get("exercise_feedback") == shown["exercise_feedback"]
    if shown.get("process_cue"):
        assert view.get("process_cue") == shown["process_cue"]
    after_get = client.get(f"/api/week/{wn}").json()["week_plan"]
    for k in READ_KEYS:
        assert view.get(k) == _session(after_get, day, sid, slot).get(k), k
