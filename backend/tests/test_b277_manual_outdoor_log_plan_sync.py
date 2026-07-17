"""B277 — Manual outdoor log closes the loop on the week plan.

Bug (field-reported by Daniele): logging an outdoor session via the manual form
(POST /api/outdoor/log) wrote the immutable log but left the plan day at
"planned" — only the active-session finish flow (B273) synced the plan. Result:
the logged routes never surfaced in the Week view (which renders outdoor off the
plan day's outdoor_session_status == "done", not off the log).

Fix: POST /log and PUT /log now call the same best-effort _sync_plan_after_
outdoor_log the finish flow uses. Bookkeeping (state.outdoor_log) is deduped to
one entry per date so re-logs / edits don't stack duplicates.

Mirrors the invariant guards from test_b273_outdoor_finish_plan_sync.py: past
weeks immutable (B257), paused plan untouched (A223), log never blocked by a
plan-sync failure.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, timedelta

import pytest


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


THIS_MONDAY = _monday(date.today())
LAST_MONDAY = THIS_MONDAY - timedelta(weeks=1)

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

HIGH_LOAD_ROUTES = [
    {"name": f"r{i}", "grade": "8b", "style": "onsight", "attempts": [{"result": "sent"}]}
    for i in range(12)
]  # load ≥ ripple threshold 65
LOW_LOAD_ROUTES = [
    {"name": "easy", "grade": "5a", "style": "repeat", "attempts": [{"result": "sent"}]}
]  # load 1


def _mk_plan(monday: date, day_overrides: dict | None = None) -> dict:
    days = []
    for i, wd in enumerate(WEEKDAYS):
        d = {"date": (monday + timedelta(days=i)).isoformat(), "weekday": wd, "sessions": []}
        if day_overrides and wd in day_overrides:
            d.update(deepcopy(day_overrides[wd]))
        days.append(d)
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

    def _plan_day(self, state: dict, monday: date, date_iso: str) -> dict:
        plan = state["week_plans"][monday.isoformat()]
        return next(d for w in plan["weeks"] for d in w["days"] if d["date"] == date_iso)

    def _post_log(self, date_iso: str, routes, spot="Berdorf"):
        res = self.client.post("/api/outdoor/log", json={
            "date": date_iso, "spot_name": spot, "discipline": "lead",
            "duration_minutes": 300, "routes": routes,
        })
        assert res.status_code == 200, res.text
        return res.json()

    def _put_log(self, date_iso: str, routes, spot="Berdorf"):
        res = self.client.put("/api/outdoor/log", json={
            "date": date_iso, "spot_name": spot, "discipline": "lead",
            "duration_minutes": 300, "routes": routes,
        })
        assert res.status_code == 200, res.text
        return res.json()


class TestManualLogClosesLoop(_Base):
    def test_planned_day_marked_done_with_load(self):
        target = THIS_MONDAY.isoformat()
        plan = _mk_plan(THIS_MONDAY, {
            "mon": {"outdoor_spot_name": "Berdorf", "outdoor_discipline": "lead",
                    "outdoor_session_status": "planned"},
        })
        self._write_state(week_plans={THIS_MONDAY.isoformat(): plan})

        res = self._post_log(target, LOW_LOAD_ROUTES)
        assert res["plan_synced"] is True

        day = self._plan_day(self._read_state(), THIS_MONDAY, target)
        assert day["outdoor_session_status"] == "done"
        assert day["outdoor_load_score"] > 0

    def test_unplanned_day_gets_add_outdoor_then_done(self):
        target = THIS_MONDAY.isoformat()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)})

        res = self._post_log(target, LOW_LOAD_ROUTES, spot="Freyr")
        assert res["plan_synced"] is True

        day = self._plan_day(self._read_state(), THIS_MONDAY, target)
        assert day["outdoor_spot_name"] == "Freyr"
        assert day["outdoor_session_status"] == "done"

    def test_bookkeeping_single_entry(self):
        target = THIS_MONDAY.isoformat()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)})
        self._post_log(target, LOW_LOAD_ROUTES)
        entries = [e for e in self._read_state().get("outdoor_log", []) if e["date"] == target]
        assert len(entries) == 1
        assert entries[0]["spot_name"] == "Berdorf"

    def test_edit_then_relog_does_not_duplicate_bookkeeping(self):
        """PUT after POST keeps bookkeeping at one entry per date (dedupe)."""
        target = THIS_MONDAY.isoformat()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)})
        self._post_log(target, LOW_LOAD_ROUTES)
        res = self._put_log(target, HIGH_LOAD_ROUTES)
        assert res["plan_synced"] is True
        entries = [e for e in self._read_state().get("outdoor_log", []) if e["date"] == target]
        assert len(entries) == 1
        day = self._plan_day(self._read_state(), THIS_MONDAY, target)
        assert day["outdoor_session_status"] == "done"


class TestInvariantGuards(_Base):
    def test_past_week_plan_untouched(self):
        target = LAST_MONDAY.isoformat()
        plan = _mk_plan(LAST_MONDAY, {
            "mon": {"outdoor_spot_name": "Berdorf", "outdoor_discipline": "lead",
                    "outdoor_session_status": "planned"},
        })
        snapshot = deepcopy(plan)
        self._write_state(week_plans={LAST_MONDAY.isoformat(): plan})

        res = self._post_log(target, LOW_LOAD_ROUTES)
        assert res["plan_synced"] is False
        assert self._read_state()["week_plans"][LAST_MONDAY.isoformat()] == snapshot
        # Log still written (primary record).
        sessions = self.client.get("/api/outdoor/sessions").json()["sessions"]
        assert [s["date"] for s in sessions] == [target]

    def test_paused_plan_skips_sync_but_logs(self):
        target = THIS_MONDAY.isoformat()
        plan = _mk_plan(THIS_MONDAY, {
            "mon": {"outdoor_spot_name": "Berdorf", "outdoor_discipline": "lead",
                    "outdoor_session_status": "planned"},
        })
        snapshot = deepcopy(plan)
        self._write_state(
            week_plans={THIS_MONDAY.isoformat(): plan},
            macrocycle={"start_date": THIS_MONDAY.isoformat(), "phases": [],
                        "pause": {"active_since": THIS_MONDAY.isoformat(),
                                  "offset_days": 0, "log": []}},
        )
        res = self._post_log(target, LOW_LOAD_ROUTES)
        assert res["plan_synced"] is False
        assert self._read_state()["week_plans"][THIS_MONDAY.isoformat()] == snapshot

    def test_no_week_plan_still_logs(self):
        target = THIS_MONDAY.isoformat()
        res = self._post_log(target, LOW_LOAD_ROUTES)
        assert res["plan_synced"] is False
        sessions = self.client.get("/api/outdoor/sessions").json()["sessions"]
        assert len(sessions) == 1

    def test_sync_failure_never_blocks_the_log(self, monkeypatch):
        import backend.api.routers.outdoor as outdoor_router

        def boom(*a, **kw):
            raise RuntimeError("sync exploded")

        monkeypatch.setattr(outdoor_router, "_sync_plan_after_outdoor_log", boom)
        target = THIS_MONDAY.isoformat()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)})
        res = self._post_log(target, LOW_LOAD_ROUTES)
        assert res["status"] == "ok"
        assert res["plan_synced"] is False
        sessions = self.client.get("/api/outdoor/sessions").json()["sessions"]
        assert len(sessions) == 1


class TestRipple(_Base):
    HARD_TUE_SESSION = {
        "session_id": "finger_strength_home", "slot": "evening", "location": "home",
        "status": "planned", "intensity": "high", "tags": {"hard": True, "finger": True},
    }

    def test_high_load_ripples_next_day(self):
        target = THIS_MONDAY.isoformat()
        plan = _mk_plan(THIS_MONDAY, {
            "mon": {"outdoor_spot_name": "Berdorf", "outdoor_discipline": "lead",
                    "outdoor_session_status": "planned"},
            "tue": {"sessions": [deepcopy(self.HARD_TUE_SESSION)]},
        })
        self._write_state(week_plans={THIS_MONDAY.isoformat(): plan})

        res = self._post_log(target, HIGH_LOAD_ROUTES)
        assert res["plan_synced"] is True

        tue = self._plan_day(
            self._read_state(), THIS_MONDAY, (THIS_MONDAY + timedelta(days=1)).isoformat(),
        )
        assert tue["sessions"][0]["session_id"] == "complementary_conditioning"
        assert "outdoor_ripple" in tue["sessions"][0]["constraints_applied"]
