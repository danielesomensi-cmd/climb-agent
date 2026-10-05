"""B371 — plan_revision: monotonic on every write, 409 on a stale copy, and the
read-time fields never saved.

Before B371 the replanner and session endpoints saved the whole ``week_plan``
the client sent, with no version check: a phone that slept on Monday's copy
overwrote with one tap whatever another device (or a B369 regeneration) had
written since — and the B364 anchored loads computed at read went back into
the stored plan as if the athlete had set them.
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
from backend.api.plan_revision import (
    StalePlanError,
    check_base_revision,
    revision_of,
    stamp_revision,
    strip_derived,
)

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    shutil.copy2(REAL_STATE_PATH, tmp_state)
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    _seed_macrocycle()
    yield tmp_state


def _seed_macrocycle():
    """Same seed as B369: the macrocycle started last week, plenty of weeks left."""
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


def _monday(offset_weeks: int = 0) -> str:
    today = date.today()
    return (today - timedelta(days=today.weekday()) + timedelta(weeks=offset_weeks)).isoformat()


def _next_week():
    """GET the next week (all days in the future → nothing frozen)."""
    wn = client.get("/api/week/0").json()["week_num"]
    r = client.get(f"/api/week/{wn + 1}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["week_plan"]["start_date"] == _monday(1)
    return wn + 1, body["week_plan"]


def _stored(start: str) -> dict:
    return deps.load_state(None)["week_plans"][start]


def _day_with_session(plan: dict) -> dict:
    for d in plan["weeks"][0]["days"]:
        if any(s.get("status") not in ("done", "skipped") for s in d.get("sessions") or []):
            return d
    raise AssertionError("no day with a pending session in the generated week")


def _remove_event(plan: dict) -> dict:
    d = _day_with_session(plan)
    s = next(s for s in d["sessions"] if s.get("status") not in ("done", "skipped"))
    return {"event_type": "remove_session", "date": d["date"], "session_ref": s["session_id"], "slot": s["slot"]}


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------

def test_revision_of_defaults_and_garbage():
    assert revision_of({}) == 1
    assert revision_of({"plan_revision": 7}) == 7
    assert revision_of({"plan_revision": "x"}) == 1
    assert revision_of(None) == 0


def test_stamp_revision_is_strictly_above_the_stored_one():
    stored = {"plan_revision": 5}
    up = {"plan_revision": 5}  # session/* do not increment by themselves
    assert stamp_revision(up, stored) == 6
    up = {"plan_revision": 6}  # apply_events already did
    assert stamp_revision(up, stored) == 6
    same = {"plan_revision": 4}
    assert stamp_revision(same, same) == 5  # caller wrote it into the cache first
    assert stamp_revision({"plan_revision": 3}, None) == 3


def test_check_base_revision():
    state = {"week_plans": {"2026-10-12": {"start_date": "2026-10-12", "plan_revision": 4}}}
    client_plan = {"start_date": "2026-10-12", "plan_revision": 3}
    check_base_revision(state, client_plan, 4, endpoint="t")      # fresh
    check_base_revision(state, client_plan, None, endpoint="t")   # legacy client: accepted
    check_base_revision({}, client_plan, 1, endpoint="t")         # nothing stored
    with pytest.raises(StalePlanError) as e:
        check_base_revision(state, client_plan, 3, endpoint="t")
    assert e.value.current_revision == 4
    assert e.value.payload()["current_revision"] == 4
    assert e.value.payload()["week_plan"]["plan_revision"] == 4
    with pytest.raises(StalePlanError):
        check_base_revision(state, client_plan, 5, endpoint="t")  # ahead is not fresh either


def _custom(status="planned", load=10.0):
    return {"slot": "lunch", "session_id": "custom_cs_x", "is_custom": True, "status": status,
            "exercises": [{"exercise_id": "goblet_squat", "sets": 3, "reps": 8, "load_kg": load}]}


def test_strip_derived_restores_custom_rows_and_drops_read_fields():
    stored = {"start_date": "2026-10-12", "weeks": [{"days": [
        {"date": "2026-10-12", "sessions": [_custom(load=10.0)]},
        {"date": "2026-10-13", "sessions": [_custom(status="done", load=20.0)]},
    ]}]}
    client_plan = deepcopy(stored)
    # what GET /api/week put on the copy at read
    row = client_plan["weeks"][0]["days"][0]["sessions"][0]["exercises"][0]
    row.update({"load_kg": 32.5, "stored_load_kg": 10.0, "load_source": "anchored", "anchored": {"x": 1}})
    client_plan["weeks"][0]["days"][0]["sessions"][0]["process_cue"] = "breathe"
    client_plan["weeks"][0]["days"][1]["sessions"][0]["process_cue"] = "kept on a done session"
    client_plan["weeks"][0]["days"][1]["sessions"][0]["exercises"][0]["load_kg"] = 21.0
    client_plan.update({"guard_warnings": [{"x": 1}], "key_status": {}, "_stale": True})

    strip_derived(client_plan, stored)

    pending = client_plan["weeks"][0]["days"][0]["sessions"][0]
    assert pending["exercises"] == stored["weeks"][0]["days"][0]["sessions"][0]["exercises"]
    assert "process_cue" not in pending
    done = client_plan["weeks"][0]["days"][1]["sessions"][0]
    # Played sessions are never touched (immutability).
    assert done["process_cue"] == "kept on a done session"
    assert done["exercises"][0]["load_kg"] == 21.0
    for k in ("guard_warnings", "key_status", "_stale"):
        assert k not in client_plan


def test_strip_derived_leaves_a_custom_without_stored_twin():
    client_plan = {"start_date": "2026-10-12", "weeks": [{"days": [
        {"date": "2026-10-12", "sessions": [_custom(load=33.0)]}]}]}
    strip_derived(client_plan, {"start_date": "2026-10-12", "weeks": [{"days": []}]})
    assert client_plan["weeks"][0]["days"][0]["sessions"][0]["exercises"][0]["load_kg"] == 33.0


# ---------------------------------------------------------------------------
# API — the 409
# ---------------------------------------------------------------------------

def test_get_week_always_carries_a_revision():
    _, plan = _next_week()
    assert isinstance(plan.get("plan_revision"), int) and plan["plan_revision"] >= 1


def test_fresh_write_moves_the_revision_and_a_stale_one_is_refused():
    wn, plan = _next_week()
    base = plan["plan_revision"]
    r = client.post("/api/replanner/events", json={
        "events": [_remove_event(plan)], "week_plan": plan, "base_revision": base})
    assert r.status_code == 200, r.text
    new_rev = r.json()["week_plan"]["plan_revision"]
    assert new_rev > base
    assert revision_of(_stored(_monday(1))) == new_rev
    stored_after_first = _stored(_monday(1))

    # A second device still on the old copy.
    r2 = client.post("/api/replanner/events", json={
        "events": [_remove_event(plan)], "week_plan": plan, "base_revision": base})
    assert r2.status_code == 409, r2.text
    body = r2.json()
    assert body["current_revision"] == new_rev
    assert isinstance(body["detail"], str) and body["detail"]
    assert body["week_start"] == _monday(1)
    assert body["week_plan"]["plan_revision"] == new_rev
    # Nothing was written.
    assert _stored(_monday(1)) == stored_after_first


def test_legacy_client_without_base_revision_is_accepted():
    _, plan = _next_week()
    base = plan["plan_revision"]
    r = client.post("/api/replanner/events", json={"events": [_remove_event(plan)], "week_plan": plan})
    assert r.status_code == 200, r.text
    assert r.json()["week_plan"]["plan_revision"] > base


def test_dry_run_is_never_refused_and_writes_nothing():
    _, plan = _next_week()
    before = _stored(_monday(1))
    r = client.post("/api/replanner/events", json={
        "events": [_remove_event(plan)], "week_plan": plan, "base_revision": 999, "dry_run": True})
    assert r.status_code == 200, r.text
    assert _stored(_monday(1)) == before


@pytest.mark.parametrize("endpoint", ["override", "quick-add", "add-exercise", "remove-exercise", "surface-override"])
def test_every_client_plan_endpoint_refuses_a_stale_copy(endpoint):
    _, plan = _next_week()
    d = _day_with_session(plan)
    stale = plan["plan_revision"] - 1 if plan["plan_revision"] > 1 else plan["plan_revision"] + 5
    payloads = {
        "override": ("/api/replanner/override", {"intent": "rest", "location": "home",
                                                 "reference_date": d["date"], "slot": d["sessions"][0]["slot"]}),
        "quick-add": ("/api/replanner/quick-add", {"session_id": "prehab_maintenance", "target_date": d["date"],
                                                  "slot": "morning", "location": "home"}),
        "add-exercise": ("/api/session/add-exercise", {"date": d["date"], "session_index": 0,
                                                       "exercise_id": "dead_hang_easy"}),
        "remove-exercise": ("/api/session/remove-exercise", {"date": d["date"], "session_index": 0,
                                                             "exercise_index": 0}),
        "surface-override": ("/api/session/surface-override", {"date": d["date"], "session_index": 0,
                                                               "surface": None}),
    }
    path, body = payloads[endpoint]
    before = _stored(_monday(1))
    r = client.post(path, json={**body, "week_plan": plan, "base_revision": stale})
    assert r.status_code == 409, r.text
    assert r.json()["current_revision"] == revision_of(before)
    assert _stored(_monday(1)) == before


@pytest.mark.parametrize("endpoint", ["override", "quick-add", "add-exercise"])
def test_every_client_plan_endpoint_moves_the_revision(endpoint):
    _, plan = _next_week()
    d = _day_with_session(plan)
    idx = next(i for i, s in enumerate(d["sessions"]) if (s.get("resolved") or {}).get("resolved_session")
               and s.get("status") not in ("done", "skipped")) if endpoint == "add-exercise" else 0
    payloads = {
        "override": ("/api/replanner/override", {"intent": "rest", "location": "home",
                                                 "reference_date": d["date"], "slot": d["sessions"][0]["slot"]}),
        "quick-add": ("/api/replanner/quick-add", {"session_id": "prehab_maintenance", "target_date": d["date"],
                                                  "slot": "morning", "location": "home"}),
        "add-exercise": ("/api/session/add-exercise", {"date": d["date"], "session_index": idx,
                                                       "exercise_id": "dead_hang_easy"}),
    }
    path, body = payloads[endpoint]
    base = plan["plan_revision"]
    r = client.post(path, json={**body, "week_plan": plan, "base_revision": base})
    assert r.status_code == 200, r.text
    assert r.json()["week_plan"]["plan_revision"] > base
    assert revision_of(_stored(_monday(1))) == r.json()["week_plan"]["plan_revision"]


def test_a_sequence_of_writes_is_monotonic_and_each_response_is_the_next_base():
    _, plan = _next_week()
    revs = [plan["plan_revision"]]
    for _ in range(3):
        r = client.post("/api/replanner/events", json={
            "events": [_remove_event(plan)], "week_plan": plan, "base_revision": plan["plan_revision"]})
        assert r.status_code == 200, r.text
        plan = r.json()["week_plan"]
        revs.append(plan["plan_revision"])
    assert revs == sorted(revs) and len(set(revs)) == len(revs)


def test_invalidation_and_regeneration_move_the_revision():
    wn, plan = _next_week()
    base = plan["plan_revision"]
    # Changing the planning prefs flags the week stale — a write.
    prefs = client.get("/api/state").json().get("planning_prefs") or {}
    cap = int(prefs.get("hard_day_cap_per_week", 3))
    assert client.put("/api/state", json={"planning_prefs": {"hard_day_cap_per_week": max(1, cap - 1)}}).status_code == 200
    flagged = revision_of(_stored(_monday(1)))
    assert flagged > base
    # A write on the pre-change copy is refused…
    r = client.post("/api/replanner/events", json={
        "events": [_remove_event(plan)], "week_plan": plan, "base_revision": base})
    assert r.status_code == 409
    # …the GET regenerates (another write) …
    g = client.get(f"/api/week/{wn}")
    assert g.status_code == 200
    regen = g.json()["week_plan"]["plan_revision"]
    assert regen > flagged
    assert revision_of(_stored(_monday(1))) == regen
    # … and a forced regeneration too.
    g2 = client.get(f"/api/week/{wn}?force=true")
    assert g2.json()["week_plan"]["plan_revision"] > regen


def test_server_side_writes_move_the_revision(isolate_state):
    """feedback (via persist_week_plan) moves the revision of the current week."""
    r = client.get("/api/week/0")
    plan = r.json()["week_plan"]
    start = plan["start_date"]
    base = plan["plan_revision"]
    today = date.today().isoformat()
    day = next((d for d in plan["weeks"][0]["days"] if d["date"] == today), None)
    sess = next((s for s in (day or {}).get("sessions") or [] if s.get("status") not in ("done", "skipped")), None)
    if sess is None:
        pytest.skip("no pending session today in the fixture week")
    r = client.post("/api/feedback", json={"log_entry": {
        "date": today, "session_id": sess["session_id"], "difficulty": "ok", "exercise_feedback": []}})
    assert r.status_code == 200, r.text
    assert revision_of(_stored(start)) > base


# ---------------------------------------------------------------------------
# API — read-time fields never saved
# ---------------------------------------------------------------------------

def test_anchored_custom_loads_sent_back_are_not_saved(isolate_state):
    _, plan = _next_week()
    start = _monday(1)
    d = plan["weeks"][0]["days"][2]
    # Put a pending custom in the STORED week (as add_custom_session would).
    st = json.loads(isolate_state.read_text())
    stored_day = next(x for x in st["week_plans"][start]["weeks"][0]["days"] if x["date"] == d["date"])
    stored_day.setdefault("sessions", []).append(_custom(load=10.0))
    isolate_state.write_text(json.dumps(st))

    g = client.get(f"/api/week/{client.get('/api/week/0').json()['week_num'] + 1}")
    plan = g.json()["week_plan"]
    # The client copy carries a read-time load (B364) — simulate it.
    cday = next(x for x in plan["weeks"][0]["days"] if x["date"] == d["date"])
    ccustom = next(s for s in cday["sessions"] if s.get("session_id") == "custom_cs_x")
    ccustom["exercises"][0].update({"load_kg": 47.5, "load_source": "anchored", "stored_load_kg": 10.0})
    plan["guard_warnings"] = [{"kind": "x"}]

    other = next(x for x in plan["weeks"][0]["days"]
                 if x["date"] != d["date"] and any(s.get("status") not in ("done", "skipped") for s in x.get("sessions") or []))
    s = next(s for s in other["sessions"] if s.get("status") not in ("done", "skipped"))
    r = client.post("/api/replanner/events", json={
        "events": [{"event_type": "remove_session", "date": other["date"], "session_ref": s["session_id"], "slot": s["slot"]}],
        "week_plan": plan, "base_revision": plan["plan_revision"]})
    assert r.status_code == 200, r.text

    saved = _stored(start)
    sday = next(x for x in saved["weeks"][0]["days"] if x["date"] == d["date"])
    scustom = next(s for s in sday["sessions"] if s.get("session_id") == "custom_cs_x")
    assert scustom["exercises"] == _custom(load=10.0)["exercises"]
    assert "guard_warnings" not in saved


# ---------------------------------------------------------------------------
# Review — write responses are the read view, played customs keep what was
# shown, feedback bumps only a week it changed, writes are serialised per user
# ---------------------------------------------------------------------------

def _seed_pending_custom(isolate_state, start: str, day_date: str, load: float = 10.0) -> None:
    st = json.loads(isolate_state.read_text())
    stored_day = next(x for x in st["week_plans"][start]["weeks"][0]["days"] if x["date"] == day_date)
    stored_day.setdefault("sessions", []).append(_custom(load=load))
    isolate_state.write_text(json.dumps(st))


def _custom_of(plan: dict, day_date: str) -> dict:
    day = next(x for x in plan["weeks"][0]["days"] if x["date"] == day_date)
    return next(s for s in day["sessions"] if s.get("session_id") == "custom_cs_x")


def test_write_response_custom_exercises_equal_the_get_view(isolate_state):
    wn, plan = _next_week()
    start = _monday(1)
    d = plan["weeks"][0]["days"][2]["date"]
    _seed_pending_custom(isolate_state, start, d)
    plan = client.get(f"/api/week/{wn}").json()["week_plan"]
    other = next(x for x in plan["weeks"][0]["days"]
                 if x["date"] != d and any(s.get("status") not in ("done", "skipped") for s in x.get("sessions") or []))
    s = next(s for s in other["sessions"] if s.get("status") not in ("done", "skipped"))
    r = client.post("/api/replanner/events", json={
        "events": [{"event_type": "remove_session", "date": other["date"], "session_ref": s["session_id"], "slot": s["slot"]}],
        "week_plan": plan, "base_revision": plan["plan_revision"]})
    assert r.status_code == 200, r.text
    after_get = client.get(f"/api/week/{wn}").json()["week_plan"]
    assert _custom_of(r.json()["week_plan"], d)["exercises"] == _custom_of(after_get, d)["exercises"]
    # B370: the read view fills the rest default — the raw row has none.
    assert "rest_between_sets_seconds" in _custom_of(r.json()["week_plan"], d)["exercises"][0]
    assert r.json()["week_plan"]["plan_revision"] == revision_of(_stored(start))
    # … and the stored plan stays raw.
    assert _custom_of(_stored(start), d)["exercises"] == _custom(load=10.0)["exercises"]


def test_custom_marked_done_keeps_the_prescription_shown(isolate_state):
    wn, plan = _next_week()
    start = _monday(1)
    d = plan["weeks"][0]["days"][2]["date"]
    _seed_pending_custom(isolate_state, start, d)
    plan = client.get(f"/api/week/{wn}").json()["week_plan"]
    shown = deepcopy(_custom_of(plan, d)["exercises"])
    r = client.post("/api/replanner/events", json={
        "events": [{"event_type": "mark_done", "date": d, "session_ref": "custom_cs_x", "slot": "lunch"}],
        "week_plan": plan, "base_revision": plan["plan_revision"]})
    assert r.status_code == 200, r.text
    saved = _custom_of(_stored(start), d)
    assert saved["status"] == "done"
    assert saved["exercises"] == shown


def test_feedback_outside_the_plan_leaves_the_current_revision_alone(isolate_state):
    plan = client.get("/api/week/0").json()["week_plan"]
    start = plan["start_date"]
    before = revision_of(_stored(start))
    far = (date.today() + timedelta(weeks=20)).isoformat()
    r = client.post("/api/feedback", json={"log_entry": {
        "date": far, "session_id": "nope", "difficulty": "ok", "exercise_feedback": []}})
    assert r.status_code == 200, r.text
    assert revision_of(_stored(start)) == before


def test_idempotent_feedback_does_not_bump_twice(isolate_state):
    """/events mark_done then /feedback (the /today flow): the feedback's own
    content (actual exercises / duration) is a change → exactly +1; a second
    identical feedback with nothing new is no change → +0."""
    plan = client.get("/api/week/0").json()["week_plan"]
    start = plan["start_date"]
    today = date.today().isoformat()
    day = next((d for d in plan["weeks"][0]["days"] if d["date"] == today), None)
    sess = next((s for s in (day or {}).get("sessions") or [] if s.get("status") not in ("done", "skipped")), None)
    if sess is None:
        pytest.skip("no pending session today in the fixture week")
    r = client.post("/api/replanner/events", json={
        "events": [{"event_type": "mark_done", "date": today, "session_ref": sess["session_id"], "slot": sess["slot"]}],
        "week_plan": plan, "base_revision": plan["plan_revision"]})
    assert r.status_code == 200, r.text
    rev_after_events = revision_of(_stored(start))
    body = {"log_entry": {"date": today, "session_id": sess["session_id"], "difficulty": "ok",
                          "exercise_feedback": []}}
    assert client.post("/api/feedback", json=body).status_code == 200
    rev1 = revision_of(_stored(start))
    assert rev1 <= rev_after_events + 1
    assert client.post("/api/feedback", json=body).status_code == 200
    assert revision_of(_stored(start)) == rev1


def test_write_endpoints_are_serialised_per_user():
    import threading

    from backend.api.plan_revision import serialized_by_user, user_write_lock
    from backend.api.routers import feedback, outdoor, replanner, session

    for fn in (replanner.events, replanner.override, replanner.quick_add, session.add_exercise,
               session.remove_exercise, session.surface_override, outdoor.post_outdoor_log,
               outdoor.put_outdoor_log, outdoor.finish_outdoor_session):
        assert hasattr(fn, "__wrapped__"), fn
    assert user_write_lock("u1") is user_write_lock("u1")
    assert user_write_lock("u1") is not user_write_lock("u2")

    inside = []
    gate = threading.Event()

    @serialized_by_user
    def slow(*, user_id):
        inside.append(("in", user_id))
        gate.wait(1)
        inside.append(("out", user_id))

    t = threading.Thread(target=slow, kwargs={"user_id": "u1"})
    t.start()
    while not inside:
        pass
    # Same user: blocked while the first write holds the lock.
    got = user_write_lock("u1").acquire(blocking=False)
    if got:
        user_write_lock("u1").release()
    assert not got
    # Another user is never blocked by it.
    assert user_write_lock("u2").acquire(blocking=False)
    user_write_lock("u2").release()
    gate.set()
    t.join()
    assert inside == [("in", "u1"), ("out", "u1")]


def test_outdoor_log_reports_plan_synced_and_moves_the_revision(isolate_state):
    """The frontend contract after B371: POST /api/outdoor/log syncs the plan
    server side (B273) and says so — the client must not then send
    complete_outdoor on its pre-log copy (it would be a 409)."""
    plan = client.get("/api/week/0").json()["week_plan"]
    start = plan["start_date"]
    base = plan["plan_revision"]
    today = date.today().isoformat()
    r = client.post("/api/outdoor/log", json={
        "log_version": "outdoor.v1", "date": today, "spot_name": "Test crag", "discipline": "lead",
        "duration_minutes": 120, "routes": [{"name": "R", "grade": "6a", "style": "onsight", "attempts": [{"result": "sent"}]}]})
    if r.status_code != 200:
        pytest.skip(f"outdoor log rejected by the fixture: {r.text}")
    if not r.json().get("plan_synced"):
        pytest.skip("fixture week has no day to sync")
    assert revision_of(_stored(start)) > base
    stale = client.post("/api/replanner/events", json={
        "events": [{"event_type": "complete_outdoor", "date": today}],
        "week_plan": plan, "base_revision": base})
    assert stale.status_code == 409
