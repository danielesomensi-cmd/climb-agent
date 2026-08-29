"""B273 — Outdoor active-session finish closes the loop on the week plan.

Bug: the A225 active-session flow (/outdoor/[date] → POST /session/{id}/finish)
wrote the immutable outdoor log but never marked the plan day done — that side
effect lived only in the frontend form flow (today/week → applyEvents
complete_outdoor). Result: routes invisible in /today//week, no load score on
the day, no ripple, wrong weekly report status.

Fix: finish now emits the same replanner events server-side (add_outdoor
fallback + complete_outdoor), best-effort after the log write.

Invariants verified here: past weeks immutable (B257), paused plan untouched
(A223), done sessions never replaced by ripple (B120), log write never blocked
by plan-sync failures.
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
]  # load 72 ≥ ripple threshold 65
LOW_LOAD_ROUTES = [
    {"name": "easy", "grade": "5a", "style": "repeat", "attempts": [{"result": "sent"}]}
]  # load 1


def _mk_plan(monday: date, day_overrides: dict | None = None) -> dict:
    """Minimal planner-shaped week plan (weeks[0].days, 7 days)."""
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

    # -- helpers ----------------------------------------------------------

    def _write_state(self, **extra):
        state = json.loads(self.state_path.read_text())
        state.update(extra)
        self.state_path.write_text(json.dumps(state))

    def _read_state(self) -> dict:
        return json.loads(self.state_path.read_text())

    def _plan_day(self, state: dict, monday: date, date_iso: str) -> dict:
        plan = state["week_plans"][monday.isoformat()]
        return next(
            d for w in plan["weeks"] for d in w["days"] if d["date"] == date_iso
        )

    def _start_and_finish(self, date_iso: str, routes, spot="Berdorf", extra_finish=None):
        start = self.client.post(
            "/api/outdoor/session/start",
            json={"date": date_iso, "spot_name": spot, "discipline": "lead"},
        )
        assert start.status_code == 200
        sid = start.json()["session_id"]
        body = {"spot_name": spot, "discipline": "lead", "routes": routes,
                "duration_minutes": 300}
        if extra_finish:
            body.update(extra_finish)
        fin = self.client.post(f"/api/outdoor/session/{sid}/finish", json=body)
        assert fin.status_code == 200
        return fin.json()


class TestFinishClosesLoop(_Base):
    def test_planned_outdoor_day_marked_done_with_load(self):
        target = THIS_MONDAY.isoformat()
        plan = _mk_plan(THIS_MONDAY, {
            "mon": {"outdoor_spot_name": "Berdorf", "outdoor_discipline": "lead",
                    "outdoor_session_status": "planned"},
        })
        self._write_state(week_plans={THIS_MONDAY.isoformat(): plan})

        res = self._start_and_finish(target, LOW_LOAD_ROUTES)
        assert res["plan_synced"] is True

        day = self._plan_day(self._read_state(), THIS_MONDAY, target)
        assert day["outdoor_session_status"] == "done"
        assert day["outdoor_load_score"] == res["load_score"]

    def test_unplanned_day_gets_add_outdoor_then_done(self):
        target = THIS_MONDAY.isoformat()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)})

        res = self._start_and_finish(target, LOW_LOAD_ROUTES, spot="Freyr")
        assert res["plan_synced"] is True

        day = self._plan_day(self._read_state(), THIS_MONDAY, target)
        assert day["outdoor_spot_name"] == "Freyr"
        assert day["outdoor_discipline"] == "lead"
        assert day["outdoor_session_status"] == "done"

    def test_b116_outdoor_log_entry_appended(self):
        target = THIS_MONDAY.isoformat()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)})

        self._start_and_finish(target, LOW_LOAD_ROUTES)
        state = self._read_state()
        entries = [e for e in state.get("outdoor_log", []) if e["date"] == target]
        assert len(entries) == 1
        assert entries[0]["spot_name"] == "Berdorf"

    def test_legacy_response_fields_unchanged(self):
        """The pre-B273 finish response fields are all still present."""
        target = THIS_MONDAY.isoformat()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)})
        res = self._start_and_finish(target, LOW_LOAD_ROUTES)
        for key in ("status", "date", "duration_minutes", "duration_capped",
                    "duration_raw_minutes", "duration_source", "load_score"):
            assert key in res
        assert res["status"] == "done"


class TestInvariantGuards(_Base):
    def test_past_week_now_syncs_but_never_ripples(self):
        """B343: a log for a past week DOES sync the plan day now — the
        immutable outdoor_logs record is an explicit user action reporting
        what really happened, the one exception B257 carves out. The
        next-day ripple (meant for a plan still being built) stays off."""
        target = LAST_MONDAY.isoformat()
        plan = _mk_plan(LAST_MONDAY, {
            "mon": {"outdoor_spot_name": "Berdorf", "outdoor_discipline": "lead",
                    "outdoor_session_status": "planned"},
            "tue": {"sessions": [deepcopy(TestRipple.HARD_TUE_SESSION)]},
        })
        self._write_state(week_plans={LAST_MONDAY.isoformat(): plan})

        res = self._start_and_finish(target, HIGH_LOAD_ROUTES)  # over ripple threshold
        assert res["plan_synced"] is True

        day = self._plan_day(self._read_state(), LAST_MONDAY, target)
        assert day["outdoor_session_status"] == "done"
        assert day["outdoor_load_score"] == res["load_score"]

        # No ripple onto the next day of a week that already closed.
        tue = self._plan_day(
            self._read_state(), LAST_MONDAY, (LAST_MONDAY + timedelta(days=1)).isoformat(),
        )
        assert tue["sessions"][0]["session_id"] == "finger_strength_home"

        sessions = self.client.get("/api/outdoor/sessions").json()["sessions"]
        assert [s["date"] for s in sessions] == [target]

    def test_paused_plan_skips_sync_but_logs(self):
        """A223: no plan mutation while paused; the log still lands."""
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

        res = self._start_and_finish(target, LOW_LOAD_ROUTES)
        assert res["plan_synced"] is False
        assert self._read_state()["week_plans"][THIS_MONDAY.isoformat()] == snapshot
        sessions = self.client.get("/api/outdoor/sessions").json()["sessions"]
        assert len(sessions) == 1

    def test_no_week_plan_still_logs(self):
        target = THIS_MONDAY.isoformat()
        res = self._start_and_finish(target, LOW_LOAD_ROUTES)
        assert res["plan_synced"] is False
        sessions = self.client.get("/api/outdoor/sessions").json()["sessions"]
        assert len(sessions) == 1

    def test_sync_failure_never_blocks_the_log(self, monkeypatch):
        """The log write is the primary record — plan-sync explosions are caught."""
        import backend.api.routers.outdoor as outdoor_router

        def boom(*a, **kw):
            raise RuntimeError("sync exploded")

        monkeypatch.setattr(outdoor_router, "_sync_plan_after_outdoor_log", boom)
        target = THIS_MONDAY.isoformat()
        res = self._start_and_finish(target, LOW_LOAD_ROUTES)
        assert res["status"] == "done"
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

        res = self._start_and_finish(target, HIGH_LOAD_ROUTES)
        assert res["plan_synced"] is True
        assert res["load_score"] >= 65  # precondition: over ripple threshold

        tue = self._plan_day(
            self._read_state(), THIS_MONDAY,
            (THIS_MONDAY + timedelta(days=1)).isoformat(),
        )
        assert tue["sessions"][0]["session_id"] == "complementary_conditioning"
        assert "outdoor_ripple" in tue["sessions"][0]["constraints_applied"]

    def test_low_load_no_ripple(self):
        target = THIS_MONDAY.isoformat()
        plan = _mk_plan(THIS_MONDAY, {
            "mon": {"outdoor_spot_name": "Berdorf", "outdoor_discipline": "lead",
                    "outdoor_session_status": "planned"},
            "tue": {"sessions": [deepcopy(self.HARD_TUE_SESSION)]},
        })
        self._write_state(week_plans={THIS_MONDAY.isoformat(): plan})

        self._start_and_finish(target, LOW_LOAD_ROUTES)
        tue = self._plan_day(
            self._read_state(), THIS_MONDAY,
            (THIS_MONDAY + timedelta(days=1)).isoformat(),
        )
        assert tue["sessions"][0]["session_id"] == "finger_strength_home"

    def test_ripple_never_touches_done_sessions(self):
        """B120: completed sessions survive the ripple untouched."""
        done_session = deepcopy(self.HARD_TUE_SESSION)
        done_session["status"] = "done"
        target = THIS_MONDAY.isoformat()
        plan = _mk_plan(THIS_MONDAY, {
            "mon": {"outdoor_spot_name": "Berdorf", "outdoor_discipline": "lead",
                    "outdoor_session_status": "planned"},
            "tue": {"sessions": [deepcopy(done_session)]},
        })
        self._write_state(week_plans={THIS_MONDAY.isoformat(): plan})

        self._start_and_finish(target, HIGH_LOAD_ROUTES)
        tue = self._plan_day(
            self._read_state(), THIS_MONDAY,
            (THIS_MONDAY + timedelta(days=1)).isoformat(),
        )
        assert tue["sessions"][0]["session_id"] == "finger_strength_home"
        assert tue["sessions"][0]["status"] == "done"
