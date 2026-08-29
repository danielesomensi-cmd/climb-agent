"""B343 — Retroactive outdoor log now syncs a past week's plan.

Bug (field-reported by Daniele, Noúfaro 2026-08-23): an outdoor log for a date
whose ISO week had already rolled into the past was written correctly to the
immutable outdoor_logs record, but _sync_plan_after_outdoor_log (B273/B277)
skipped the plan day AND the state.outdoor_log bookkeeping entry entirely —
the day stayed "planned" in /week and never counted in that week's adherence,
even though the user had explicitly reported what happened.

Fix: the past-week guard is bypassed ONLY inside _sync_plan_after_outdoor_log
— every other is_past_week() call site (replanner override/events, /week
reads) is untouched. Two safeguards ship with the bypass (covered here for the
archive-interaction case; the no-ripple case is covered in
test_b273_outdoor_finish_plan_sync.py and
test_b277_manual_outdoor_log_plan_sync.py, same fixture pattern):

  1. the next-day ripple never fires on a week that already closed;
  2. a week already moved to the A221 cold store is updated IN the cold
     store — never materialized back into hot state["week_plans"].
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


THIS_MONDAY = _monday(date.today())
# Well past the A221 hot window ({N-1, N, future}) — guaranteed archived.
ARCHIVED_MONDAY = THIS_MONDAY - timedelta(weeks=3)

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

ROUTES = [
    {"name": "Good Grip", "grade": "7c", "style": "project", "attempts": [{"result": "sent"}]},
]


def _mk_plan(monday: date, day_overrides: dict | None = None) -> dict:
    days = []
    for i, wd in enumerate(WEEKDAYS):
        d = {"date": (monday + timedelta(days=i)).isoformat(), "weekday": wd, "sessions": []}
        if day_overrides and wd in day_overrides:
            d.update(day_overrides[wd])
        days.append(d)
    return {"start_date": monday.isoformat(), "weeks": [{"week_index": 0, "days": days}]}


class TestArchivedWeekSync:
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

        self.storage = storage
        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    def _read_state(self) -> dict:
        return json.loads(self.state_path.read_text())

    def _log(self, target: str):
        res = self.client.post("/api/outdoor/log", json={
            "date": target, "spot_name": "Noúfaro", "discipline": "lead",
            "duration_minutes": 240, "routes": ROUTES,
        })
        assert res.status_code == 200, res.text
        return res.json()

    def test_archived_week_updates_cold_store_not_hot_state(self):
        """A retroactive log for a week already in the A221 cold store must
        update the archived copy, and must NOT resurrect the week into hot
        state["week_plans"] — that would defeat the archive boundary."""
        target = ARCHIVED_MONDAY.isoformat()
        plan = _mk_plan(ARCHIVED_MONDAY, {
            "mon": {"outdoor_spot_name": "Noúfaro", "outdoor_discipline": "lead",
                    "outdoor_session_status": "planned"},
        })
        # Seed the cold store directly — hot state has no entry for this week.
        self.storage.archive_week(None, target, plan)

        res = self._log(target)
        assert res["plan_synced"] is True

        state = self._read_state()
        assert ARCHIVED_MONDAY.isoformat() not in (state.get("week_plans") or {})

        archived = self.storage.read_archived_week(None, target)
        day = next(d for w in archived["weeks"] for d in w["days"] if d["date"] == target)
        assert day["outdoor_session_status"] == "done"
        assert day["outdoor_load_score"] > 0

        # Bookkeeping (used by reports) lives in hot state regardless of
        # where the plan itself was updated.
        entries = [e for e in state.get("outdoor_log", []) if e["date"] == target]
        assert len(entries) == 1

    def test_no_archived_week_still_logs_without_error(self):
        """A retroactive log for a date with no plan at all (hot or cold) —
        e.g. before the user ever had a macrocycle — must not sync (nothing
        to sync) but must still write the primary immutable record."""
        target = ARCHIVED_MONDAY.isoformat()
        res = self._log(target)
        assert res["plan_synced"] is False

        sessions = self.client.get("/api/outdoor/sessions").json()["sessions"]
        assert [s["date"] for s in sessions] == [target]

    def test_weekly_report_reflects_the_retroactive_sync(self):
        """The second half of the original bug report: a week's adherence
        must pick up a log filed after the week itself already closed. Uses
        the hot N-1 week (Daniele's actual Noúfaro case) — generate_weekly_
        report's archive lookup is gated on a real user_id, which the file-
        backend fixture here doesn't exercise; that's an orthogonal, existing
        gap, not part of this bug."""
        from backend.engine.report_engine import generate_weekly_report

        last_monday = THIS_MONDAY - timedelta(weeks=1)
        target = last_monday.isoformat()
        plan = _mk_plan(last_monday, {
            "mon": {"outdoor_spot_name": "Noúfaro", "outdoor_discipline": "lead",
                    "outdoor_session_status": "planned"},
        })
        state = self._read_state()
        state["week_plans"] = {target: plan}
        self.state_path.write_text(json.dumps(state))

        assert self._log(target)["plan_synced"] is True

        report = generate_weekly_report(self._read_state(), None, target)
        assert report["adherence"]["planned"] >= 1
        assert report["adherence"]["completed"] >= 1
