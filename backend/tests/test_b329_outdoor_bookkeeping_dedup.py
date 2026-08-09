"""B329 — one `state.outdoor_log` bookkeeping row per date, on every path.

B277 made the /api/outdoor/log path idempotent, but the replanner-events path
(`complete_outdoor`) kept appending blindly. A day closed through both paths —
finish an active session, then the client's own complete_outdoor event, or
simply a double tap — left two rows for the same date.

Observed in production (2026-08-09): the state carried two rows for 2026-08-05
and two for 2026-08-08, 4 seconds apart, each with the day's full load score.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest


THIS_MONDAY = date.today() - timedelta(days=date.today().weekday())
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _mk_plan(monday: date) -> dict:
    """Week plan where every day is a planned outdoor day, so `complete_outdoor`
    has something to close on whichever date a test picks."""
    days = [
        {"date": (monday + timedelta(days=i)).isoformat(), "weekday": wd,
         "sessions": [],
         "outdoor_spot_name": "Berdorf",
         "outdoor_discipline": "lead",
         "outdoor_session_status": "planned"}
        for i, wd in enumerate(WEEKDAYS)
    ]
    return {"start_date": monday.isoformat(),
            "weeks": [{"week_index": 0, "days": days}]}


class TestBookkeepingDedup:
    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        from backend.api import deps
        from backend.engine import storage

        self.state_path = tmp_path / "user_state.json"
        self.state_path.write_text(json.dumps({
            "schema_version": "1.5",
            "outdoor_spots": [],
            "week_plans": {THIS_MONDAY.isoformat(): _mk_plan(THIS_MONDAY)},
        }))
        monkeypatch.setattr(storage, "STATE_PATH", self.state_path)
        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        monkeypatch.setattr(storage, "USERS_DIR", tmp_path / "users")
        monkeypatch.setattr(deps, "STATE_PATH", self.state_path)

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    def _complete_outdoor(self, date_iso: str, load: int = 30):
        res = self.client.post("/api/replanner/events", json={
            "week_plan": _mk_plan(THIS_MONDAY),
            "events": [{
                "event_type": "complete_outdoor",
                "date": date_iso,
                "spot_name": "Berdorf",
                "discipline": "lead",
                "outdoor_load_score": load,
            }],
        })
        assert res.status_code == 200, res.text
        return res

    def _rows_for(self, date_iso: str):
        state = json.loads(self.state_path.read_text())
        return [e for e in state.get("outdoor_log", []) if e.get("date") == date_iso]

    def test_single_complete_writes_one_row(self):
        target = THIS_MONDAY.isoformat()
        self._complete_outdoor(target)
        assert len(self._rows_for(target)) == 1

    def test_double_tap_does_not_duplicate(self):
        """The production symptom: two events seconds apart, two rows."""
        target = THIS_MONDAY.isoformat()
        self._complete_outdoor(target)
        self._complete_outdoor(target)
        assert len(self._rows_for(target)) == 1

    def test_relog_keeps_the_latest_load_score(self):
        target = THIS_MONDAY.isoformat()
        self._complete_outdoor(target, load=20)
        self._complete_outdoor(target, load=45)
        rows = self._rows_for(target)
        assert len(rows) == 1
        assert rows[0]["load_score"] == 45

    def test_historical_duplicates_are_cleaned_on_rewrite(self):
        target = THIS_MONDAY.isoformat()
        state = json.loads(self.state_path.read_text())
        state["outdoor_log"] = [
            {"date": target, "spot_name": "Berdorf", "load_score": 22},
            {"date": target, "spot_name": "Berdorf", "load_score": 22},
        ]
        self.state_path.write_text(json.dumps(state))

        self._complete_outdoor(target, load=33)
        rows = self._rows_for(target)
        assert len(rows) == 1
        assert rows[0]["load_score"] == 33

    def test_other_dates_are_left_alone(self):
        d1 = THIS_MONDAY.isoformat()
        d2 = (THIS_MONDAY + timedelta(days=2)).isoformat()
        self._complete_outdoor(d1, load=20)
        self._complete_outdoor(d2, load=40)
        self._complete_outdoor(d1, load=25)

        assert len(self._rows_for(d1)) == 1
        assert len(self._rows_for(d2)) == 1
        assert self._rows_for(d2)[0]["load_score"] == 40
