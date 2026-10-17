"""B376 — every storage read once per request (request-scoped memo).

A warm GET /api/week made 14 sequential Supabase round-trips on a real state,
most of them identical. ``backend/engine/storage_memo.py`` memoises the storage
reads (archive weeks, outdoor logs) for the life of ONE request; writes
invalidate; outside a request nothing changes.

The spies patch ``<fn>.__wrapped__`` — the real backend function behind the
memo wrapper — so they count actual I/O, not calls to the wrapper.
"""

from __future__ import annotations

import json
import shutil
import uuid
from collections import Counter
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine import storage, storage_memo

client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_STATE = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
READS = ("read_archived_week", "list_archived_keys", "read_archived_weeks_in_range", "read_outdoor_logs")
UID = str(uuid.UUID(int=0x376, version=4))
HDR = {"X-User-ID": UID}


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    from backend.engine import storage_file

    monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
    monkeypatch.delenv("STORAGE_REQUEST_MEMO", raising=False)
    yield


@pytest.fixture
def spy(monkeypatch):
    """Count the real backend reads (behind the memo wrapper)."""
    calls: Counter = Counter()
    depth = [0]
    for name in READS:
        wrapper = getattr(storage, name)
        real = wrapper.__wrapped__

        def counting(*a, __real=real, __name=name, **kw):
            # Top-level reads only: the file backend's range read is built on
            # list_archived_keys + read_archived_week, while on Supabase it is a
            # single query — nested reads are not round-trips.
            if depth[0] == 0:
                calls[__name] += 1
            depth[0] += 1
            try:
                return __real(*a, **kw)
            finally:
                depth[0] -= 1

        monkeypatch.setattr(wrapper, "__wrapped__", counting)
    return calls


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


def _done(session_id: str, ex: str) -> dict:
    return {"slot": "evening", "session_id": session_id, "status": "done", "tags": {"hard": True, "finger": True},
            "resolved": {"resolved_session": {"exercise_instances": [{"exercise_id": ex}]}}}


def _seed() -> dict:
    """Macrocycle started 4 weeks ago; only the current week is hot, the three
    past weeks live in the cold store (A221) → the resolver tops up from the
    archive, key status / retest read the range, guards read outdoor logs."""
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
    plan = _plan(mon, {
        0: [{"slot": "evening", "session_id": "limit_boulder_gym", "tags": {"hard": True, "finger": True}}],
        3: [{"slot": "evening", "session_id": "strength_long", "tags": {"hard": True, "finger": True}}],
        5: [{"slot": "evening", "session_id": "technique_focus_gym", "tags": {"hard": False, "finger": False}}],
    })
    state["week_plans"] = {mon.isoformat(): plan}
    state["current_week_plan"] = plan
    state["session_completion_log"] = []
    deps.save_state(state, UID)
    for back in (1, 2, 3):
        ws = mon - timedelta(weeks=back)
        storage.archive_week(UID, ws.isoformat(), _plan(ws, {
            1: [_done("strength_long", "max_hang_7s")],
            4: [_done("limit_boulder_gym", "limit_bouldering")],
        }))
    for back in (2, 9):
        d = (mon - timedelta(days=back)).isoformat()
        storage.append_outdoor_log_line(UID, {"date": d, "spot_name": "Arco", "routes": [
            {"name": "Via", "grade": "7a", "attempts": [{"result": "sent"}]}]})
    return plan


def _week_num() -> int:
    return 4  # macrocycle started 3 weeks before this Monday


def _get_week() -> dict:
    r = client.get(f"/api/week/{_week_num()}", headers=HDR, params={"today": _monday().isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


def _events_dry_run(plan: dict) -> dict:
    wed = (_monday() + timedelta(days=2)).isoformat()
    r = client.post("/api/replanner/events", headers=HDR, json={
        "week_plan": plan, "dry_run": True, "today": _monday().isoformat(),
        "events": [{"event_type": "add_custom_session", "custom_session_id": "cs_hang",
                    "target_date": wed, "slot": "lunch", "location": "home"}],
    })
    assert r.status_code == 200, r.text
    return r.json()


def _measure(spy, monkeypatch, call, memo: str):
    monkeypatch.setenv("STORAGE_REQUEST_MEMO", memo)
    spy.clear()
    body = call()
    return body, dict(spy)


class TestGetWeek:
    def test_each_distinct_read_at_most_once(self, spy, monkeypatch):
        _seed()
        _get_week()  # cold call (may persist the resolved week); measure warm
        _, off = _measure(spy, monkeypatch, _get_week, "0")
        _, on = _measure(spy, monkeypatch, _get_week, "1")
        print(f"B376 GET /week reads — memo off: {off} = {sum(off.values())}, on: {on} = {sum(on.values())}")
        # Without the memo the resolver re-reads the archive once per session.
        assert off["list_archived_keys"] > 1 and off["read_archived_week"] > on["read_archived_week"]
        assert on["list_archived_keys"] == 1
        assert on["read_archived_weeks_in_range"] <= 1
        assert sum(on.values()) < sum(off.values())

    def test_response_identical_with_and_without_memo(self, monkeypatch):
        from backend.engine import resolve_session as _rs

        # The resolver stamps resolved_at to the second: pin it, or the two
        # calls differ whenever they straddle a second boundary.
        monkeypatch.setattr(_rs, "now_iso", lambda: "2026-10-17T12:00:00")
        _seed()
        _get_week()
        monkeypatch.setenv("STORAGE_REQUEST_MEMO", "0")
        off = _get_week()
        monkeypatch.setenv("STORAGE_REQUEST_MEMO", "1")
        on = _get_week()
        assert json.dumps(on, sort_keys=True) == json.dumps(off, sort_keys=True)

    def test_no_leak_across_requests(self, spy):
        _seed()
        _get_week()
        spy.clear()
        _get_week()
        first = dict(spy)
        # A write between two requests is seen by the second one.
        storage.append_outdoor_log_line(UID, {"date": (_monday() - timedelta(days=1)).isoformat(),
                                              "spot_name": "Ceredo", "routes": []})
        spy.clear()
        _get_week()
        assert dict(spy) == first  # every read is re-done: nothing survived the request
        assert not storage_memo.is_active()


class TestEventsDryRun:
    def test_dry_run_reads_once_and_matches(self, spy, monkeypatch):
        plan = _seed()
        state = deps.load_state(UID)
        state["custom_sessions"] = [{"id": "cs_hang", "name": "Hangs",
                                     "exercises": [{"exercise_id": "max_hang_7s", "sets": 5, "work_seconds": 7}]}]
        deps.save_state(state, UID)
        off_body, off = _measure(spy, monkeypatch, lambda: _events_dry_run(plan), "0")
        on_body, on = _measure(spy, monkeypatch, lambda: _events_dry_run(plan), "1")
        print(f"B376 POST /events dry_run reads — memo off: {off} = {sum(off.values())}, "
              f"on: {on} = {sum(on.values())}")
        assert json.dumps(on_body, sort_keys=True) == json.dumps(off_body, sort_keys=True)
        assert sum(on.values()) <= sum(off.values())
        assert on.get("read_archived_weeks_in_range", 0) <= 1


class TestScope:
    def test_outside_a_request_nothing_is_memoised(self, spy):
        _seed()
        assert not storage_memo.is_active()
        storage.read_outdoor_logs(UID, "2000-01-01")
        storage.read_outdoor_logs(UID, "2000-01-01")
        assert spy["read_outdoor_logs"] == 2

    def test_inside_a_scope_a_read_is_done_once(self, spy):
        _seed()
        with storage_memo.request_scope():
            a = storage.read_outdoor_logs(UID, "2000-01-01")
            b = storage.read_outdoor_logs(UID, since_date="2000-01-01")  # same bound args
            c = storage.read_outdoor_logs(UID, "2000-01-02")  # different args → own read
        assert a == b
        assert len(c) == len(a)
        assert spy["read_outdoor_logs"] == 2

    def test_write_inside_a_scope_invalidates(self, spy):
        _seed()
        mon = _monday()
        with storage_memo.request_scope():
            before = storage.read_outdoor_logs(UID, "2000-01-01")
            storage.append_outdoor_log_line(UID, {"date": mon.isoformat(), "spot_name": "Nago", "routes": []})
            after = storage.read_outdoor_logs(UID, "2000-01-01")
            keys_before = storage.list_archived_keys(UID)
            ws = (mon - timedelta(weeks=5)).isoformat()
            storage.archive_week(UID, ws, _plan(mon - timedelta(weeks=5), {}))
            keys_after = storage.list_archived_keys(UID)
            assert storage.read_archived_week(UID, ws) is not None
        assert len(after) == len(before) + 1
        assert ws in keys_after and ws not in keys_before
        assert spy["read_outdoor_logs"] == 2
        assert spy["list_archived_keys"] == 2

    def test_mutating_a_result_does_not_poison_the_memo(self):
        _seed()
        mon = _monday()
        ws = (mon - timedelta(weeks=1)).isoformat()
        with storage_memo.request_scope():
            first = storage.read_archived_week(UID, ws)
            pristine = deepcopy(first)
            first["weeks"].clear()
            first["poison"] = True
            second = storage.read_archived_week(UID, ws)
            assert second == pristine
            second["weeks"][0]["days"].clear()
            third = storage.read_archived_week(UID, ws)
            rows = storage.read_outdoor_logs(UID)
            rows.append({"date": "2099-01-01"})
            rows[0]["spot_name"] = "X"
            rows_again = storage.read_outdoor_logs(UID)
        assert third == pristine
        assert all(r.get("date") != "2099-01-01" for r in rows_again)
        assert rows_again[0]["spot_name"] == "Arco"

    def test_kill_switch(self, spy, monkeypatch):
        _seed()
        monkeypatch.setenv("STORAGE_REQUEST_MEMO", "0")
        with storage_memo.request_scope():
            assert not storage_memo.is_active()
            storage.list_archived_keys(UID)
            storage.list_archived_keys(UID)
        assert spy["list_archived_keys"] == 2

    def test_failed_read_is_not_cached(self, monkeypatch):
        calls = []

        def boom(*a, **kw):
            calls.append(1)
            raise OSError("down")

        monkeypatch.setattr(storage.list_archived_keys, "__wrapped__", boom)
        with storage_memo.request_scope():
            for _ in range(2):
                with pytest.raises(OSError):
                    storage.list_archived_keys(UID)
        assert len(calls) == 2
