"""A236 (A-GAMIFY-03) — monthly heatmap engine + endpoint.

Covers the rest-positive day classification (done / planned / skipped / rest /
rest_planned / none), load aggregation across sources, cold-store fallback,
and the API contract.
"""

from __future__ import annotations

import shutil
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.engine.report_engine import _heatmap_day_cell, generate_monthly_heatmap

client = TestClient(app)

_TEST_USER_ID = "00000000-0000-4000-a000-000000000236"

TODAY = "2026-07-15"


@pytest.fixture(autouse=True)
def _cleanup_test_users():
    yield
    from backend.api.deps import USERS_DIR

    shutil.rmtree(USERS_DIR / _TEST_USER_ID, ignore_errors=True)


def _day(date_iso: str, sessions=None, **extra):
    return {"date": date_iso, "weekday": "mon", "sessions": sessions or [], **extra}


class TestDayCell:
    def test_done_session_sums_load(self):
        day = _day(
            "2026-07-10",
            sessions=[
                {"status": "done", "session_load_score": 25},
                {"status": "skipped", "estimated_load_score": 10},
            ],
        )
        cell = _heatmap_day_cell(day, "2026-07-10", TODAY, 0.0, None)
        assert cell == {"date": "2026-07-10", "status": "done", "load": 25}

    def test_done_falls_back_to_estimated_load(self):
        day = _day("2026-07-10", sessions=[{"status": "done", "estimated_load_score": 18}])
        cell = _heatmap_day_cell(day, "2026-07-10", TODAY, 0.0, None)
        assert cell["load"] == 18

    def test_past_scheduled_not_done_is_skipped(self):
        day = _day("2026-07-10", sessions=[{"status": "skipped"}])
        assert _heatmap_day_cell(day, "2026-07-10", TODAY, 0.0, None)["status"] == "skipped"

    def test_future_scheduled_is_planned(self):
        day = _day("2026-07-20", sessions=[{"status": "planned"}])
        assert _heatmap_day_cell(day, "2026-07-20", TODAY, 0.0, None)["status"] == "planned"

    def test_today_scheduled_not_done_is_planned_not_skipped(self):
        day = _day(TODAY, sessions=[{"status": "planned"}])
        assert _heatmap_day_cell(day, TODAY, TODAY, 0.0, None)["status"] == "planned"

    def test_past_empty_in_plan_day_is_rest_respected(self):
        day = _day("2026-07-10")
        assert _heatmap_day_cell(day, "2026-07-10", TODAY, 0.0, None)["status"] == "rest"

    def test_future_empty_in_plan_day_is_rest_planned(self):
        day = _day("2026-07-20")
        assert _heatmap_day_cell(day, "2026-07-20", TODAY, 0.0, None)["status"] == "rest_planned"

    def test_no_plan_no_activity_is_none(self):
        assert _heatmap_day_cell(None, "2026-07-10", TODAY, 0.0, None)["status"] == "none"

    def test_free_session_only_day_is_done(self):
        # A free session on a rest/none day must not read as "rest respected"
        cell = _heatmap_day_cell(None, "2026-07-10", TODAY, 12.5, None)
        assert cell["status"] == "done"
        assert cell["load"] == 12.5

    def test_outdoor_done_on_plan_uses_plan_load_not_log(self):
        day = _day("2026-07-10", outdoor_session_status="done", outdoor_load_score=21)
        cell = _heatmap_day_cell(day, "2026-07-10", TODAY, 0.0, 99.0)
        assert cell["status"] == "done"
        assert cell["load"] == 21  # plan value wins — no double count

    def test_outdoor_logged_without_plan_sync_counts(self):
        # Pre-B277 history: plan day still "planned" but outdoor log exists
        day = _day("2026-07-10", outdoor_slot=True)
        cell = _heatmap_day_cell(day, "2026-07-10", TODAY, 0.0, 21.0)
        assert cell["status"] == "done"
        assert cell["load"] == 21

    def test_completed_other_activity_is_done(self):
        day = _day(
            "2026-07-10",
            other_activities=[{"slot": "evening", "name": "HIIT", "status": "completed", "load": 8}],
        )
        cell = _heatmap_day_cell(day, "2026-07-10", TODAY, 0.0, None)
        assert cell["status"] == "done"
        assert cell["load"] == 8


class TestGenerator:
    def _state_with_week(self, monday: str, days):
        return {
            "week_plans": {monday: {"weeks": [{"days": days}]}},
            "free_sessions": [],
        }

    def test_month_shape_and_plan_days(self):
        # July 2026: 2026-07-06 is a Monday
        days = [_day(f"2026-07-{6 + i:02d}") for i in range(7)]
        days[0]["sessions"] = [{"status": "done", "session_load_score": 30}]
        state = self._state_with_week("2026-07-06", days)
        out = generate_monthly_heatmap(state, None, "2026-07")
        assert out["month"] == "2026-07"
        assert len(out["days"]) == 31
        by_date = {c["date"]: c for c in out["days"]}
        assert by_date["2026-07-06"]["status"] == "done"
        assert by_date["2026-07-06"]["load"] == 30
        # Day with no plan coverage at all
        assert by_date["2026-07-01"]["status"] == "none"

    def test_cold_store_fallback(self, monkeypatch):
        days = [_day("2026-07-06", sessions=[{"status": "done", "session_load_score": 15}])]
        archived = {"weeks": [{"days": days}]}
        from backend.engine import storage

        monkeypatch.setattr(
            storage,
            "read_archived_week",
            lambda uid, ws: archived if ws == "2026-07-06" else None,
        )
        out = generate_monthly_heatmap({"week_plans": {}}, "some-user", "2026-07")
        by_date = {c["date"]: c for c in out["days"]}
        assert by_date["2026-07-06"]["status"] == "done"
        assert by_date["2026-07-06"]["load"] == 15

    def test_free_session_included(self):
        state = {
            "week_plans": {},
            "free_sessions": [
                {"date": "2026-07-03", "finished_at": "2026-07-03T18:00:00", "load_score": 9},
                {"date": "2026-07-03", "finished_at": "2026-07-03T20:00:00", "load_score": 5},
                {"date": "2026-07-04", "load_score": 99},  # not finished → ignored
            ],
        }
        out = generate_monthly_heatmap(state, None, "2026-07")
        by_date = {c["date"]: c for c in out["days"]}
        assert by_date["2026-07-03"]["status"] == "done"
        assert by_date["2026-07-03"]["load"] == 14
        assert by_date["2026-07-04"]["status"] == "none"


class TestApi:
    def test_endpoint_ok(self):
        r = client.get(
            "/api/reports/heatmap?month=2026-07",
            headers={"X-User-ID": _TEST_USER_ID},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["month"] == "2026-07"
        assert len(body["days"]) == 31
        assert {"date", "status", "load"} <= set(body["days"][0].keys())

    def test_invalid_month_422(self):
        for bad in ("2026-13", "07-2026", "2026-7", "garbage"):
            r = client.get(
                f"/api/reports/heatmap?month={bad}",
                headers={"X-User-ID": _TEST_USER_ID},
            )
            assert r.status_code == 422, bad
