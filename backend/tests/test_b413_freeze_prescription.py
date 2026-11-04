"""B413 (D2) — a played engine session keeps the prescription it was shown.

Before B413 the guided player sent only ``POST /api/feedback``: the server
marked the session done WITHOUT its prescription, the feedback moved the
ladder, and the next GET resolved the played session with the NEW state and
saved that (B375). 2026-11-03: the view showed the Copenhagen plank 3x20 s,
the stored record says dynamic Copenhagen 3x6 — and the history seed then read
the wrong dose for that day.

Now the prescription is frozen on the server at the planned → done transition
(``plan_revision.freeze_played_resolved``), with GET's own resolver
(``week._auto_resolve``: B268 order, A281 taper, user_added rows, the phase of
the week) on the plan before the "done" and the state before the feedback.
In /feedback it is written after the closed loop ran, so every input of the
closed loop is what it was without the freeze. B375 stays the fallback.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api import plan_revision as pr
from backend.api.main import app
from backend.api.routers import feedback as feedback_router
from backend.api.routers import week as week_router
from backend.engine import bw_ladders as bl
from backend.tests.test_c272_bw_ladders_catalog import _tested_state

client = TestClient(app)

UID = str(uuid.UUID(int=0xB4132, version=4))
HDR = {"X-User-ID": UID}

#: The 03/11 lateral entry: Copenhagen plank at the top of its band (3x20 s),
#: one session at the top already — the next "ok" (or done unrated) promotes.
LATERAL_AT_TOP = {"level_idx": 2, "target": 20, "sets": 3, "top_streak": 1, "source": "feedback"}

_PHASE = {
    "domain_weights": {"core_prehab": 0.087, "finger_strength": 0.348, "power_endurance": 0.087,
                       "pulling_strength": 0.261, "technique": 0.087, "volume_climbing": 0.13},
    "intensity_cap": "max",
    "session_pool": ["finger_strength_home", "prehab_maintenance", "strength_long", "core_training",
                     "flexibility_full", "handstand_practice"],
}


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    from backend.engine import storage_file

    monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
    monkeypatch.delenv("STORAGE_REQUEST_MEMO", raising=False)
    yield


def _monday() -> date:
    d = date.today()
    return d - timedelta(days=d.weekday())


MON = _monday()
MON_ISO = MON.isoformat()


def _week(start: date, sessions: dict) -> dict:
    return {
        "start_date": start.isoformat(),
        "profile_snapshot": {"phase_id": "strength_power"},
        "weeks": [{"week_index": 1, "days": [
            {"date": (start + timedelta(days=i)).isoformat(), "sessions": copy.deepcopy(sessions.get(i, []))}
            for i in range(7)]}],
    }


#: The session of 03/11: the legs lunch, whose floor-core block alternates
#: (A/B by week) the Copenhagen plank and the L-sit, each at its ladder level.
SID = "legs_maintenance_lunch"


def _core(**extra) -> dict:
    return dict({"slot": "lunch", "session_id": SID, "location": "home",
                 "tags": {"hard": False, "finger": False}}, **extra)


def _custom() -> dict:
    return {"slot": "lunch", "session_id": "custom_cs_core", "is_custom": True, "custom_session_id": "cs_core",
            "exercises": [{"exercise_id": "back_extension", "sets": 3, "reps": 8, "progress_mode": "ladder"}],
            "tags": {"hard": False, "finger": False}}


def _state(*, tested: bool = True, this_week: dict | None = None, lateral: dict | None = None,
           offset: int | None = None) -> dict:
    st = _tested_state()
    for rows in (st.get("tests") or {}).values():
        for r in rows:
            r["date"] = (MON - timedelta(days=14)).isoformat()
    if not tested:
        st["tests"] = {}
    # A bench at home: the ladder stage can then prescribe the dynamic
    # Copenhagen (bench required) once the athlete reaches it — the 03/11 case.
    st["equipment"]["home"] = sorted(set(st["equipment"]["home"]) | {"bench"})
    st["bw_progression"] = {"lateral": dict(lateral or LATERAL_AT_TOP,
                                            last_session_date=(MON - timedelta(days=5)).isoformat())}
    st["macrocycle"] = {
        "start_date": (MON - timedelta(weeks=_offset() if offset is None else offset)).isoformat(),
        "total_weeks": 16,
        "phases": [dict(_PHASE, phase_id="strength_power", duration_weeks=10),
                   dict(_PHASE, phase_id="power_endurance", duration_weeks=3),
                   dict(_PHASE, phase_id="performance", duration_weeks=3)],
    }
    st["availability"] = {d: {"evening": {"available": True, "preferred_location": "home"}}
                          for d in ("mon", "wed", "fri")}
    plan = _week(MON, this_week if this_week is not None else {0: [_core()]})
    prev = MON - timedelta(weeks=1)
    st["week_plans"] = {MON_ISO: plan, prev.isoformat(): _week(prev, {})}
    st["current_week_plan"] = plan
    st["custom_sessions"] = [{"id": "cs_core", "name": "Core", "exercises": copy.deepcopy(_custom()["exercises"])}]
    st["session_completion_log"] = []
    return st


_OFFSET: list = []


def _offset() -> int:
    """Weeks between the macrocycle start and this Monday such that the A/B
    rotation of the legs lunch picks the Copenhagen plank this week (the pair
    order is seeded by the phase start, which moves with the real clock)."""
    if not _OFFSET:
        for k in range(2, 9):
            st = _state(offset=k)
            view = copy.deepcopy(st["week_plans"][MON_ISO])
            week_router._auto_resolve(view, st, None, phase="strength_power")
            if _lateral_rows(_session(view)["resolved"]) == PLANK_3X20:
                _OFFSET.append(k)
                break
        else:
            raise AssertionError("no week picks the Copenhagen plank")
    return _OFFSET[0]


def _seed(**kw) -> dict:
    st = _state(**kw)
    deps.save_state(st, UID)
    return st


def _get(**params) -> dict:
    r = client.get("/api/week/0", headers=HDR, params=dict({"today": MON_ISO}, **params))
    assert r.status_code == 200, r.text
    return r.json()


def _session(plan: dict, sid: str = SID, day: int = 0) -> dict:
    for s in plan["weeks"][0]["days"][day]["sessions"]:
        if s.get("session_id") == sid:
            return s
    raise AssertionError(f"{sid} not found")


def _stored(sid: str = SID, day: int = 0) -> dict:
    return _session(deps.load_state(UID)["week_plans"][MON_ISO], sid, day)


def _lateral_rows(resolved: dict) -> list:
    return [(i["exercise_id"], i["prescription"].get("sets"), i["prescription"].get("work_seconds"),
             i["prescription"].get("reps"))
            for i in (resolved or {}).get("resolved_session", {}).get("exercise_instances", [])
            if (i.get("prescription") or {}).get("source") == "bw_ladder"]


def _guided_feedback(items=None, sid: str = SID, day: str = MON_ISO):
    items = items if items is not None else [
        {"exercise_id": "copenhagen_plank", "completed": True, "completed_sets": 3, "bw_ladder": "engine"}]
    return client.post("/api/feedback", headers=HDR, json={"log_entry": {
        "date": day, "session_id": sid, "feedback_contract": 2,
        "actual": {"exercise_feedback_v1": items}}})


def _events(plan: dict, events: list, **extra):
    return client.post("/api/replanner/events", headers=HDR,
                       json=dict({"week_plan": plan, "today": MON_ISO, "events": events}, **extra))


def _mark_done(plan: dict, sid: str = SID, day: str = MON_ISO, **extra):
    return _events(plan, [{"event_type": "mark_done", "date": day, "session_ref": sid}], **extra)


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True)


def _body(resolved: dict) -> dict:
    """A resolution without its clock stamp (``generated_at``, to the second):
    two resolutions of the same session compare on what they prescribe."""
    return {k: v for k, v in (resolved or {}).items() if k != "generated_at"}


def _no_clock(obj):
    """*obj* without any ``generated_at`` stamp, at any depth."""
    if isinstance(obj, dict):
        return {k: _no_clock(v) for k, v in obj.items() if k != "generated_at"}
    if isinstance(obj, list):
        return [_no_clock(v) for v in obj]
    return obj


def _played(session: dict) -> str:
    """A played session as stored, minus the A141 ``process_cue`` a client
    echoes back on a played session (read-time, B371 keeps played sessions as
    sent) — every field of the record itself is compared."""
    return _canon({k: v for k, v in session.items() if k != "process_cue"})


PLANK_3X20 = [("copenhagen_plank", 3, 20, None)]




# ---------------------------------------------------------------------------
# The bug and its fix
# ---------------------------------------------------------------------------

def test_guided_feedback_freezes_the_prescription_shown():
    """03/11: the guided player posts only the feedback. The record keeps the
    Copenhagen plank 3x20 s that was shown, while the ladder moves on."""
    _seed()
    shown = _session(_get()["week_plan"])
    assert _lateral_rows(shown["resolved"]) == PLANK_3X20
    r = _guided_feedback()
    assert r.status_code == 200, r.text
    stored = _stored()
    assert stored["status"] == "done"
    assert _body(stored["resolved"]) == _body(shown["resolved"])  # the view, bit for bit
    # The ladder did move (unrated done = ok at the top → promotion).
    e = deps.load_state(UID)["bw_progression"]["lateral"]
    assert (e["exercise_id"], e["level_idx"]) == ("copenhagen_dynamic", 3)
    # The response view carries the frozen record too.
    assert _lateral_rows(_session(r.json()["week_plan"])["resolved"]) == PLANK_3X20


def test_without_the_freeze_the_next_get_stored_the_new_level(monkeypatch):
    """The pre-B413 behaviour, for the record: no freeze → B375 caches the
    resolution derived from the moved ladder."""
    _seed()
    monkeypatch.setattr(feedback_router, "compute_played_resolved", lambda *a, **k: {})
    assert _guided_feedback().status_code == 200
    assert not _stored().get("resolved")
    _get()
    assert _lateral_rows(_stored()["resolved"]) == [("copenhagen_dynamic", 3, None, 6)]


def test_next_get_does_not_rewrite():
    _seed()
    _get()
    assert _guided_feedback().status_code == 200
    before = _canon(_stored())
    plan = _get()["week_plan"]
    assert _canon(_stored()) == before
    assert _lateral_rows(_session(plan)["resolved"]) == PLANK_3X20


def test_events_freezes_server_view_not_stale_client_copy():
    _seed()
    body = _get()
    client_plan = body["week_plan"]
    server_view = copy.deepcopy(_session(client_plan)["resolved"])
    # The client's copy is an old one (resolved before a ladder change).
    _session(client_plan)["resolved"] = {"resolved_session": {"exercise_instances": [
        {"exercise_id": "plank", "prescription": {"sets": 1, "work_seconds": 5}}]}}
    r = _mark_done(client_plan, base_revision=client_plan.get("plan_revision"))
    assert r.status_code == 200, r.text
    assert _body(_stored()["resolved"]) == _body(server_view)
    assert _lateral_rows(_stored()["resolved"]) == PLANK_3X20


def test_feedback_after_events_no_refreeze_revision_plus_one():
    _seed()
    plan = _get()["week_plan"]
    assert _mark_done(plan, base_revision=plan.get("plan_revision")).status_code == 200
    st = deps.load_state(UID)
    frozen = copy.deepcopy(_session(st["week_plans"][MON_ISO])["resolved"])
    rev = st["week_plans"][MON_ISO]["plan_revision"]
    # The mark done moved the lateral ladder (done without feedback = ok):
    # a re-resolution now would show the dynamic Copenhagen.
    assert st["bw_progression"]["lateral"]["level_idx"] == 3
    assert _guided_feedback([{"exercise_id": "copenhagen_plank", "completed": True, "completed_sets": 3,
                              "bw_ladder": "engine", "feedback_label": "easy"}]).status_code == 200
    st = deps.load_state(UID)
    assert _session(st["week_plans"][MON_ISO])["resolved"] == frozen
    assert _lateral_rows(frozen) == PLANK_3X20
    assert st["week_plans"][MON_ISO]["plan_revision"] == rev + 1


def test_b216_alt_plan():
    """current_week_plan still points at last week (Monday rollover): the
    mark_done lands in week_plans[this Monday] — frozen there too."""
    st = _state()
    prev = (MON - timedelta(weeks=1)).isoformat()
    st["current_week_plan"] = copy.deepcopy(st["week_plans"][prev])
    deps.save_state(st, UID)
    shown = copy.deepcopy(_session(deps.load_state(UID)["week_plans"][MON_ISO]))
    # The view GET serves (computed without the GET, which would resync the slot).
    view = copy.deepcopy(st["week_plans"][MON_ISO])
    week_router._auto_resolve(view, copy.deepcopy(st), UID, phase="strength_power")
    assert "resolved" not in shown
    assert _guided_feedback().status_code == 200
    stored = _stored()
    assert stored["status"] == "done"
    assert _body(stored["resolved"]) == json.loads(json.dumps(_body(_session(view)["resolved"])))
    assert _lateral_rows(stored["resolved"]) == PLANK_3X20


def test_feedback_inputs_bit_identical_with_and_without_freeze(monkeypatch):
    """Everything the closed loop reads, and everything it writes, is the same
    with and without the freeze: only the played session's ``resolved``
    differs (the clock-stamped fields aside)."""
    captured: dict = {}
    real = feedback_router.apply_feedback

    def scrub(obj):
        """Without the frozen ``resolved`` and the clock stamps (``*_at``)."""
        if isinstance(obj, dict):
            return {k: scrub(v) for k, v in obj.items() if k != "resolved" and not k.endswith("_at")}
        if isinstance(obj, list):
            return [scrub(v) for v in obj]
        return obj

    def spy(log_entry, state, **kw):
        captured.setdefault("calls", []).append(_canon(scrub([log_entry, state, kw.get("archived_weeks")])))
        return real(log_entry, state, **kw)

    monkeypatch.setattr(feedback_router, "apply_feedback", spy)
    items = [{"exercise_id": "copenhagen_plank", "completed": True, "completed_sets": 3, "bw_ladder": "engine",
              "feedback_label": "ok"},
             {"exercise_id": "plank", "completed": True, "completed_sets": 3, "feedback_label": "hard"}]

    def run(freeze: bool) -> dict:
        _seed()
        if not freeze:
            monkeypatch.setattr(feedback_router, "compute_played_resolved", lambda *a, **k: {})
        assert _guided_feedback(copy.deepcopy(items)).status_code == 200
        monkeypatch.setattr(feedback_router, "compute_played_resolved", pr.compute_played_resolved)
        return deps.load_state(UID)

    with_freeze = run(True)
    without = run(False)
    assert len(captured["calls"]) == 2 and captured["calls"][0] == captured["calls"][1]
    assert _session(with_freeze["week_plans"][MON_ISO]).get("resolved")
    assert not _session(without["week_plans"][MON_ISO]).get("resolved")
    assert scrub(with_freeze) == scrub(without)


def test_custom_sessions_unaffected():
    _seed(this_week={0: [_custom(), _core()]})
    assert pr.played_engine_keys(
        _week(MON, {0: [dict(_custom(), status="done"), {"slot": "lunch", "session_id": "generated_bp_1",
                                                         "status": "done"}]}),
        _week(MON, {0: [_custom(), {"slot": "lunch", "session_id": "generated_bp_1"}]})) == []
    shown = _session(_get()["week_plan"], "custom_cs_core")
    r = _guided_feedback([{"exercise_id": "back_extension", "completed": True, "completed_sets": 3,
                           "bw_ladder": "ladder", "feedback_label": "ok"}], sid="custom_cs_core")
    assert r.status_code == 200, r.text
    stored = _stored("custom_cs_core")
    assert "resolved" not in stored
    # The B371 custom freeze, as before: the rows of the view.
    assert stored["exercises"] == shown["exercises"]
    # The engine session of the same day is not touched.
    assert "status" not in _stored() and "resolved" not in _stored()


def test_user_edited_and_user_added():
    st = _state()
    view = copy.deepcopy(st["week_plans"][MON_ISO])
    week_router._auto_resolve(view, copy.deepcopy(st), None, phase="strength_power")
    resolved = _session(view)["resolved"]
    extra = {"exercise_id": "band_pull_apart", "source": "user_added", "prescription": {"sets": 2, "reps": 15}}
    # A pending session with a user-added row: the freeze re-appends it.
    before = copy.deepcopy(st["week_plans"][MON_ISO])
    _session(before)["resolved"] = copy.deepcopy(resolved)
    _session(before)["resolved"]["resolved_session"]["exercise_instances"].append(dict(extra))
    after = copy.deepcopy(before)
    _session(after)["status"] = "done"
    _session(after)["resolved"] = {"stale": True}
    assert pr.freeze_played_resolved(after, before, st) == 1
    inst = _session(after)["resolved"]["resolved_session"]["exercise_instances"]
    assert inst[-1] == extra and inst[:-1] == resolved["resolved_session"]["exercise_instances"]
    # A session the user edited keeps its own resolved (the pencil wins).
    edited = {"resolved_session": {"exercise_instances": [
        {"exercise_id": "plank", "prescription": {"sets": 4, "work_seconds": 45}}]}}
    before = copy.deepcopy(st["week_plans"][MON_ISO])
    _session(before).update({"_user_edited": True, "resolved": copy.deepcopy(edited)})
    after = copy.deepcopy(before)
    _session(after)["status"] = "done"
    assert pr.freeze_played_resolved(after, before, st) == 1
    assert _session(after)["resolved"] == edited


def test_taper_day_freeze_equals_get():
    st = _state(this_week={0: [_core()], 2: [_core(slot="evening")]})
    st["week_plans"][MON_ISO]["weeks"][0]["days"][2]["taper_volume_multiplier"] = 0.5
    before = st["week_plans"][MON_ISO]
    get_view = copy.deepcopy(before)
    week_router._auto_resolve(get_view, copy.deepcopy(st), None, phase="strength_power")
    after = copy.deepcopy(before)
    _session(after, day=2)["status"] = "done"
    assert pr.freeze_played_resolved(after, before, st) == 1
    frozen = _session(after, day=2)["resolved"]
    assert _body(frozen) == _body(_session(get_view, day=2)["resolved"])
    assert any(i["prescription"].get("taper_scaled_from") for i in frozen["resolved_session"]["exercise_instances"])
    assert "resolved" not in _session(after, day=0)  # only the session played


def test_freeze_failure_fail_soft(monkeypatch):
    _seed()
    real = week_router._auto_resolve

    def boom(*a, **k):
        raise RuntimeError("resolver down")

    monkeypatch.setattr(week_router, "_auto_resolve", boom)
    assert _guided_feedback().status_code == 200
    assert _stored()["status"] == "done" and not _stored().get("resolved")
    # (never monkeypatch.undo(): it would also undo the storage isolation)
    monkeypatch.setattr(week_router, "_auto_resolve", real)
    _seed()  # the same request, the resolver back: the freeze is there
    assert _guided_feedback().status_code == 200 and _stored().get("resolved")


def test_undo_then_remark_refreezes():
    _seed()
    plan = _get()["week_plan"]
    assert _mark_done(plan).status_code == 200
    assert _lateral_rows(_stored()["resolved"]) == PLANK_3X20
    plan = _get()["week_plan"]
    r = _events(plan, [{"event_type": "mark_planned", "date": MON_ISO, "session_ref": SID}])
    assert r.status_code == 200, r.text
    assert "status" not in _stored()
    # The undo put the ladder back (the "done" had promoted it).
    e = deps.load_state(UID)["bw_progression"]["lateral"]
    assert (e["level_idx"], e["target"], e["top_streak"]) == (2, 20, 1)
    # Settings: the athlete moves the lateral ladder up by hand.
    r = client.put("/api/bw-progression/lateral", headers=HDR, json={"level_idx": 3, "date": MON_ISO})
    assert r.status_code == 200, r.text
    plan = _get()["week_plan"]
    shown = _session(plan)["resolved"]
    assert _lateral_rows(shown) == [("copenhagen_dynamic", 3, None, 6)]
    assert _mark_done(plan).status_code == 200
    assert _body(_stored()["resolved"]) == _body(shown)


def test_frozen_prescription_survives_regeneration():
    """Past sessions are immutable: the frozen done session stays byte for
    byte through GET, /events, a forced regeneration, a ladder change and a
    gym / equipment change."""
    _seed(this_week={0: [_core()], 2: [_core()]})
    assert _guided_feedback().status_code == 200
    want = _played(_stored())
    assert _lateral_rows(_stored()["resolved"]) == PLANK_3X20

    _get()
    assert _played(_stored()) == want
    plan = _get()["week_plan"]
    wed = (MON + timedelta(days=2)).isoformat()
    assert _mark_done(plan, day=wed).status_code == 200
    assert _played(_stored()) == want
    regen = _get(force="true")
    assert regen["week_plan"] and not regen.get("regeneration_failed")
    assert _played(_stored()) == want
    r = client.put("/api/bw-progression/lateral", headers=HDR, json={"level_idx": 0, "date": MON_ISO})
    assert r.status_code == 200, r.text
    _get()
    assert _played(_stored()) == want
    plan = _get()["week_plan"]
    r = _events(plan, [{"event_type": "change_gym", "date": MON_ISO, "location": "gym", "gym_id": "g_board"}])
    assert r.status_code == 200, r.text
    assert _played(_stored()) == want
    st = deps.load_state(UID)
    r = client.put("/api/state", headers=HDR, json={"equipment": dict(st["equipment"], home=["pullup_bar"])})
    assert r.status_code == 200, r.text
    _get()
    assert not _get(force="true").get("regeneration_failed")
    assert _played(_stored()) == want


def test_auto_resolve_stop_after_default_identical():
    st = _state(this_week={0: [_core()], 2: [_core()], 4: [_core()]})
    full = copy.deepcopy(st["week_plans"][MON_ISO])
    week_router._auto_resolve(full, copy.deepcopy(st), None, phase="strength_power")
    default = copy.deepcopy(st["week_plans"][MON_ISO])
    week_router._auto_resolve(default, copy.deepcopy(st), None, phase="strength_power", stop_after=None)
    assert _canon(_no_clock(default)) == _canon(_no_clock(full))
    wed = (MON + timedelta(days=2)).isoformat()
    part = copy.deepcopy(st["week_plans"][MON_ISO])
    week_router._auto_resolve(part, copy.deepcopy(st), None, phase="strength_power",
                              stop_after=[(wed, "lunch", SID)])
    # Up to the key: identical to the whole walk (B268 recency flows forward
    # only); after it: nothing resolved.
    assert _body(_session(part, day=0)["resolved"]) == _body(_session(full, day=0)["resolved"])
    assert _body(_session(part, day=2)["resolved"]) == _body(_session(full, day=2)["resolved"])
    assert "resolved" not in _session(part, day=4)


def test_ladder_history_twin_uses_frozen_dose():
    """The history seed reads the dose of a logged row from its planned twin
    (the stored ``resolved``): with the freeze it is the dose played."""
    _seed()
    assert _guided_feedback().status_code == 200
    st = deps.load_state(UID)
    st["bw_progression"] = {}  # no persisted level: the seed reads the history
    hist = bl._history(st, MON + timedelta(days=1), None, bl._load_file())
    row = hist["lateral"]
    assert (row["exercise_id"], row["dose"], row["sets"]) == ("copenhagen_plank", 20, 3)


def test_one_archive_read_per_request_with_the_freeze(monkeypatch):
    """The freeze resolves on the archive the request already loaded: still
    one archive range read on /feedback and /events (B376, tested variant)."""
    from backend.api import ladder_archive
    from backend.engine import storage

    calls: list = []
    wrapper = storage.read_archived_weeks_in_range
    real = wrapper.__wrapped__
    monkeypatch.setattr(wrapper, "__wrapped__",
                        lambda uid, a, b, __real=real: calls.append(b) or __real(uid, a, b))
    _seed()
    calls.clear()
    assert _guided_feedback().status_code == 200
    assert _stored().get("resolved") and calls == [ladder_archive.OPEN_END], calls
    _seed()
    plan = _get()["week_plan"]
    calls.clear()
    assert _mark_done(plan).status_code == 200
    assert _stored().get("resolved") and calls == [ladder_archive.OPEN_END], calls
