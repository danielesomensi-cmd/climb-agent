"""B334 — the plan sync respects the subscription guard; editing your own data does not.

Finding OUTDOOR-PUT-UNGATED (D278). `POST /api/outdoor/log` carries
require_active_subscription, `PUT /api/outdoor/log` does not — and that
asymmetry is deliberate: across this codebase the guard protects *training*
actions while reading, editing and deleting your own data stays free
(`/api/user/export`, `PUT /api/state`, the free_session DELETEs).

What was riding along on that freedom is the plan mutation. `_sync_plan_after_
outdoor_log` marks the day done, writes the load and applies the ripple — the
resource the guard exists to protect — so an expired subscription could reach it
through the ungated PUT.

The fix gates the *side effect*, not the endpoint. These tests pin both halves:
the plan stops moving, and the athlete keeps custody of their own log.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, timedelta

import pytest


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


THIS_MONDAY = _monday(date.today())
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

ROUTES = [
    {"name": "Heintz", "grade": "6c", "style": "repeat", "attempts": [{"result": "sent"}]}
]


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
        self.monkeypatch = monkeypatch

    def _deny_subscription(self):
        """Make check_subscription report a lapsed subscription.

        Patched on the outdoor router's own import site: the function is
        imported inside _sync_plan_after_outdoor_log, so the name is resolved
        from backend.engine.subscription_guard at call time.
        """
        from backend.engine import subscription_guard

        self.monkeypatch.setattr(
            subscription_guard, "check_subscription",
            lambda uid: {"status": "expired", "is_active": False, "can_interact": False,
                         "trial_days_remaining": None, "has_payment_method": False},
        )

    def _write_state(self, **extra):
        state = json.loads(self.state_path.read_text())
        state.update(extra)
        self.state_path.write_text(json.dumps(state))

    def _read_state(self) -> dict:
        return json.loads(self.state_path.read_text())

    def _day(self, date_iso: str) -> dict:
        plan = self._read_state()["week_plans"][THIS_MONDAY.isoformat()]
        return next(d for w in plan["weeks"] for d in w["days"] if d["date"] == date_iso)

    def _seed_planned_day(self, date_iso: str):
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY, {
            "mon": {"outdoor_spot_name": "Berdorf", "outdoor_discipline": "lead",
                    "outdoor_session_status": "planned"},
        })})

    def _body(self, date_iso: str, spot="Berdorf"):
        return {"date": date_iso, "spot_name": spot, "discipline": "lead",
                "duration_minutes": 300, "routes": ROUTES}


class TestPlanSyncRespectsSubscription(_Base):
    def test_lapsed_subscription_does_not_move_the_plan(self):
        target = THIS_MONDAY.isoformat()
        self._seed_planned_day(target)
        assert self.client.post("/api/outdoor/log", json=self._body(target)).status_code == 200
        assert self._day(target)["outdoor_session_status"] == "done"

        # Now the subscription lapses and the athlete edits the same day.
        self._deny_subscription()
        self._write_state(week_plans={THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY, {
            "mon": {"outdoor_spot_name": "Berdorf", "outdoor_discipline": "lead",
                    "outdoor_session_status": "planned"},
        })})
        res = self.client.put("/api/outdoor/log", json=self._body(target))

        assert res.status_code == 200, res.text
        assert res.json()["plan_synced"] is False
        assert self._day(target)["outdoor_session_status"] == "planned", (
            "the ungated PUT still moved the plan"
        )

    def test_lapsed_subscription_still_keeps_the_log(self):
        """Data custody is the other half: the edit itself must land."""
        target = THIS_MONDAY.isoformat()
        self._seed_planned_day(target)
        self.client.post("/api/outdoor/log", json=self._body(target))

        self._deny_subscription()
        res = self.client.put(
            "/api/outdoor/log", json=self._body(target, spot="Paderno")
        )
        assert res.status_code == 200, res.text

        got = self.client.get(f"/api/outdoor/log/{target}")
        assert got.status_code == 200, got.text
        assert got.json()["session"]["spot_name"] == "Paderno", (
            "gating the side effect must not cost the athlete their own edit"
        )

    def test_active_subscription_still_syncs(self):
        """No regression for everyone who is actually paying or in trial."""
        target = THIS_MONDAY.isoformat()
        self._seed_planned_day(target)
        res = self.client.post("/api/outdoor/log", json=self._body(target))
        assert res.json()["plan_synced"] is True
        assert self._day(target)["outdoor_session_status"] == "done"
