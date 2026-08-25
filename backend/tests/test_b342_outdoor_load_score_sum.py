"""B342 — day-level outdoor_load_score must sum every crag, not pick one.

Found live while verifying B341 (multi-crag days): once storage correctly
keeps one log entry per crag, two call sites that compute the DAY's
outdoor_load_score turned out to still assume a single entry per date —
the same bug class B341 fixed for outdoor_spot_name, just for the load
number instead of the label:

1. `outdoor.py::_sync_plan_after_outdoor_log` (active-session finish / manual
   POST-log path) passed only the just-finished session's own score as the
   day's total, silently dropping any other crag logged earlier that day.
2. `replanner.py`'s `/api/replanner/events` handler recomputed the day's
   score from `matching[-1]` — the *last* entry for that date in whatever
   order the log read returns, arbitrary once a date can hold more than one
   row (confirmed live: this returned different crags across two identical
   requests once B341 let a date hold multiple rows).

Per-session load_score (e.g. what `POST .../finish` returns to the client
for that one session) is untouched — only the day-level aggregate changes.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from backend.engine.outdoor_log import compute_outdoor_load_score


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


THIS_MONDAY = _monday(date.today())
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

ROUTES_A = [
    {"name": "r1", "grade": "6c+", "style": "onsight", "attempts": [{"result": "sent"}]},
    {"name": "r2", "grade": "6b", "style": "repeat", "attempts": [{"result": "sent"}]},
]
ROUTES_B = [
    {"name": "r3", "grade": "7a", "style": "onsight", "attempts": [{"result": "sent"}]},
    {"name": "r4", "grade": "7a+", "style": "redpoint", "attempts": [{"result": "fell"}, {"result": "sent"}]},
]

EXPECTED_A = compute_outdoor_load_score({"routes": ROUTES_A})
EXPECTED_B = compute_outdoor_load_score({"routes": ROUTES_B})


def _mk_plan(monday: date) -> dict:
    days = []
    for i, wd in enumerate(WEEKDAYS):
        days.append({"date": (monday + timedelta(days=i)).isoformat(), "weekday": wd, "sessions": []})
    return {"start_date": monday.isoformat(), "weeks": [{"week_index": 0, "days": days}]}


class _Base:
    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        from backend.api import deps
        from backend.engine import storage

        self.state_path = tmp_path / "user_state.json"
        self.state_path.write_text(json.dumps({"schema_version": "1.5", "outdoor_spots": []}))
        monkeypatch.setattr(storage, "STATE_PATH", self.state_path)
        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        monkeypatch.setattr(storage, "USERS_DIR", tmp_path / "users")
        monkeypatch.setattr(deps, "STATE_PATH", self.state_path)

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    def _write_state(self, **extra):
        state = json.loads(self.state_path.read_text())
        state.update(extra)
        self.state_path.write_text(json.dumps(state))

    def _read_state(self) -> dict:
        return json.loads(self.state_path.read_text())

    def _day(self, target: str) -> dict:
        plan = self._read_state()["week_plans"][THIS_MONDAY.isoformat()]
        return next(d for d in plan["weeks"][0]["days"] if d["date"] == target)

    def _start_and_finish(self, date_iso: str, spot: str, routes: list):
        start = self.client.post(
            "/api/outdoor/session/start",
            json={"date": date_iso, "spot_name": spot, "discipline": "lead"},
        )
        assert start.status_code == 200
        sid = start.json()["session_id"]
        body = {"spot_name": spot, "discipline": "lead", "routes": routes, "duration_minutes": 60}
        fin = self.client.post(f"/api/outdoor/session/{sid}/finish", json=body)
        assert fin.status_code == 200
        return fin.json()


class TestFinishSyncSumsAcrossCrags(_Base):
    def test_second_crag_finish_sums_day_load_not_replaces(self):
        target = THIS_MONDAY.isoformat()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)})

        self._start_and_finish(target, "Symplegades", ROUTES_A)
        self._start_and_finish(target, "Ourania", ROUTES_B)

        day = self._day(target)
        assert day["outdoor_load_score"] == EXPECTED_A + EXPECTED_B

    def test_own_session_response_stays_per_session_not_day_total(self):
        target = THIS_MONDAY.isoformat()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)})

        res_a = self._start_and_finish(target, "Symplegades", ROUTES_A)
        assert res_a["load_score"] == EXPECTED_A

        res_b = self._start_and_finish(target, "Ourania", ROUTES_B)
        # The client response for THIS finish is still this session's own
        # score — only the plan's day-level field becomes the sum.
        assert res_b["load_score"] == EXPECTED_B


class TestReplannerEventsSumsAcrossCrags(_Base):
    def test_manual_complete_outdoor_event_sums_all_crags_for_that_date(self):
        target = THIS_MONDAY.isoformat()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)})

        self._start_and_finish(target, "Symplegades", ROUTES_A)
        self._start_and_finish(target, "Ourania", ROUTES_B)

        plan = self._read_state()["week_plans"][THIS_MONDAY.isoformat()]
        res = self.client.post("/api/replanner/events", json={
            "events": [{"event_type": "complete_outdoor", "date": target}],
            "week_plan": plan,
        })
        assert res.status_code == 200
        day = next(
            d for w in res.json()["week_plan"]["weeks"] for d in w["days"] if d["date"] == target
        )
        assert day["outdoor_load_score"] == EXPECTED_A + EXPECTED_B
