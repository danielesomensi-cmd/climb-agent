"""B413 (D1) — the bodyweight ladders read the archived weeks.

A221 moves a past week to the cold store once it is older than the previous
Monday. Six ladder readers asked for the athlete's level without the archive,
so the seed of a family with no persisted entry saw ~2 weeks of history
instead of 120 days: the feedback on a family that existed only in the archive
found no base and was lost (T2B 2026-10-26 "ok", back extension 2026-10-28
"easy" — the real rows below), and the dose shown was not the dose the
feedback stepped from.

- Engine: every ladder reader takes an optional ``archived_weeks`` (None = the
  hot weeks, bit for bit as before).
- API: ONE loader (``backend/api/ladder_archive.py``) — no read for an
  untested athlete or an all-warm window, at most one archive range read per
  request (the retest policy and the key status filter their ranges out of
  it), a failed read serves the recent-weeks view on GET and persists nothing,
  and is a 503 that writes nothing on a write.
- Coach chat and CLI read the same Monday-aligned window.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api import deps, ladder_archive
from backend.api.main import app
from backend.api.plan_revision import freeze_played_customs, read_view
from backend.engine import bw_ladders as bl
from backend.engine import bw_progression as bp
from backend.engine import storage
from backend.engine.progression_v1 import apply_feedback
from backend.tests.test_c272_bw_ladders_catalog import _tested_state

client = TestClient(app)


def _plan(monday: str, days) -> dict:
    return {"start_date": monday, "weeks": [{"week_index": 1, "days": [
        {"date": d, "sessions": copy.deepcopy(ss)} for d, ss in days]}]}


# ---------------------------------------------------------------------------
# The real rows (Daniele, 2026-09-11 → 2026-10-28), reduced to the ladder rows
# ---------------------------------------------------------------------------

#: Archived on 26-28/10 (older than the previous Monday, 19/10).
REAL_ARCHIVE = {
    "2026-09-07": _plan("2026-09-07", [("2026-09-11", [{
        "session_id": "custom_cs_3a79af49", "slot": "lunch", "is_custom": True, "status": "done",
        "exercises": [{"exercise_id": "back_extension", "sets": 3, "reps": 12, "rest_between_sets_seconds": 45}],
        "actual_exercises": [{"completed": True, "exercise_id": "back_extension", "completed_reps": 1,
                              "completed_sets": 1, "feedback_label": "ok"}]}])]),
    "2026-10-12": _plan("2026-10-12", [
        ("2026-10-13", [{
            "session_id": "custom_cs_a4f41469", "slot": "lunch", "is_custom": True, "status": "done",
            "exercises": [{"exercise_id": "back_extension", "sets": 3, "reps": 12, "progress_mode": "ladder"}],
            "actual_exercises": [{"exercise_id": "back_extension", "completed": False, "bw_ladder": "ladder",
                                  "prescribed_sets": 3}]}]),
        ("2026-10-15", [{
            "session_id": "strength_long", "slot": "evening", "status": "done",
            "actual_exercises": [{"completed": True, "exercise_id": "hanging_leg_raise", "completed_sets": 3}]}]),
    ]),
}
#: Hot on 26-28/10.
REAL_HOT = {
    "2026-10-19": _plan("2026-10-19", [("2026-10-19", [{
        "session_id": "technique_focus_gym", "slot": "evening", "status": "done",
        "actual_exercises": [{"exercise_id": "toes_to_bar", "completed": False, "bw_ladder": "engine"}]}])]),
    "2026-10-26": _plan("2026-10-26", [
        ("2026-10-26", [{
            "session_id": "custom_cs_5e626e22", "slot": "lunch", "is_custom": True, "status": "done",
            "exercises": [{"exercise_id": "toes_to_bar", "sets": 3, "reps": 5, "progress_mode": "ladder",
                           "rest_between_sets_seconds": 90}]}]),
        ("2026-10-28", [{
            "session_id": "custom_cs_67206d0f", "slot": "lunch", "is_custom": True, "status": "done",
            "exercises": [{"exercise_id": "back_extension", "sets": 3, "reps": 12, "progress_mode": "ladder",
                           "rest_between_sets_seconds": 60}]}]),
    ]),
}
T2B_LOG = {"date": "2026-10-26", "session_id": "custom_cs_5e626e22", "feedback_contract": 2,
           "actual": {"exercise_feedback_v1": [
               {"bw_ladder": "ladder", "completed": True, "exercise_id": "toes_to_bar", "completed_sets": 2,
                "feedback_label": "ok", "prescribed_reps": 5, "prescribed_sets": 3}]}}
BACK_EXT_LOG = {"date": "2026-10-28", "session_id": "custom_cs_67206d0f", "feedback_contract": 2,
                "actual": {"exercise_feedback_v1": [
                    {"bw_ladder": "ladder", "completed": True, "exercise_id": "back_extension", "completed_sets": 2,
                     "feedback_label": "easy", "prescribed_reps": 12, "prescribed_sets": 3}]}}


def _real_state() -> dict:
    st = _tested_state()
    st["week_plans"] = copy.deepcopy(REAL_HOT)
    st["bw_progression"] = {}
    return st


def _strip(entry):
    return {k: v for k, v in (entry or {}).items() if k not in ("_prev", "last_outcome")}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class TestEngine:
    def test_entries_for_is_invariant_to_the_archive_move(self):
        """The same history read hot, or hot + archive after the A221 move,
        gives the same entries; a wider archive (overlapping the hot weeks,
        which win) changes nothing either."""
        everything = _tested_state()
        everything["week_plans"] = {**copy.deepcopy(REAL_ARCHIVE), **copy.deepcopy(REAL_HOT)}
        everything["bw_progression"] = {}
        for ref in ("2026-10-20", "2026-10-26", "2026-10-28", "2026-11-04", "2026-12-01"):
            r = date.fromisoformat(ref)
            floor = (r - timedelta(days=r.weekday() + 7)).isoformat()
            moved = copy.deepcopy(everything)
            arch = {k: moved["week_plans"].pop(k) for k in list(moved["week_plans"]) if k < floor}
            want = bp.entries_for(everything, ref)
            assert want, ref
            assert bp.entries_for(moved, ref, archived_weeks=arch) == want, ref
            assert bp.entries_for(moved, ref, archived_weeks={**arch, **copy.deepcopy(REAL_HOT)}) == want, ref
            assert bl.seed_levels(moved, ref, archived_weeks=arch) == bl.seed_levels(everything, ref), ref
        # Without the archive the moved state lost the families (the bug).
        moved = copy.deepcopy(everything)
        for k in list(moved["week_plans"]):
            if k < "2026-10-19":
                moved["week_plans"].pop(k)
        assert bp.entries_for(moved, "2026-10-26", exclude_session_key="2026-10-26|custom_cs_5e626e22") == {}
        assert set(bp.entries_for(moved, "2026-10-26", exclude_session_key="2026-10-26|custom_cs_5e626e22",
                                  archived_weeks=REAL_ARCHIVE)) == {"compression_hang", "posterior_chain"}

    def test_feedback_on_archive_only_family(self):
        # T2B 26/10 "ok": the history lives in the archive (15/10 hanging leg
        # raise = toes_to_bar L3, dose unknown → bottom of the band 5); the
        # 19/10 row is completed:false. Before B413 the feedback was lost.
        st = _real_state()
        assert apply_feedback(copy.deepcopy(T2B_LOG), copy.deepcopy(st)).get("bw_progression") == {}
        out = apply_feedback(copy.deepcopy(T2B_LOG), copy.deepcopy(st), archived_weeks=REAL_ARCHIVE)
        e = out["bw_progression"]["compression_hang"]
        assert (e["exercise_id"], e["level_idx"], e["sets"], e["target"]) == ("toes_to_bar", 3, 3, 6)
        assert e["last_outcome"]["kind"] == "step_up" and e["last_session_date"] == "2026-10-26"
        assert e["_prev"]["entry"]["target"] == 5 and e["_prev"]["entry"]["seeded_from"]["date"] == "2026-10-15"
        # Back extension 28/10 "easy": seeded from 11/09 (3x12 "ok", at the
        # top; 13/10 not done) → a custom row at the top proposes the next level.
        assert apply_feedback(copy.deepcopy(BACK_EXT_LOG), copy.deepcopy(st)).get("bw_progression") == {}
        out = apply_feedback(copy.deepcopy(BACK_EXT_LOG), copy.deepcopy(st), archived_weeks=REAL_ARCHIVE)
        e = out["bw_progression"]["posterior_chain"]
        assert (e["exercise_id"], e["level_idx"], e["target"]) == ("back_extension", 1, 12)
        assert e["last_outcome"]["kind"] == "promotion_proposed"
        assert e["pending_promotion"]["exercise_id"] == "single_leg_back_extension"
        assert e["_prev"]["entry"]["seeded_from"]["date"] == "2026-09-11"
        # Resubmitting replays from the snapshot (idempotent with the archive).
        again = apply_feedback(copy.deepcopy(BACK_EXT_LOG), copy.deepcopy(out), archived_weeks=REAL_ARCHIVE)
        assert again["bw_progression"]["posterior_chain"] == e

    def test_every_ladder_path_sees_the_archive(self, monkeypatch):
        # Hot: only the week of 19/10 (the sessions of 26-28/10 are not played).
        st = _real_state()
        st["week_plans"].pop("2026-10-26")
        day = "2026-10-28"
        row = {"exercise_id": "back_extension", "sets": 3, "reps": 8, "progress_mode": "ladder"}
        # Resolver stage.
        assert "posterior_chain" not in bp.build_resolve_context(st, day)["entries"]
        ctx = bp.build_resolve_context(st, day, archived_weeks=REAL_ARCHIVE)
        assert ctx["entries"]["posterior_chain"]["target"] == 12
        # resolve_session passes it to the stage (through week._auto_resolve).
        seen = []
        real = bp.build_resolve_context
        monkeypatch.setattr(bp, "build_resolve_context",
                            lambda *a, **k: seen.append(k.get("archived_weeks")) or real(*a, **k))
        from backend.api.routers.week import _auto_resolve

        plan = _plan("2026-10-26", [("2026-10-29", [{"slot": "evening", "session_id": "strength_long"}])])
        _auto_resolve(plan, copy.deepcopy(st), None, phase="strength_power", archived_weeks=REAL_ARCHIVE)
        assert seen and all(w is REAL_ARCHIVE for w in seen)
        monkeypatch.setattr(bp, "build_resolve_context", real)
        # Custom ladder rows.
        assert bp.resolve_custom_ladder_rows(st, [row], day)[0]["reps"] == 8
        got = bp.resolve_custom_ladder_rows(st, [row], day, REAL_ARCHIVE)[0]
        assert (got["reps"], got["stored_reps"], got["progress_source"]) == (12, 8, "bw_ladder")
        # Settings view.
        fam = lambda v: next(r for r in v["families"] if r["family"] == "posterior_chain")  # noqa: E731
        assert fam(bp.ladder_view(st, day))["active"] is False
        assert fam(bp.ladder_view(st, day, REAL_ARCHIVE))["level_idx"] == 1
        # set_level: two levels above "nothing" needs a confirm; one above the
        # seeded L1 does not.
        with pytest.raises(PermissionError):
            bp.set_level(copy.deepcopy(st), "posterior_chain", 2, day)
        assert bp.set_level(copy.deepcopy(st), "posterior_chain", 2, day, archived_weeks=REAL_ARCHIVE)["level_idx"] == 2
        # Promotion tap on a seeded entry: decline persists the seed.
        assert bp.resolve_promotion(copy.deepcopy(st), "posterior_chain", accept=False, ref_date=day) is None
        dec = bp.resolve_promotion(copy.deepcopy(st), "posterior_chain", accept=False, ref_date=day,
                                   archived_weeks=REAL_ARCHIVE)
        assert (dec["level_idx"], dec["target"]) == (1, 12)
        # read_view and the custom freeze (the pending custom of 28/10).
        st2 = copy.deepcopy(st)
        week = copy.deepcopy(REAL_HOT["2026-10-26"])
        pending = week["weeks"][0]["days"][1]["sessions"][0]
        pending.pop("status")
        pending["exercises"] = [dict(row)]
        st2["week_plans"]["2026-10-26"] = week
        ex = lambda p: p["weeks"][0]["days"][1]["sessions"][0]["exercises"][0]  # noqa: E731
        assert ex(read_view(week, st2))["reps"] == 8
        assert ex(read_view(week, st2, REAL_ARCHIVE))["reps"] == 12
        after = copy.deepcopy(week)
        after["weeks"][0]["days"][1]["sessions"][0]["status"] = "done"
        assert freeze_played_customs(after, week, st2, REAL_ARCHIVE) == 1
        assert ex(after)["reps"] == 12
        # A None archive is the pre-B413 behaviour bit for bit.
        assert bp.entries_for(st, day, archived_weeks=None) == bp.entries_for(st, day)

    def test_engine_level_equals_athlete_context(self):
        from backend.engine.athlete_context import build_athlete_context

        st = _real_state()
        for day in ("2026-10-26", "2026-10-28"):
            ref = date.fromisoformat(day)
            # The coach / CLI window, read exactly as they read it.
            lo = bl.archive_window_start(ref).isoformat()
            arch = {k: v for k, v in REAL_ARCHIVE.items() if lo <= k <= day}
            ctx = build_athlete_context(st, ref, archived_weeks=arch, include_next_week=False)
            seed = {r["family"]: r for r in ctx["bw_ladders"]["families"] if r.get("level_idx") is not None}
            entries = bp.entries_for(st, day, archived_weeks=arch)
            assert set(seed) == set(entries), day
            for name, e in entries.items():
                assert (seed[name]["level_idx"], seed[name]["target"], seed[name]["sets"]) == (
                    e["level_idx"], e["target"], e["sets"]), (day, name)


class TestWindow:
    def test_one_monday_aligned_window_for_every_reader(self, monkeypatch):
        from backend.coach import athlete_block
        from backend.api.routers import week as week_router

        n = bl.archive_lookback_days()
        assert n == 120 >= bl.RETEST_ARCHIVE_LOOKBACK_D == week_router._RETEST_ARCHIVE_LOOKBACK_D
        assert athlete_block.ARCHIVE_LOOKBACK_D == n
        for day in ("2026-10-26", "2026-10-28", "2026-11-04", "2026-11-08"):
            lo = bl.archive_window_start(day)
            assert lo.weekday() == 0 and (date.fromisoformat(day) - lo).days >= n
        reads = []
        monkeypatch.setattr("backend.engine.storage.read_archived_weeks_in_range",
                            lambda uid, a, b: reads.append(a) or {})
        athlete_block._archived_weeks({"week_plans": {}}, None, date(2026, 11, 4))
        assert reads == [bl.archive_window_start("2026-11-04").isoformat()] == ["2026-07-06"]


# ---------------------------------------------------------------------------
# API — one loader per request (dates relative to the real clock: the loader
# uses the server's today to tell which weeks A221 may have archived)
# ---------------------------------------------------------------------------

UID = str(uuid.UUID(int=0xB413, version=4))
HDR = {"X-User-ID": UID}
CUSTOM_ROW = {"exercise_id": "back_extension", "sets": 3, "reps": 8, "progress_mode": "ladder",
              "rest_between_sets_seconds": 60}


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


def _week(start: date, sessions: dict) -> dict:
    days = [(
        (start + timedelta(days=i)).isoformat(), sessions.get(i, [])) for i in range(7)]
    plan = _plan(start.isoformat(), days)
    plan["profile_snapshot"] = {"phase_id": "strength_power", "hard_cap_per_week": 4, "recovery_multiplier": 1.0,
                                "session_pool": ["strength_long"]}
    return plan


def _custom_slot() -> dict:
    return {"slot": "lunch", "session_id": "custom_cs_core", "is_custom": True, "custom_session_id": "cs_core",
            "exercises": [dict(CUSTOM_ROW)], "tags": {"hard": False, "finger": False}}


def _seed_api(*, tested: bool = True, warm: bool = False, played_engine: bool = False) -> dict:
    """This week hot (a pending custom with a back-extension ladder row on
    Monday), the previous week hot, the back extension history five weeks ago
    in the cold store: 3x10 "ok" → seeded L1 3x11."""
    mon = _monday()
    st = _tested_state()
    test_day = (mon - timedelta(days=14)).isoformat()
    for rows in (st.get("tests") or {}).values():
        for r in rows:
            r["date"] = test_day
    if not tested:
        st["tests"] = {}
    st["bw_progression"] = {}
    st["macrocycle"] = {
        "start_date": (mon - timedelta(weeks=3)).isoformat(),
        "end_date": (mon + timedelta(weeks=9) - timedelta(days=1)).isoformat(),
        "total_weeks": 12,
        "phases": [
            {"phase_id": "strength_power", "duration_weeks": 6, "domain_weights": {}, "session_pool": [],
             "start_week": 1, "end_week": 6},
            {"phase_id": "power_endurance", "duration_weeks": 3, "domain_weights": {}, "session_pool": [],
             "start_week": 7, "end_week": 9},
            {"phase_id": "performance", "duration_weeks": 3, "domain_weights": {}, "session_pool": [],
             "start_week": 10, "end_week": 12},
        ],
    }
    this_week = {0: [_custom_slot()]}
    if played_engine:
        this_week[0].append({"slot": "evening", "session_id": "strength_long", "status": "done",
                             "tags": {"hard": True, "finger": True}})
    plan = _week(mon, this_week)
    st["week_plans"] = {mon.isoformat(): plan, (mon - timedelta(weeks=1)).isoformat(): _week(mon - timedelta(weeks=1), {})}
    st["current_week_plan"] = plan
    st["custom_sessions"] = [{"id": "cs_core", "name": "Core", "exercises": [dict(CUSTOM_ROW)]}]
    st["session_completion_log"] = []
    hist_week = mon - timedelta(weeks=5)
    history = _week(hist_week, {2: [{
        "slot": "lunch", "session_id": "custom_cs_old", "is_custom": True, "status": "done",
        "exercises": [{"exercise_id": "back_extension", "sets": 3, "reps": 10}],
        "actual_exercises": [{"exercise_id": "back_extension", "completed": True, "completed_sets": 3,
                              "feedback_label": "ok"}]}]})
    if warm:
        # Every week of the window that A221 could archive is still hot.
        wk = bl.archive_window_start(mon)
        while wk <= mon - timedelta(weeks=2):
            st["week_plans"].setdefault(wk.isoformat(), _week(wk, {}))
            wk += timedelta(days=7)
        st["week_plans"][hist_week.isoformat()] = history
    else:
        storage.archive_week(UID, hist_week.isoformat(), history)
    deps.save_state(st, UID)
    return plan


@pytest.fixture
def range_reads(monkeypatch):
    """The real archive range reads (behind the B376 memo): their ``end``."""
    calls: list = []
    wrapper = storage.read_archived_weeks_in_range
    real = wrapper.__wrapped__

    def counting(user_id, start, end, __real=real):
        calls.append(end)
        return __real(user_id, start, end)

    monkeypatch.setattr(wrapper, "__wrapped__", counting)
    return calls


def _broken_archive(monkeypatch):
    def boom(*a, **k):
        raise OSError("statement timeout")

    monkeypatch.setattr(storage.read_archived_weeks_in_range, "__wrapped__", boom)


def _get_week() -> dict:
    r = client.get("/api/week/4", headers=HDR, params={"today": _monday().isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


def _custom_row_of(plan: dict) -> dict:
    for d in plan["weeks"][0]["days"]:
        for s in d["sessions"]:
            if s.get("session_id") == "custom_cs_core":
                return s["exercises"][0]
    raise AssertionError("custom not found")


def _feedback(label="ok"):
    mon = _monday().isoformat()
    return client.post("/api/feedback", headers=HDR, json={"log_entry": {
        "date": mon, "session_id": "custom_cs_core", "feedback_contract": 2,
        "actual": {"exercise_feedback_v1": [{"exercise_id": "back_extension", "completed": True, "completed_sets": 3,
                                             "feedback_label": label, "bw_ladder": "ladder", "prescribed_sets": 3}]}}})


def _mark_done(plan: dict, **extra):
    mon = _monday().isoformat()
    return client.post("/api/replanner/events", headers=HDR, json=dict({
        "week_plan": plan, "today": mon,
        "events": [{"event_type": "mark_done", "date": mon, "session_ref": "custom_cs_core"}]}, **extra))


def _stored_custom() -> dict:
    st = deps.load_state(UID)
    return _custom_row_of(st["week_plans"][_monday().isoformat()])


class TestApi:
    def test_shown_frozen_and_feedback_dose_agree(self):
        _seed_api()
        shown = _custom_row_of(_get_week()["week_plan"])
        assert (shown["reps"], shown["stored_reps"]) == (11, 8)
        r = client.get("/api/custom-session/cs_core", headers=HDR, params={"date": _monday().isoformat()})
        assert r.status_code == 200 and r.json()["exercises"][0]["reps"] == 11
        r = client.get("/api/bw-progression", headers=HDR, params={"date": _monday().isoformat()})
        fam = next(f for f in r.json()["families"] if f["family"] == "posterior_chain")
        assert (fam["active"], fam["level_idx"], fam["dose"]) == (True, 1, "3x11")
        r = _feedback()
        assert r.status_code == 200, r.text
        assert _stored_custom()["reps"] == 11  # the frozen prescription = the one shown
        e = deps.load_state(UID)["bw_progression"]["posterior_chain"]
        assert e["_prev"]["entry"]["target"] == 11 and e["target"] == 12  # the base = the dose shown

    def test_events_mark_done_freezes_the_dose_shown(self):
        plan = _seed_api()
        assert _custom_row_of(_get_week()["week_plan"])["reps"] == 11
        r = _mark_done(plan)
        assert r.status_code == 200, r.text
        assert _stored_custom()["reps"] == 11

    def test_one_archive_read_per_request_for_a_tested_user(self, range_reads):
        plan = _seed_api(played_engine=True)
        for call in (_get_week, _get_week, lambda: _mark_done(plan), lambda: _feedback("easy")):
            range_reads.clear()
            body = call()
            if hasattr(body, "status_code"):
                assert body.status_code == 200, body.text
            # One range read: the ladder window (open end); the retest policy
            # and the key status of the request filter theirs out of it.
            assert range_reads == [ladder_archive.OPEN_END], range_reads

    def test_untested_no_archive_read(self, range_reads):
        _seed_api(tested=False)
        _get_week()
        assert ladder_archive.OPEN_END not in range_reads
        assert _custom_row_of(_get_week()["week_plan"])["reps"] == 8  # catalog dose, as before
        range_reads.clear()
        assert _feedback().status_code == 200
        assert range_reads == []

    def test_all_warm_window_no_archive_read(self, range_reads):
        _seed_api(warm=True)
        body = _get_week()
        assert ladder_archive.OPEN_END not in range_reads
        assert _custom_row_of(body["week_plan"])["reps"] == 11  # the hot history seeds it

    def test_archive_failure_get_persists_nothing(self, monkeypatch):
        _seed_api(played_engine=True)
        real = storage.read_archived_weeks_in_range.__wrapped__
        _broken_archive(monkeypatch)
        body = _get_week()
        assert _custom_row_of(body["week_plan"])["reps"] == 8  # the recent-weeks view
        mon = _monday().isoformat()
        stored = deps.load_state(UID)["week_plans"][mon]["weeks"][0]["days"][0]["sessions"]
        played = next(s for s in stored if s["session_id"] == "strength_long")
        assert not played.get("resolved")  # B375 cache skipped in this request
        monkeypatch.setattr(storage.read_archived_weeks_in_range, "__wrapped__", real)
        _get_week()  # the archive is back: the played session is cached
        stored = deps.load_state(UID)["week_plans"][mon]["weeks"][0]["days"][0]["sessions"]
        assert next(s for s in stored if s["session_id"] == "strength_long").get("resolved")

    def test_archive_failure_on_write_is_503_and_writes_nothing(self, monkeypatch):
        plan = _seed_api()
        before = json.dumps(deps.load_state(UID), sort_keys=True)
        _broken_archive(monkeypatch)
        for call in (_feedback, lambda: _mark_done(plan),
                     lambda: client.put("/api/bw-progression/posterior_chain", headers=HDR,
                                        json={"level_idx": 1, "date": _monday().isoformat()}),
                     lambda: client.post("/api/bw-progression/posterior_chain/promotion", headers=HDR,
                                         json={"accept": False, "date": _monday().isoformat()})):
            r = call()
            assert r.status_code == 503, r.text
            assert r.json()["detail"]["error"] == "archive_unavailable"
            assert json.dumps(deps.load_state(UID), sort_keys=True) == before
        # The dry run reads no ladder dose: it still answers.
        assert _mark_done(plan, dry_run=True).status_code == 200


class TestLoader:
    def test_load_is_none_without_need_and_reads_the_open_window(self, monkeypatch):
        mon = _monday()
        st = _tested_state()
        for rows in st["tests"].values():
            for r in rows:
                r["date"] = (mon - timedelta(days=10)).isoformat()
        st["week_plans"] = {}
        reads = []
        monkeypatch.setattr(storage.read_archived_weeks_in_range, "__wrapped__",
                            lambda uid, a, b: reads.append((a, b)) or {"x": {}})
        assert ladder_archive.load(st, "u", []) is ladder_archive.NOT_NEEDED
        assert ladder_archive.load(None, "u", [mon]) is ladder_archive.NOT_NEEDED
        got = ladder_archive.load(st, "u", [mon, mon + timedelta(days=6)])
        assert got.weeks == {"x": {}} and not got.failed
        assert reads == [(bl.archive_window_start(mon).isoformat(), ladder_archive.OPEN_END)]
        # A range already read in the request serves a narrower one.
        from backend.engine import storage_memo

        reads.clear()
        with storage_memo.request_scope():
            storage.read_archived_weeks_in_range("u", "2000-01-01", ladder_archive.OPEN_END)
            assert ladder_archive.read_range("u", "2026-01-05", "2026-02-02") == {}
            ladder_archive.read_range("v", "2026-01-05", "2026-02-02")  # another user: its own read
        assert [r[0] for r in reads] == ["2000-01-01", "2026-01-05"]
