"""B341 — multi-crag outdoor days.

Bug (found live, 2026-08-25): a day with two different crags silently lost
the first one. Two failure points, both fixed here:

1. `apply_events`'s `add_outdoor` handler unconditionally overwrote
   `day["outdoor_spot_name"]` — the second crag's `add_outdoor` (fired
   either from the manual quick-add dialog or from the active-session finish
   sync) replaced the first crag's name instead of joining it.
2. In production (Supabase), `outdoor_logs` upserted on
   `(user_id, session_date)` alone — finishing a second crag the same day
   overwrote the first crag's immutable log row (routes and all). Fixed by
   moving the unique constraint to `(user_id, session_date, spot_name)`
   (DB migration, not exercised here) and widening the file-storage read
   dedup key to match.

Scope, deliberately not covered here (documented limitation, not a bug this
brief fixes): PUT/DELETE `/api/outdoor/log/{date}` still target "the"
session for a date — on a multi-crag day they only reach the last-logged
crag. Multi-crag days are rare enough that editing/deleting an individual
crag from such a day is left as a known gap.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, timedelta

import pytest

from backend.engine.replanner_v1 import apply_events


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


THIS_MONDAY = _monday(date.today())
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

LOW_LOAD_ROUTES = [
    {"name": "easy", "grade": "5a", "style": "repeat", "attempts": [{"result": "sent"}]}
]


def _mk_plan(monday: date, day_overrides: dict | None = None) -> dict:
    days = []
    for i, wd in enumerate(WEEKDAYS):
        d = {"date": (monday + timedelta(days=i)).isoformat(), "weekday": wd, "sessions": []}
        if day_overrides and wd in day_overrides:
            d.update(deepcopy(day_overrides[wd]))
        days.append(d)
    return {"start_date": monday.isoformat(), "weeks": [{"week_index": 0, "days": days}]}


# ── apply_events: add_outdoor join/merge logic ──────────────────────────


class TestAddOutdoorMultiCrag:
    def test_second_distinct_spot_joins_with_dash(self):
        plan = _mk_plan(THIS_MONDAY)
        target = plan["weeks"][0]["days"][0]["date"]
        plan = apply_events(plan, [{
            "event_type": "add_outdoor", "date": target,
            "spot_name": "Symplegades", "discipline": "lead",
        }])
        updated = apply_events(plan, [{
            "event_type": "add_outdoor", "date": target,
            "spot_name": "Ourania", "discipline": "lead",
        }])
        day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target)
        assert day["outdoor_spot_name"] == "Symplegades - Ourania"

    def test_same_spot_added_twice_does_not_duplicate(self):
        plan = _mk_plan(THIS_MONDAY)
        target = plan["weeks"][0]["days"][0]["date"]
        for _ in range(2):
            plan = apply_events(plan, [{
                "event_type": "add_outdoor", "date": target,
                "spot_name": "Berdorf", "discipline": "lead",
            }])
        day = next(d for d in plan["weeks"][0]["days"] if d["date"] == target)
        assert day["outdoor_spot_name"] == "Berdorf"

    def test_third_distinct_spot_appends_not_replaces(self):
        plan = _mk_plan(THIS_MONDAY)
        target = plan["weeks"][0]["days"][0]["date"]
        for spot in ("Symplegades", "Ourania", "Snake Valley"):
            plan = apply_events(plan, [{
                "event_type": "add_outdoor", "date": target,
                "spot_name": spot, "discipline": "lead",
            }])
        day = next(d for d in plan["weeks"][0]["days"] if d["date"] == target)
        assert day["outdoor_spot_name"] == "Symplegades - Ourania - Snake Valley"

    def test_discipline_merges_to_both_when_crags_differ(self):
        plan = _mk_plan(THIS_MONDAY)
        target = plan["weeks"][0]["days"][0]["date"]
        plan = apply_events(plan, [{
            "event_type": "add_outdoor", "date": target,
            "spot_name": "Symplegades", "discipline": "lead",
        }])
        updated = apply_events(plan, [{
            "event_type": "add_outdoor", "date": target,
            "spot_name": "Panorama", "discipline": "boulder",
        }])
        day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target)
        assert day["outdoor_discipline"] == "both"

    def test_spot_id_keeps_first_crag(self):
        plan = _mk_plan(THIS_MONDAY)
        target = plan["weeks"][0]["days"][0]["date"]
        plan = apply_events(plan, [{
            "event_type": "add_outdoor", "date": target,
            "spot_name": "Symplegades", "discipline": "lead", "spot_id": "spot_symplegades",
        }])
        updated = apply_events(plan, [{
            "event_type": "add_outdoor", "date": target,
            "spot_name": "Ourania", "discipline": "lead", "spot_id": "spot_ourania",
        }])
        day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target)
        assert day["outdoor_spot_id"] == "spot_symplegades"


# ── End-to-end: two active-session finishes the same day ────────────────


class TestFinishTwiceSameDayKeepsBothCrags:
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

    def _start_and_finish(self, date_iso: str, spot: str):
        start = self.client.post(
            "/api/outdoor/session/start",
            json={"date": date_iso, "spot_name": spot, "discipline": "lead"},
        )
        assert start.status_code == 200
        sid = start.json()["session_id"]
        body = {"spot_name": spot, "discipline": "lead", "routes": LOW_LOAD_ROUTES,
                "duration_minutes": 60}
        fin = self.client.post(f"/api/outdoor/session/{sid}/finish", json=body)
        assert fin.status_code == 200
        return fin.json()

    def test_second_crag_does_not_overwrite_first_in_log(self):
        target = THIS_MONDAY.isoformat()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)})

        self._start_and_finish(target, "Symplegades")
        self._start_and_finish(target, "Ourania")

        log = self.client.get("/api/outdoor/sessions")
        assert log.status_code == 200
        entries = [s for s in log.json()["sessions"] if s["date"] == target]
        assert {e["spot_name"] for e in entries} == {"Symplegades", "Ourania"}

    def test_second_crag_joins_day_pointer_with_dash(self):
        target = THIS_MONDAY.isoformat()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)})

        self._start_and_finish(target, "Symplegades")
        self._start_and_finish(target, "Ourania")

        state = self._read_state()
        plan = state["week_plans"][THIS_MONDAY.isoformat()]
        day = next(d for d in plan["weeks"][0]["days"] if d["date"] == target)
        assert day["outdoor_spot_name"] == "Symplegades - Ourania"
        assert day["outdoor_session_status"] == "done"

    def test_refinishing_same_crag_stays_idempotent(self):
        target = THIS_MONDAY.isoformat()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)})

        self._start_and_finish(target, "Symplegades")
        self._start_and_finish(target, "Symplegades")

        state = self._read_state()
        plan = state["week_plans"][THIS_MONDAY.isoformat()]
        day = next(d for d in plan["weeks"][0]["days"] if d["date"] == target)
        assert day["outdoor_spot_name"] == "Symplegades"

        log = self.client.get("/api/outdoor/sessions")
        entries = [s for s in log.json()["sessions"] if s["date"] == target]
        assert len(entries) == 1
