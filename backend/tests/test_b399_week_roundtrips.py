"""B399 — GET /api/week/0 with fewer storage round-trips, same response.

Two sequential Supabase round-trips were paid on every read and bought nothing:

1. **A second ``read_state`` for played custom sessions** (B375 no-op). A done
   custom / generated session has no catalog template, so ``_auto_resolve``
   leaves its ``resolved`` at None — but it was still handed to
   ``_persist_played_resolved``, which took the user lock and reloaded the
   whole state (~435 KB in prod) only for ``_cache_completed_resolved`` to skip
   it. ``_resolvable_targets`` now drops it before any I/O.
2. **Two ``outdoor_logs`` reads** — key status asked for 10 days before the
   week, the guards for 7, so the request memo (B376) could not merge them.
   The guards now ask storage for the same (wider) window and filter theirs.

The "before" of every test is the pre-B399 code put back with monkeypatch
(``_legacy``), so before and after run on the same seeded state in one test.

The outdoor spy patches ``read_outdoor_logs.__wrapped__`` — the real backend
read behind the memo wrapper — so it counts actual I/O, as in B376.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps, guard_status, key_status
from backend.api import plan_revision
from backend.api.main import app
from backend.api.routers import week as week_router
from backend.engine import storage, storage_memo

client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_STATE = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
UID = str(uuid.UUID(int=0x399, version=4))
HDR = {"X-User-ID": UID}

_STORED_RESOLVED = {"resolved_session": {"exercise_instances": [
    {"exercise_id": "weighted_pullup", "prescription": {"sets": 4, "reps": 3, "load_kg": 20}},
]}}


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    from backend.engine import resolve_session as _rs
    from backend.engine import storage_file

    monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
    monkeypatch.delenv("STORAGE_REQUEST_MEMO", raising=False)
    # B376 lesson: the resolver stamps resolved_at to the second — pin it, or
    # two reads straddling a second boundary differ.
    monkeypatch.setattr(_rs, "now_iso", lambda: "2026-10-18T12:00:00")
    yield


@pytest.fixture
def spy(monkeypatch):
    """Count state reads, real outdoor-log reads, user-lock takes and writes."""
    calls: Counter = Counter()

    real_read_state = storage.read_state

    def read_state(*a, **kw):
        calls["read_state"] += 1
        return real_read_state(*a, **kw)

    monkeypatch.setattr(storage, "read_state", read_state)

    real_write_state = storage.write_state

    def write_state(*a, **kw):
        calls["write_state"] += 1
        return real_write_state(*a, **kw)

    monkeypatch.setattr(storage, "write_state", write_state)

    wrapper = storage.read_outdoor_logs
    real_outdoor = wrapper.__wrapped__

    def read_outdoor(*a, **kw):
        calls["read_outdoor_logs"] += 1
        calls["outdoor_since:" + str(a[1] if len(a) > 1 else kw.get("since_date"))] += 1
        return real_outdoor(*a, **kw)

    monkeypatch.setattr(wrapper, "__wrapped__", read_outdoor)

    real_lock = plan_revision.user_write_lock

    def lock(user_id):
        calls["user_write_lock"] += 1
        return real_lock(user_id)

    monkeypatch.setattr(plan_revision, "user_write_lock", lock)
    return calls


def _legacy(monkeypatch) -> None:
    """Put the pre-B399 code back: every played target goes to the persist,
    and the guards read their own 7-day window."""
    monkeypatch.setattr(week_router, "_resolvable_targets", lambda week_plan, targets: list(targets))

    def legacy_outdoor_rows_for(user_id, start_date):
        if not start_date:
            return None
        ws = date.fromisoformat(str(start_date)[:10])
        return key_status._outdoor_rows(user_id, ws - timedelta(days=7), ws + timedelta(days=6))

    monkeypatch.setattr(guard_status, "outdoor_rows_for", legacy_outdoor_rows_for)


def _monday() -> date:
    d = date.today()
    return d - timedelta(days=d.weekday())


def _plan(start: date, sessions: dict) -> dict:
    days = []
    for i in range(7):
        d = (start + timedelta(days=i)).isoformat()
        days.append({"date": d, "weekday": WEEKDAYS[i], "sessions": deepcopy(sessions.get(i, []))})
    return {"start_date": start.isoformat(), "weeks": [{"week_index": 1, "days": days}],
            "profile_snapshot": {"phase_id": "strength_power", "hard_cap_per_week": 4, "recovery_multiplier": 1.0,
                                 "session_pool": ["strength_long", "limit_boulder_gym", "finger_strength_home",
                                                  "technique_focus_gym"]}}


def _custom(cs_id: str, status: str | None) -> dict:
    s = {
        "slot": "evening", "session_id": f"custom_{cs_id}", "custom_session_id": cs_id,
        "session_mode": "custom_build", "is_custom": True, "name": "Core + pull",
        "location": "home", "gym_id": None, "intensity": "medium",
        "tags": {"hard": False, "finger": False},
        "exercises": [
            {"exercise_id": "pullup", "sets": 3, "reps": 6, "rest_seconds": 120},
            {"exercise_id": "plank", "sets": 3, "work_seconds": 40, "rest_seconds": 60},
        ],
    }
    if status:
        s["status"] = status
    if status == "done":
        s["completed_at"] = "2026-10-12T19:30:00"
        s["feedback_summary"] = "ok"
    return s


def _seed(extra_played: list | None = None) -> date:
    """Current week hot, cache hit: a played custom session (never resolvable),
    a played catalog session with its stored resolution, planned sessions.
    Outdoor days straddle both look-backs (10 and 7 days)."""
    mon = _monday()
    state = json.loads(FIXTURE_STATE.read_text()) if FIXTURE_STATE.exists() else deepcopy(deps.EMPTY_TEMPLATE)
    state["macrocycle"] = {
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
    day0 = [
        _custom("cs_done", "done"),
        {"slot": "lunch", "session_id": "strength_long", "location": "home", "status": "done",
         "tags": {"hard": True, "finger": True}, "resolved": deepcopy(_STORED_RESOLVED)},
    ]
    day0.extend(extra_played or [])
    plan = _plan(mon, {
        0: day0,
        3: [{"slot": "evening", "session_id": "limit_boulder_gym", "location": "gym",
             "tags": {"hard": True, "finger": True}}],
        5: [_custom("cs_next", None)],
    })
    state["week_plans"] = {mon.isoformat(): plan}
    state["current_week_plan"] = deepcopy(plan)
    state["session_completion_log"] = []
    deps.save_state(state, UID)
    deps.load_state(UID)  # one-off load migrations land here, not in a measured read
    for back in (10, 8, 7, 2):
        storage.append_outdoor_log_line(UID, {
            "date": (mon - timedelta(days=back)).isoformat(), "spot_name": f"Crag{back}",
            "routes": [{"name": "Via", "grade": "7a", "attempts": [{"result": "sent"}]}]})
    return mon


def _get_week() -> dict:
    r = client.get("/api/week/0", headers=HDR, params={"today": date.today().isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


def _measure(spy) -> tuple:
    spy.clear()
    body = _get_week()
    return body, dict(spy)


def _stored_plan(mon: date) -> dict:
    return deepcopy(deps.load_state(UID)["week_plans"][mon.isoformat()])


class TestGetWeekRoundTrips:
    def test_before_after_counts_and_identical_response(self, spy, monkeypatch):
        mon = _seed()
        _get_week()  # warm (first read of the seeded state)

        with monkeypatch.context() as m:
            _legacy(m)
            before_body, before = _measure(spy)
        after_body, after = _measure(spy)

        print(f"B399 GET /week/0 — before: read_state={before.get('read_state', 0)} "
              f"outdoor={before.get('read_outdoor_logs', 0)} lock={before.get('user_write_lock', 0)}; "
              f"after: read_state={after.get('read_state', 0)} outdoor={after.get('read_outdoor_logs', 0)} "
              f"lock={after.get('user_write_lock', 0)}")

        # Before: the persist reloaded the state under the lock for the played
        # custom session, and the 10-day and 7-day windows were two reads.
        assert before["read_state"] == 2
        assert before["user_write_lock"] == 1
        assert before["read_outdoor_logs"] == 2
        assert before[f"outdoor_since:{(mon - timedelta(days=10)).isoformat()}"] == 1
        assert before[f"outdoor_since:{(mon - timedelta(days=7)).isoformat()}"] == 1
        # After: one state read, no lock, one outdoor read (the wider window).
        assert after["read_state"] == 1
        assert after.get("user_write_lock", 0) == 0
        assert after["read_outdoor_logs"] == 1
        assert after[f"outdoor_since:{(mon - timedelta(days=10)).isoformat()}"] == 1
        # A GET with nothing to cache writes nothing, before and after.
        assert before.get("write_state", 0) == 0 and after.get("write_state", 0) == 0

        assert json.dumps(after_body, sort_keys=True) == json.dumps(before_body, sort_keys=True)

    def test_identical_response_with_memo_off(self, monkeypatch):
        _seed()
        _get_week()
        monkeypatch.setenv("STORAGE_REQUEST_MEMO", "0")
        with monkeypatch.context() as m:
            _legacy(m)
            before = _get_week()
        after = _get_week()
        assert json.dumps(after, sort_keys=True) == json.dumps(before, sort_keys=True)

    def test_guard_and_key_outputs_see_the_outdoor_days(self):
        """The shared read still feeds both consumers (not an empty window)."""
        mon = _seed()
        guard_rows = guard_status.outdoor_rows_for(UID, mon.isoformat())
        key_rows = key_status._outdoor_rows(UID, mon - timedelta(days=10), mon + timedelta(days=6))
        assert sorted(r["date"] for r in guard_rows) == [
            (mon - timedelta(days=7)).isoformat(), (mon - timedelta(days=2)).isoformat()]
        assert sorted(r["date"] for r in key_rows) == [
            (mon - timedelta(days=b)).isoformat() for b in (10, 8, 7, 2)]


class TestPlayedSessionsImmutable:
    def test_played_custom_untouched_and_not_reloaded(self, spy):
        mon = _seed()
        seeded = _stored_plan(mon)
        spy.clear()
        body = _get_week()
        assert spy["read_state"] == 1 and spy.get("user_write_lock", 0) == 0
        assert spy.get("write_state", 0) == 0
        # Storage: the played sessions are byte-identical (no `resolved` added).
        assert _stored_plan(mon) == seeded
        served = body["week_plan"]["weeks"][0]["days"][0]["sessions"]
        done_custom = next(s for s in served if s["session_id"] == "custom_cs_done")
        assert done_custom["exercises"] == _custom("cs_done", "done")["exercises"]
        assert done_custom["status"] == "done" and not done_custom.get("resolved")
        done_catalog = next(s for s in served if s["session_id"] == "strength_long")
        assert done_catalog["resolved"] == _STORED_RESOLVED

    def test_resolvable_played_session_still_persisted_once(self, spy):
        """B375 unchanged: a played catalog session without a stored resolution
        is persisted on the first read (lock + reload), never on the next."""
        unresolved = {"slot": "morning", "session_id": "prehab_maintenance", "location": "home",
                      "status": "skipped", "skipped_at": "2026-10-12T08:00:00"}
        mon = _seed(extra_played=[unresolved])
        spy.clear()
        _get_week()
        assert spy["read_state"] == 2 and spy["user_write_lock"] == 1 and spy["write_state"] == 1
        stored = {s["session_id"]: s for s in _stored_plan(mon)["weeks"][0]["days"][0]["sessions"]}
        assert stored["prehab_maintenance"].get("resolved")
        assert "resolved" not in stored["custom_cs_done"]
        assert stored["strength_long"]["resolved"] == _STORED_RESOLVED
        cur = {s["session_id"]: s for s in deps.load_state(UID)["current_week_plan"]["weeks"][0]["days"][0]["sessions"]}
        assert cur["prehab_maintenance"]["resolved"] == stored["prehab_maintenance"]["resolved"]

        spy.clear()
        _get_week()
        assert spy["read_state"] == 1 and spy.get("user_write_lock", 0) == 0
        assert spy.get("write_state", 0) == 0


class TestResolvableTargets:
    def test_same_effect_as_all_targets(self):
        """Filtering the targets never changes what _cache_completed_resolved
        writes: it drops only targets that function would skip on the source."""
        mon = _monday()
        played = [
            _custom("a", "done"),  # resolver leaves resolved=None
            {"slot": "lunch", "session_id": "prehab_maintenance", "status": "done"},  # resolved below
            {"slot": "morning", "session_id": "finger_maintenance_home", "status": "skipped"},  # resolve error
        ]
        stored = _plan(mon, {0: played})
        served = deepcopy(stored)
        sessions = served["weeks"][0]["days"][0]["sessions"]
        targets = week_router._played_without_resolved(served)
        assert len(targets) == 3
        sessions[0]["resolved"] = None
        sessions[1]["resolved"] = deepcopy(_STORED_RESOLVED)
        sessions[2]["resolved"] = None
        sessions[2]["resolve_error"] = True
        # A target whose served session changed id is dropped too.
        targets.append((0, 0, 1, "other_id"))
        targets.append((0, 9, 0, "missing"))

        kept = week_router._resolvable_targets(served, targets)
        assert kept == [(0, 0, 1, "prehab_maintenance")]

        st_all = {"week_plans": {mon.isoformat(): deepcopy(stored)}}
        st_kept = {"week_plans": {mon.isoformat(): deepcopy(stored)}}
        dirty_all = week_router._cache_completed_resolved(served, st_all, mon.isoformat(), True, targets=targets)
        dirty_kept = week_router._cache_completed_resolved(served, st_kept, mon.isoformat(), True, targets=kept)
        assert dirty_all is dirty_kept is True
        assert st_all == st_kept

    def test_nothing_resolvable_means_no_persist(self):
        mon = _monday()
        served = _plan(mon, {0: [_custom("a", "done")]})
        targets = week_router._played_without_resolved(served)
        served["weeks"][0]["days"][0]["sessions"][0]["resolved"] = None
        assert week_router._resolvable_targets(served, targets) == []


class TestOutdoorWindow:
    def test_guard_rows_equal_legacy_window(self, spy):
        mon = _seed()
        spy.clear()
        assert not storage_memo.is_active()
        new = guard_status.outdoor_rows_for(UID, mon.isoformat())
        legacy = key_status._outdoor_rows(UID, mon - timedelta(days=7), mon + timedelta(days=6))
        assert new == legacy
        assert [r["date"] for r in new] == [(mon - timedelta(days=b)).isoformat() for b in (7, 2)]
        # The guards now ask storage for the key status's window.
        assert spy[f"outdoor_since:{(mon - timedelta(days=10)).isoformat()}"] == 1
        assert spy[f"outdoor_since:{(mon - timedelta(days=7)).isoformat()}"] == 1  # the legacy call above

    def test_key_window_unchanged(self):
        mon = _seed()
        rows = key_status._outdoor_rows(UID, mon - timedelta(days=10), mon + timedelta(days=6))
        assert [r["date"] for r in rows] == [(mon - timedelta(days=b)).isoformat() for b in (10, 8, 7, 2)]

    def test_one_read_per_request_scope(self, spy):
        mon = _seed()
        spy.clear()
        with storage_memo.request_scope():
            key_status._outdoor_rows(UID, mon - timedelta(days=10), mon + timedelta(days=6))
            guard_status.outdoor_rows_for(UID, mon.isoformat())
            guard_status.outdoor_rows_for(UID, mon.isoformat())
        assert spy["read_outdoor_logs"] == 1

    def test_rows_after_the_week_still_dropped(self):
        mon = _seed()
        storage.append_outdoor_log_line(UID, {"date": (mon + timedelta(days=7)).isoformat(),
                                              "spot_name": "Next", "routes": []})
        rows = guard_status.outdoor_rows_for(UID, mon.isoformat())
        assert all(r["date"] <= (mon + timedelta(days=6)).isoformat() for r in rows)

    def test_storage_failure_is_fail_soft(self, monkeypatch):
        def boom(*a, **kw):
            raise OSError("down")

        monkeypatch.setattr(storage.read_outdoor_logs, "__wrapped__", boom)
        assert guard_status.outdoor_rows_for(UID, _monday().isoformat()) is None
